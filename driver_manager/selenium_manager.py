import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium_stealth import stealth
from config.settings import settings
from typing import Optional
import time
import json
import random
import os
import zipfile
import tempfile
import shutil
import undetected_chromedriver as uc
from utils.proxy_manager import proxy_manager, ProxyInfo

logger = logging.getLogger(__name__)


class SeleniumManager:
    def __init__(self):
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        self.proxy: Optional[ProxyInfo] = None

    @staticmethod
    def build_proxy_auth_extension(username: str, password: str) -> str:
        """Создаёт Chrome-расширение (Manifest V3) для авторизации прокси."""

        manifest_json = """{
      "manifest_version": 3,
      "name": "Proxy Auth",
      "version": "1.0",
      "permissions": [
        "proxy",
        "webRequest",
        "webRequestAuthProvider"
      ],
      "host_permissions": [
        "<all_urls>"
      ],
      "background": {
        "service_worker": "background.js"
      }
    }"""

        background_js = f"""
    chrome.webRequest.onAuthRequired.addListener(
      function(details) {{
        return {{
          authCredentials: {{
            username: "{username}",
            password: "{password}"
          }}
        }};
      }},
      {{urls: ["<all_urls>"]}},
      ["blocking"]
    );
    """

        tmp_dir = tempfile.mkdtemp(prefix="chrome_proxy_auth_")
        plugin_path = os.path.join(tmp_dir, "proxy_auth_plugin.zip")

        with zipfile.ZipFile(plugin_path, "w") as zp:
            zp.writestr("manifest.json", manifest_json)
            zp.writestr("background.js", background_js)

        return plugin_path

    def setup_driver(self):
        chrome_options = uc.ChromeOptions()

        if settings.HEADLESS:
            chrome_options.add_argument("--headless=new")

        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--allow-running-insecure-content")

        # Отключить автоматизационные флаги
        # chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        # chrome_options.add_experimental_option('useAutomationExtension', False)

        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/143.0.0.0 Safari/537.36"
        )

        chrome_binary = self._find_chrome_binary()

        if chrome_binary:
            chrome_options.binary_location = chrome_binary
            logger.info("Using Chrome binary at %s", chrome_binary)
        else:
            logger.warning("Chrome binary not found via autodetect, relying on default lookup")

        self.proxy = proxy_manager.get_random_proxy()

        if self.proxy:
            chrome_options.add_argument(f"--proxy-server={self.proxy.browser_proxy}")

            # 2) Расширение с авторизацией (логин/пароль одинаковы для всех)
            proxy_ext_path = self.build_proxy_auth_extension(self.proxy.login, self.proxy.password)
            chrome_options.add_extension(proxy_ext_path)

            logger.info("Using proxy %s", self.proxy.browser_proxy)
        else:
            logger.info("Proxy is not configured or list is empty, using direct connection")

        driver = uc.Chrome(options=chrome_options, browser_executable_path=chrome_binary if chrome_binary else None)

        self.driver = driver
        self.wait = WebDriverWait(driver, 20)

        logger.info("Chrome driver created successfully")
        return driver

    def _find_chrome_binary(self) -> Optional[str]:
        """Locate Chrome/Chromium executable.

        Priority:
        1. Explicit CHROME_BINARY environment variable
        2. Common executables in PATH: google-chrome, chromium, chromium-browser, chrome
        """

        env_path = settings.CHROME_BINARY
        if env_path and os.path.isfile(env_path):
            return env_path

        candidates = ["google-chrome", "chromium", "chromium-browser", "chrome"]
        for name in candidates:
            path = shutil.which(name)
            if path:
                return path

        return None

    def navigate_to_url(self, url: str) -> bool:
        if not self.driver:
            logger.error("Driver not initialized")
            return False

        try:
            logger.info(f"Navigating to: {url}")
            self.driver.get(url)

            # Минимальная задержка для API
            time.sleep(random.uniform(0.3, 0.8))

            # Быстрая проверка блокировки только по заголовку
            if "Access denied" in self.driver.title or "Cloudflare" in self.driver.title:
                logger.warning("Detected anti-bot protection")
                return False

            return True

        except TimeoutException:
            logger.error(f"Timeout while loading: {url}")
            return False
        except WebDriverException as e:
            logger.error(f"WebDriver error: {e}")
            return False

    def is_blocked(self) -> bool:
        """
        Check if we're blocked by anti-bot protection
        """
        if not self.driver:
            return True

        try:
            # Common anti-bot indicators
            blocked_indicators = [
                "cloudflare",
                "checking your browser",
                "enable javascript",
                "access denied",
                "blocked"
            ]

            page_source = self.driver.page_source.lower()

            for indicator in blocked_indicators:
                if indicator in page_source:
                    return True

            return False

        except Exception:
            return True

    def wait_for_json_response(self, timeout: int = 30) -> Optional[str]:
        if not self.driver:
            return None

        try:
            start_time = time.time()

            # Ждём полной загрузки страницы столько, сколько задано timeout
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )

            last_snippet = None

            while time.time() - start_time < timeout:
                try:
                    page_source = self.driver.page_source
                    json_content = self.extract_json_from_html(page_source)

                    if json_content:
                        try:
                            data = json.loads(json_content)
                            if "widgetStates" in data:
                                logger.info("JSON response with widgetStates found")
                                return json_content
                        except json.JSONDecodeError:
                            pass

                    # Диагностика тела ответа
                    try:
                        snippet = self.driver.execute_script(
                            "return document.body.innerText"
                        )[:500]

                        if snippet != last_snippet:
                            last_snippet = snippet
                            logger.debug(f"Body snippet (first 500 chars): {snippet}")
                    except Exception:
                        pass

                    time.sleep(0.5)

                except Exception as e:
                    logger.debug(f"Error checking page source: {e}")
                    time.sleep(0.5)
                    continue

            logger.warning(f"Timeout waiting for JSON response after {timeout} seconds")

            try:
                snippet = self.driver.execute_script(
                    "return document.body.innerText"
                )[:500]
                logger.warning(f"Final body snippet: {snippet}")
            except Exception:
                pass

            return self.extract_json_from_html(self.driver.page_source)

        except Exception as e:
            logger.error(f"Error waiting for JSON response: {e}")
            return None

    def extract_json_from_html(self, html_content: str) -> Optional[str]:
        try:
            import re

            pre_pattern = r'<pre[^>]*>(.*?)</pre>'
            pre_match = re.search(pre_pattern, html_content, re.DOTALL | re.IGNORECASE)

            if pre_match:
                json_content = pre_match.group(1).strip()
                logger.debug("Found JSON in <pre> tag")
                return json_content

            # Если не нашли в <pre>, попробуем найти JSON напрямую
            # Ищем первую открывающую скобку до последней закрывающей
            first_brace = html_content.find('{')
            last_brace = html_content.rfind('}')

            if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
                json_content = html_content[first_brace:last_brace + 1]
                logger.debug("Found JSON by brace search")
                return json_content

            logger.debug("No JSON found in HTML content")
            return None

        except Exception as e:
            logger.error(f"Error extracting JSON from HTML: {e}")
            return None

    def debug_page_content(self):
        """
        Debug helper to see what's on the page
        """
        if not self.driver:
            return

        try:
            content = self.driver.page_source
            logger.info(f"Page content length: {len(content)}")
            logger.info(f"Content starts with: {content[:200]}")

            # Проверяем наличие <pre> тега
            if '<pre' in content.lower():
                logger.info("Page contains <pre> tag")

                # Попробуем извлечь JSON
                json_content = self.extract_json_from_html(content)
                if json_content:
                    logger.info(f"Extracted JSON length: {len(json_content)}")
                    logger.info(f"JSON starts with: {json_content[:100]}")

                    try:
                        data = json.loads(json_content)
                        if 'widgetStates' in data:
                            logger.info("Extracted JSON contains widgetStates")
                            widget_states = data['widgetStates']
                            logger.info(f"WidgetStates keys count: {len(widget_states)}")
                        else:
                            logger.info("Extracted JSON does not contain widgetStates")
                            logger.info(f"JSON keys: {list(data.keys())}")
                    except json.JSONDecodeError as e:
                        logger.info(f"Extracted content is not valid JSON: {e}")
                else:
                    logger.info("Could not extract JSON from <pre> tag")

            # Проверяем наличие JavaScript
            if 'script' in content.lower():
                logger.info("Page contains JavaScript")

            # Проверяем, есть ли уже JSON напрямую
            stripped_content = content.strip()
            if stripped_content.startswith('{'):
                logger.info("Page contains direct JSON structure")
            else:
                logger.info("Page contains HTML wrapper")

        except Exception as e:
            logger.error(f"Error in debug: {e}")

    def close(self):
        """
        Close driver and cleanup
        """
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Driver closed successfully")
            except Exception as e:
                logger.error(f"Error closing driver: {e}")
            finally:
                self.driver = None
                self.wait = None
