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
import textwrap

logger = logging.getLogger(__name__)



class SeleniumManager:
    def __init__(self):
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        self.proxy: Optional[ProxyInfo] = None
        self._proxy_ext_dir: Optional[str] = None

    def build_proxy_auth_extension_dir(self, username: str, password: str) -> str:
        """
        Создаёт unpacked Chrome-расширение (Manifest V3), которое автоматически
        подставляет proxy-логин/пароль через onAuthRequired.
        Возвращает путь к директории расширения.
        """

        # Манифест для MV3
        manifest_json = textwrap.dedent(f"""
        {{
          "name": "Proxy Auth Helper",
          "description": "Auto-auth for HTTP proxy",
          "version": "1.0.0",
          "manifest_version": 3,
          "permissions": [
            "proxy",
            "storage",
            "webRequest",
            "webRequestAuthProvider"
          ],
          "host_permissions": [
            "<all_urls>"
          ],
          "background": {{
            "service_worker": "background.js"
          }}
        }}
        """).strip()

        # background.js: всегда отдаём одни и те же креды
        background_js = textwrap.dedent(f"""
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
        """).strip()

        tmp_dir = tempfile.mkdtemp(prefix="chrome_proxy_auth_ext_")

        manifest_path = os.path.join(tmp_dir, "manifest.json")
        background_path = os.path.join(tmp_dir, "background.js")

        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(manifest_json)

        with open(background_path, "w", encoding="utf-8") as f:
            f.write(background_js)

        # запомним, чтобы потом удалить
        self._proxy_ext_dir = tmp_dir
        logger.info("Proxy auth extension created at %s", tmp_dir)

        return tmp_dir


    def detect_ip_via_page(self, tag: str = ""):
        """
        Отдельная навигация на сервис, который отдаёт IP в теле ответа,
        чтение этого IP через document.body.innerText.
        Это обходит проблемы с fetch/cors и даёт 100% картину именно из браузера.
        """
        if not self.driver:
            logger.warning("detect_ip_via_page called but driver is None")
            return

        test_url = "https://api.ipify.org?format=text"  # можно поменять на другой сервис, если этот блочится

        try:
            logger.info("Navigating to IP check page: %s", test_url)
            self.driver.get(test_url)

            # дадим странице чуть времени
            import time
            time.sleep(1.0)

            ip_text = self.driver.execute_script(
                "return document.body && document.body.innerText ? document.body.innerText.trim() : '';"
            )

            if ip_text:
                logger.info("Outbound IP via page (%s): %s", tag, ip_text)
            else:
                logger.warning("Could not read IP text from page (%s)", tag)

        except Exception as e:
            logger.warning("Failed to detect IP via page (%s): %s", tag, e)


    def log_current_ip(self, tag: str = ""):
        """
        Логируем внешний IP, с которого Chromium ходит в интернет (через прокси).
        Используем execute_async_script, чтобы дождаться fetch().
        Если не удалось — логируем текст ошибки.
        """
        if not self.driver:
            logger.warning("log_current_ip called but driver is None")
            return

        try:
            script = """
                var done = arguments[0];
                fetch('https://api.ipify.org?format=json')
                  .then(function(r) { return r.json(); })
                  .then(function(d) {
                      done({ok: true, ip: d.ip});
                  })
                  .catch(function(e) {
                      done({ok: false, error: String(e)});
                  });
            """
            result = self.driver.execute_async_script(script)

            # result должен быть объектом {ok: bool, ip?: str, error?: str}
            if not isinstance(result, dict):
                logger.warning("Unexpected IP check result (%s): %r", tag, result)
                return

            if result.get("ok") and result.get("ip"):
                if tag:
                    logger.info("Outbound IP (%s): %s", tag, result["ip"])
                else:
                    logger.info("Outbound IP: %s", result["ip"])
            else:
                logger.warning(
                    "Could not detect outbound IP (%s): %s",
                    tag,
                    result.get("error", "unknown error"),
                )
        except Exception as e:
            logger.warning("Failed to detect outbound IP (%s): %s", tag, e)

    def build_proxy_auth_extension(self) -> str:
        """
        Создаёт Chrome-расширение (Manifest V3), которое автоматически
        подставляет proxy-логин/пароль через onAuthRequired.
        Возвращает путь к .zip файлу расширения.
        """

        # Манифест для MV3
        manifest_json = f"""
    {{
      "name": "Proxy Auth Helper",
      "description": "Auto-auth for HTTP proxy",
      "version": "1.0.0",
      "manifest_version": 3,
      "permissions": [
        "proxy",
        "storage",
        "webRequest",
        "webRequestAuthProvider"
      ],
      "host_permissions": [
        "<all_urls>"
      ],
      "background": {{
        "service_worker": "background.js"
      }}
    }}
    """

        # background.js: всегда отдаём одни и те же креды
        background_js = f"""
    chrome.webRequest.onAuthRequired.addListener(
      (details, callback) => {{
        callback({{
          authCredentials: {{
            username: "{self.proxy.login}",
            password: "{self.proxy.password}"
          }}
        }});
      }},
      {{ urls: ["<all_urls>"] }},
      ["asyncBlocking"]
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
        chrome_options.add_argument("--log-net-log=/tmp/chrome_netlog.json")
        chrome_options.add_argument("--net-log-capture-mode=Everything")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        # chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
            "YaBrowser/25.12.0.2002.10 YaApp_iOS/2512.0 "
            "YaApp_iOS_Browser/2512.0 Safari/604.1 SA/3"
        )

        chrome_binary = self._find_chrome_binary()

        if chrome_binary:
            chrome_options.binary_location = chrome_binary
            logger.info("Using Chrome binary at %s", chrome_binary)
        else:
            logger.warning("Chrome binary not found via autodetect, relying on default lookup")

        self.proxy = proxy_manager.get_random_proxy()

        if self.proxy:
            if not self.check_proxy_alive(self.proxy):
                logger.warning("Selected proxy is not alive, falling back to direct connection")
                self.proxy = None

        if self.proxy:
            # 1) направляем трафик через прокси
            chrome_options.add_argument(f"--proxy-server={self.proxy.browser_proxy}")

            # 2) расширение с авторизацией (логин/пароль берём из ProxyInfo)
            try:
                ext_dir = self.build_proxy_auth_extension_dir(
                    username=self.proxy.login,
                    password=self.proxy.password,
                )
                chrome_options.add_argument(f"--load-extension={ext_dir}")
                logger.info("Using proxy %s with auth extension", self.proxy.browser_proxy)
            except Exception as e:
                logger.error("Failed to create proxy auth extension: %s", e)
        else:
            logger.info("Proxy is not configured or list is empty, using direct connection")

        driver = uc.Chrome(
            options=chrome_options,
            browser_executable_path=chrome_binary if chrome_binary else None
        )
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.driver = driver
        self.wait = WebDriverWait(driver, 20)

        logger.info("Chrome driver created successfully")

        # Можно оставить сразу после инициализации:
        self.log_current_ip(tag="after driver init")

        self.detect_ip_via_page(tag="after driver init")

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
            logger.info("Navigating to: %s", url)
            self.driver.get(url)

            # Минимальная задержка для API
            time.sleep(random.uniform(3, 7))

            try:
                title = self.driver.title
            except Exception:
                title = "<no title>"

            try:
                self.driver.execute_script("window.scrollBy(0, document.body.scrollHeight * 0.5);")
            except Exception as e:
                logger.debug("Scroll JS failed: %s", e)

            time.sleep(random.uniform(2, 4))

            current_url = None
            body_snippet = None

            try:
                current_url = self.driver.current_url
                body_snippet = self.driver.execute_script(
                    "return document.body.innerText.slice(0, 300);"
                )
            except Exception as e:
                logger.debug("Error getting page debug info after navigation: %s", e)

            logger.debug(
                "After navigation: current_url=%s, title=%r, body_snippet_start=%r",
                current_url, title, body_snippet
            )

            # Проверка блокировки
            if self.is_blocked():
                logger.warning(
                    "Detected anti-bot/blocked page. url=%s, title=%r, snippet=%r",
                    current_url, title, body_snippet
                )
                return False

            # Старый быстрый кейс тоже можно оставить
            if "Access denied" in (title or "") or "Cloudflare" in (title or ""):
                logger.warning("Detected anti-bot protection by title")
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
                "blocked",
                "доступ ограничен",
                "инцидент:",
                "confirm that you're not a bot",  # Добавили для капчи
                "slide the"  # Добавили для слайдер-капчи
            ]

            page_source = self.driver.page_source.lower()

            for indicator in blocked_indicators:
                if indicator in page_source:
                    logger.warning("Anti-bot indicator detected: %r", indicator)

                    # Если это капча, пытаемся решить
                    if "slide the" in page_source or "confirm that you're not a bot" in page_source:
                        logger.info("Attempting to solve captcha automatically...")
                        if self.attempt_captcha_solution():
                            logger.info("Captcha solved, continuing...")
                            return False  # Не заблокирован, капча решена

                    return True

            return False

        except Exception:
            return True

    # Обновите selenium_manager.py
    def attempt_captcha_solution(self):
        """Пытается решить капчу Ozon с новым решателем"""
        try:
            from utils.ozon_captcha_solver_v3 import OzonCaptchaSolverV3
            solver = OzonCaptchaSolverV3(self.driver)

            # Даем время для полной загрузки капчи
            time.sleep(2)

            return solver.solve()
        except Exception as e:
            logger.error(f"Failed to solve captcha: {e}")
            return False

    # Обновите метод is_blocked для более точного определения
    def is_blocked(self) -> bool:
        """Check if we're blocked by anti-bot protection"""
        if not self.driver:
            return True

        try:
            # Получаем текущий URL и заголовок
            current_url = self.driver.current_url.lower()
            title = self.driver.title.lower()

            # Быстрая проверка по URL и заголовку
            if any(keyword in current_url for keyword in ['antibot', '__rr']) or \
                    'captcha' in title:
                logger.warning(f"Blocked by captcha: URL={current_url}, title={title}")
                return True

            # Проверка по тексту на странице
            page_text = self.driver.page_source.lower()
            blocked_indicators = [
                "confirm that you're not a bot",
                "slide the slider",
                "puzzle piece",
                "antibot captcha",
                "enable javascript",
                "checking your browser",
                "доступ ограничен"
            ]

            for indicator in blocked_indicators:
                if indicator in page_text:
                    logger.warning(f"Blocked indicator found: {indicator}")
                    return True

            return False

        except Exception as e:
            logger.error(f"Error checking if blocked: {e}")
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

    def check_proxy_alive(self, proxy: ProxyInfo, timeout: int = 10) -> bool:
        import requests

        proxy_url = f"http://{proxy.login}:{proxy.password}@{proxy.host}:{proxy.port}"
        proxies = {
            "http": proxy_url,
            "https": proxy_url,
        }

        try:
            resp = requests.get(
                "https://www.google.com/generate_204",
                proxies=proxies,
                timeout=timeout,
                allow_redirects=False,
            )
            # Если вообще доехали и получили ответ — считаем, что прокси живой
            logger.info(
                "Proxy %s is reachable, status=%s, reason=%s",
                proxy_url, resp.status_code, resp.reason
            )
            return True
        except requests.exceptions.ProxyError as e:
            logger.warning("Proxy %s ProxyError (likely dead/unusable): %s", proxy_url, e)
            return False
        except requests.exceptions.ConnectTimeout as e:
            logger.warning("Proxy %s connect timeout: %s", proxy_url, e)
            return False
        except requests.exceptions.ReadTimeout as e:
            logger.warning("Proxy %s read timeout: %s", proxy_url, e)
            return False
        except Exception as e:
            logger.warning("Proxy %s unexpected error while checking: %s", proxy_url, e)
            # тут уже по вкусу: можно вернуть False, можно True
            return False

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

        # чистим временную директорию расширения
        if self._proxy_ext_dir:
            try:
                shutil.rmtree(self._proxy_ext_dir, ignore_errors=True)
                logger.info("Proxy extension directory %s removed", self._proxy_ext_dir)
            except Exception as e:
                logger.error("Error removing proxy extension directory %s: %s",
                             self._proxy_ext_dir, e)
            finally:
                self._proxy_ext_dir = None
