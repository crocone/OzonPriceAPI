import json
import logging
import os
import random
import re
import shutil
import tempfile
import textwrap
import time
from typing import Optional

import requests
import undetected_chromedriver as uc
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium_stealth import stealth

from config.settings import settings
from utils.proxy_manager import ProxyInfo, proxy_manager

logger = logging.getLogger(__name__)


class SeleniumManager:
    def __init__(self):
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        self.proxy: Optional[ProxyInfo] = None
        self._proxy_ext_dir: Optional[str] = None

    def build_proxy_auth_extension_dir(self, username: str, password: str) -> str:
        """Create unpacked MV3 extension for proxy authentication."""
        manifest_json = textwrap.dedent(
            """
            {
              "name": "Proxy Auth Helper",
              "description": "Auto-auth for HTTP proxy",
              "version": "1.0.0",
              "manifest_version": 3,
              "permissions": ["proxy", "storage", "webRequest", "webRequestAuthProvider"],
              "host_permissions": ["<all_urls>"],
              "background": {"service_worker": "background.js"}
            }
            """
        ).strip()

        background_js = textwrap.dedent(
            f"""
            chrome.webRequest.onAuthRequired.addListener(
              (details, callback) => {{
                callback({{
                  authCredentials: {{
                    username: "{username}",
                    password: "{password}"
                  }}
                }});
              }},
              {{ urls: ["<all_urls>"] }},
              ["asyncBlocking"]
            );
            """
        ).strip()

        tmp_dir = tempfile.mkdtemp(prefix="chrome_proxy_auth_ext_")
        with open(os.path.join(tmp_dir, "manifest.json"), "w", encoding="utf-8") as f:
            f.write(manifest_json)
        with open(os.path.join(tmp_dir, "background.js"), "w", encoding="utf-8") as f:
            f.write(background_js)

        self._proxy_ext_dir = tmp_dir
        logger.info("Proxy auth extension created at %s", tmp_dir)
        return tmp_dir

    def _find_chrome_binary(self) -> Optional[str]:
        env_path = settings.CHROME_BINARY
        if env_path and os.path.isfile(env_path):
            return env_path

        for name in ["google-chrome", "chromium", "chromium-browser", "chrome"]:
            path = shutil.which(name)
            if path:
                return path
        return None

    def _random_desktop_user_agent(self) -> str:
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        ]
        if settings.USER_AGENT:
            user_agents.insert(0, settings.USER_AGENT)
        return random.choice(user_agents)

    def setup_driver(self):
        chrome_options = uc.ChromeOptions()

        if settings.HEADLESS:
            chrome_options.add_argument("--headless=new")

        width = random.randint(1280, 1920)
        height = random.randint(720, 1080)
        user_agent = self._random_desktop_user_agent()

        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument(f"--window-size={width},{height}")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--disable-features=IsolateOrigins,site-per-process")
        chrome_options.add_argument("--lang=ru-RU")
        chrome_options.add_argument(f"--user-agent={user_agent}")

        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        chrome_binary = self._find_chrome_binary()
        if chrome_binary:
            chrome_options.binary_location = chrome_binary
            logger.info("Using Chrome binary at %s", chrome_binary)

        self.proxy = proxy_manager.get_random_proxy()
        if self.proxy and not self.check_proxy_alive(self.proxy):
            logger.warning("Selected proxy is not alive, fallback to direct connection")
            self.proxy = None

        if self.proxy:
            chrome_options.add_argument(f"--proxy-server={self.proxy.browser_proxy}")
            try:
                ext_dir = self.build_proxy_auth_extension_dir(self.proxy.login, self.proxy.password)
                chrome_options.add_argument(f"--load-extension={ext_dir}")
                logger.info("Using proxy %s", self.proxy.browser_proxy)
            except Exception as exc:
                logger.error("Failed to create proxy auth extension: %s", exc)

        driver = uc.Chrome(
            options=chrome_options,
            browser_executable_path=chrome_binary if chrome_binary else None,
        )
        self.driver = driver
        self.wait = WebDriverWait(driver, settings.PAGE_LOAD_TIMEOUT)

        self._apply_stealth(user_agent)
        logger.info("Chrome driver created successfully")

        self.log_current_ip(tag="after driver init")
        return driver

    def _apply_stealth(self, user_agent: str):
        if not self.driver:
            return

        try:
            stealth(
                self.driver,
                languages=["ru-RU", "ru", "en-US", "en"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
            )
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            self.driver.execute_cdp_cmd(
                "Network.setUserAgentOverride",
                {"userAgent": user_agent, "platform": "Windows", "acceptLanguage": "ru-RU,ru;q=0.9,en-US;q=0.8"},
            )
        except Exception as exc:
            logger.warning("Failed to apply stealth patches: %s", exc)

    def log_current_ip(self, tag: str = ""):
        if not self.driver:
            return

        script = """
            var done = arguments[0];
            fetch('https://api.ipify.org?format=json')
              .then(r => r.json())
              .then(d => done({ok: true, ip: d.ip}))
              .catch(e => done({ok: false, error: String(e)}));
        """

        try:
            result = self.driver.execute_async_script(script)
            if isinstance(result, dict) and result.get("ok"):
                logger.info("Outbound IP (%s): %s", tag, result.get("ip"))
            else:
                logger.warning("Could not detect outbound IP (%s): %s", tag, result)
        except Exception as exc:
            logger.warning("Failed to detect outbound IP (%s): %s", tag, exc)

    def navigate_to_url(self, url: str) -> bool:
        if not self.driver:
            logger.error("Driver not initialized")
            return False

        try:
            logger.info("Navigating to: %s", url)
            self.driver.get(url)
            time.sleep(random.uniform(2.0, 4.5))

            try:
                self.driver.execute_script("window.scrollBy(0, document.body.scrollHeight * 0.35);")
                time.sleep(random.uniform(0.8, 1.5))
            except Exception:
                pass

            if self.is_blocked():
                logger.warning("Detected anti-bot/blocked page during navigation: %s", url)
                return False

            return True
        except TimeoutException:
            logger.error("Timeout while loading: %s", url)
            return False
        except WebDriverException as exc:
            logger.error("WebDriver error while loading %s: %s", url, exc)
            return False

    def attempt_captcha_solution(self) -> bool:
        try:
            from utils.captcha_solver import OzonCaptchaSolverV3

            solver = OzonCaptchaSolverV3(self.driver)
            time.sleep(1.5)
            return solver.solve()
        except Exception as exc:
            logger.error("Failed to solve captcha: %s", exc)
            return False

    def is_blocked(self) -> bool:
        if not self.driver:
            return True

        try:
            current_url = self.driver.current_url.lower()
            title = self.driver.title.lower()
            page_text = self.driver.page_source.lower()

            if any(keyword in current_url for keyword in ["antibot", "__rr", "captcha"]):
                logger.warning("Blocked by URL marker: %s", current_url)
                return True

            blocked_indicators = [
                "confirm that you're not a bot",
                "slide the slider",
                "puzzle piece",
                "antibot captcha",
                "enable javascript",
                "checking your browser",
                "доступ ограничен",
                "access denied",
            ]

            for indicator in blocked_indicators:
                if indicator in title or indicator in page_text:
                    logger.warning("Blocked indicator found: %s", indicator)
                    if indicator in {"confirm that you're not a bot", "slide the slider", "puzzle piece", "antibot captcha"}:
                        logger.info("Trying captcha solver...")
                        if self.attempt_captcha_solution():
                            logger.info("Captcha solver reported success")
                            return False
                    return True

            return False
        except Exception as exc:
            logger.error("Error checking blocked page: %s", exc)
            return True

    def load_cookies_from_file(self, cookies_path: str, domain: str):
        if not self.driver:
            raise RuntimeError("Driver not initialized")
        if not os.path.exists(cookies_path):
            raise FileNotFoundError(cookies_path)

        with open(cookies_path, "r", encoding="utf-8") as f:
            cookies = json.load(f)

        added = 0
        for cookie in cookies:
            if "expirationDate" in cookie:
                cookie["expiry"] = int(cookie.pop("expirationDate"))
            cookie.pop("sameSite", None)
            if domain not in cookie.get("domain", ""):
                continue
            try:
                self.driver.add_cookie(cookie)
                added += 1
            except Exception:
                continue

        logger.info("Loaded %d cookies for domain %s", added, domain)

    def wait_for_json_response(self, timeout: int = 30) -> Optional[str]:
        if not self.driver:
            return None

        try:
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )

            end_time = time.time() + timeout
            while time.time() < end_time:
                content = self.driver.page_source
                json_content = self.extract_json_from_html(content)

                if json_content:
                    try:
                        payload = json.loads(json_content)
                        if "widgetStates" in payload:
                            return json_content
                    except json.JSONDecodeError:
                        pass

                try:
                    body_text = self.driver.execute_script(
                        "return (document.body && document.body.innerText) ? document.body.innerText.trim() : ''"
                    )
                    if body_text.startswith("{") and "widgetStates" in body_text:
                        return body_text
                except Exception:
                    pass

                time.sleep(0.5)

            return self.extract_json_from_html(self.driver.page_source)
        except Exception as exc:
            logger.error("Error waiting for JSON response: %s", exc)
            return None

    def extract_json_from_html(self, html_content: str) -> Optional[str]:
        try:
            pre_match = re.search(r"<pre[^>]*>(.*?)</pre>", html_content, re.DOTALL | re.IGNORECASE)
            if pre_match:
                return pre_match.group(1).strip()

            first_brace = html_content.find("{")
            last_brace = html_content.rfind("}")
            if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
                return html_content[first_brace:last_brace + 1]
            return None
        except Exception:
            return None

    def check_proxy_alive(self, proxy: ProxyInfo, timeout: int = 10) -> bool:
        proxy_url = f"http://{proxy.login}:{proxy.password}@{proxy.host}:{proxy.port}"
        proxies = {"http": proxy_url, "https": proxy_url}
        try:
            response = requests.get(
                "https://www.google.com/generate_204",
                proxies=proxies,
                timeout=timeout,
                allow_redirects=False,
            )
            logger.info("Proxy %s reachable (status=%s)", proxy_url, response.status_code)
            return True
        except Exception as exc:
            logger.warning("Proxy %s not usable: %s", proxy_url, exc)
            return False

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Driver closed successfully")
            except Exception as exc:
                logger.error("Error closing driver: %s", exc)
            finally:
                self.driver = None
                self.wait = None

        if self._proxy_ext_dir:
            try:
                shutil.rmtree(self._proxy_ext_dir, ignore_errors=True)
            finally:
                self._proxy_ext_dir = None
