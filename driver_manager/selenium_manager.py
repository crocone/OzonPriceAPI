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
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

logger = logging.getLogger(__name__)


class SeleniumManager:
    def __init__(self):
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        self.proxy: Optional[ProxyInfo] = None
        self._proxy_ext_dir: Optional[str] = None
        self._profile_path: Optional[str] = None
        self._current_user_agent: Optional[str] = None

    def get_random_user_agent(self) -> str:
        """Возвращает случайный User-Agent"""
        user_agents = [
            # Desktop User-Agents
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            # Mobile User-Agents
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
            "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
        ]
        return random.choice(user_agents)

    def build_proxy_auth_extension_dir(self, username: str, password: str, host: str, port: str) -> str:
        """
        Создаёт unpacked Chrome-расширение (Manifest V2), которое автоматически
        подставляет proxy-логин/пароль через onAuthRequired.
        Возвращает путь к директории расширения.
        """
        # Используем Manifest V2 (более стабильный для прокси)
        manifest_json = textwrap.dedent(f"""
        {{
          "version": "1.0.0",
          "manifest_version": 2,
          "name": "Proxy Auth Helper",
          "description": "Auto-auth for HTTP proxy",
          "permissions": [
            "proxy",
            "tabs",
            "unlimitedStorage",
            "storage",
            "<all_urls>",
            "webRequest",
            "webRequestBlocking"
          ],
          "background": {{
            "scripts": ["background.js"]
          }}
        }}
        """).strip()

        background_js = textwrap.dedent(f"""
        var config = {{
            mode: "fixed_servers",
            rules: {{
                singleProxy: {{
                    scheme: "http",
                    host: "{host}",
                    port: parseInt("{port}")
                }},
                bypassList: ["localhost"]
            }}
        }};

        chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});

        function callbackFn(details) {{
            return {{
                authCredentials: {{
                    username: "{username}",
                    password: "{password}"
                }}
            }};
        }}

        chrome.webRequest.onAuthRequired.addListener(
            callbackFn,
            {{urls: ["<all_urls>"]}},
            ['blocking']
        );
        """).strip()

        tmp_dir = tempfile.mkdtemp(prefix="chrome_proxy_auth_ext_")

        manifest_path = os.path.join(tmp_dir, "manifest.json")
        background_path = os.path.join(tmp_dir, "background.js")

        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(manifest_json)

        with open(background_path, "w", encoding="utf-8") as f:
            f.write(background_js)

        self._proxy_ext_dir = tmp_dir
        logger.info("Proxy auth extension created at %s", tmp_dir)
        return tmp_dir

    def patch_driver(self):
        """Патчим WebDriver чтобы он не обнаруживался"""
        if not self.driver:
            return

        try:
            # Удаляем webdriver свойства
            self.driver.execute_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });

                // Патчим chrome runtime
                window.chrome = {
                    runtime: {},
                    loadTimes: function(){},
                    csi: function(){},
                    app: {}
                };

                // Патчим plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });

                // Патчим languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['ru-RU', 'ru', 'en-US', 'en']
                });
            """)

            # Патчим через CDP
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                '''
            })

        except Exception as e:
            logger.warning("Error patching driver: %s", e)

    def simulate_human_behavior(self):
        """Имитация человеческого поведения"""
        if not self.driver:
            return

        try:
            actions = [
                lambda: self.driver.execute_script("window.scrollBy(0, {})".format(random.randint(100, 500))),
                lambda: self.driver.execute_script("window.scrollBy(0, {})".format(-random.randint(50, 200))),
                lambda: self.driver.execute_script("""
                    // Клик по пустому месту
                    document.body.click();
                """),
                lambda: self.driver.execute_script("""
                    // Движение мыши
                    const event = new MouseEvent('mousemove', {
                        view: window,
                        bubbles: true,
                        cancelable: true,
                        clientX: %d,
                        clientY: %d
                    });
                    if (document.elementFromPoint(100, 100)) {
                        document.elementFromPoint(100, 100).dispatchEvent(event);
                    }
                """ % (random.randint(100, 500), random.randint(100, 300))),
            ]

            # Выполняем 3-5 случайных действий
            for _ in range(random.randint(2, 4)):
                random.choice(actions)()
                time.sleep(random.uniform(0.1, 0.3))

        except Exception as e:
            logger.debug("Error simulating human behavior: %s", e)

    def detect_ip_via_page(self, tag: str = ""):
        """
        Отдельная навигация на сервис, который отдаёт IP в теле ответа,
        чтение этого IP через document.body.innerText.
        Это обходит проблемы с fetch/cors и даёт 100% картину именно из браузера.
        """
        if not self.driver:
            logger.warning("detect_ip_via_page called but driver is None")
            return

        test_urls = [
            "https://api.ipify.org?format=text",
            "https://checkip.amazonaws.com/",
            "https://ifconfig.me/ip"
        ]

        test_url = random.choice(test_urls)

        try:
            logger.debug("Navigating to IP check page: %s", test_url)
            self.driver.get(test_url)

            # Дадим странице время загрузиться
            time.sleep(random.uniform(1.0, 2.0))

            ip_text = self.driver.execute_script(
                "return document.body && document.body.innerText ? document.body.innerText.trim() : '';"
            )

            if ip_text:
                logger.info("Outbound IP via page (%s): %s", tag, ip_text)
            else:
                logger.warning("Could not read IP text from page (%s)", tag)

        except Exception as e:
            logger.warning("Failed to detect IP via page (%s): %s", tag, e)

    def setup_driver(self):
        # Создаем уникальный профиль для каждого драйвера
        profile_num = random.randint(1000, 9999)
        self._profile_path = f"/tmp/chrome_profile_{profile_num}"
        if not os.path.exists(self._profile_path):
            os.makedirs(self._profile_path)

        chrome_options = uc.ChromeOptions()

        if settings.HEADLESS:
            chrome_options.add_argument("--headless=new")

        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        # Случайный размер окна
        width = random.randint(1200, 1920)
        height = random.randint(800, 1080)
        chrome_options.add_argument(f"--window-size={width},{height}")

        # Anti-detection
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        # User-Agent
        self._current_user_agent = self.get_random_user_agent()
        chrome_options.add_argument(f"--user-agent={self._current_user_agent}")

        # Профиль
        chrome_options.add_argument(f"--user-data-dir={self._profile_path}")
        chrome_options.add_argument("--profile-directory=Default")

        # Дополнительные настройки
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--disable-features=IsolateOrigins,site-per-process")
        chrome_options.add_argument("--disable-site-isolation-trials")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-setuid-sandbox")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-popup-blocking")
        chrome_options.add_argument("--disable-default-apps")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--disable-background-timer-throttling")

        # Локаль и язык
        chrome_options.add_argument("--lang=ru-RU")
        chrome_options.add_argument("--accept-lang=ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7")

        chrome_binary = self._find_chrome_binary()
        if chrome_binary:
            chrome_options.binary_location = chrome_binary
            logger.info("Using Chrome binary at %s", chrome_binary)
        else:
            logger.warning("Chrome binary not found via autodetect, relying on default lookup")

        # Выбор и проверка прокси
        self.proxy = proxy_manager.get_random_proxy()
        if self.proxy:
            if not self.check_proxy_alive(self.proxy):
                logger.warning("Selected proxy is not alive, trying another one")
                self.proxy = proxy_manager.get_random_proxy(exclude_current=True)

        if self.proxy and self.check_proxy_alive(self.proxy):
            try:
                # Разбираем прокси на части
                proxy_parts = self.proxy.browser_proxy.replace("http://", "").split(":")
                if len(proxy_parts) >= 2:
                    host = proxy_parts[0]
                    port = proxy_parts[1].split("/")[0] if "/" in proxy_parts[1] else proxy_parts[1]

                    ext_dir = self.build_proxy_auth_extension_dir(
                        username=self.proxy.login,
                        password=self.proxy.password,
                        host=host,
                        port=port
                    )
                    chrome_options.add_argument(f"--load-extension={ext_dir}")
                    logger.info("Using proxy %s with auth extension", self.proxy.browser_proxy)
                else:
                    logger.error("Invalid proxy format: %s", self.proxy.browser_proxy)
                    self.proxy = None
            except Exception as e:
                logger.error("Failed to create proxy auth extension: %s", e)
                self.proxy = None
        else:
            logger.info("Proxy is not configured or list is empty, using direct connection")
            self.proxy = None

        try:
            driver = uc.Chrome(
                options=chrome_options,
                browser_executable_path=chrome_binary if chrome_binary else None,
                version_main=None,  # Автоопределение версии
                suppress_welcome=True
            )

            self.driver = driver
            self.wait = WebDriverWait(driver, 20)

            # Патчим драйвер
            self.patch_driver()

            # Дополнительные настройки через CDP
            driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": self._current_user_agent,
                "platform": "Windows"
            })

            logger.info("Chrome driver created successfully")

            # Проверяем IP
            self.detect_ip_via_page(tag="after driver init")

            # Прогрев: заходим на нейтральный сайт
            self.warm_up_browser()

            return driver

        except Exception as e:
            logger.error("Failed to create driver: %s", e)
            raise

    def warm_up_browser(self):
        """Прогрев браузера перед работой"""
        if not self.driver:
            return

        try:
            # Заходим на нейтральные сайты для создания истории
            warm_up_urls = [
                "https://www.google.com",
                "https://yandex.ru",
                "https://mail.ru"
            ]

            for url in random.sample(warm_up_urls, k=random.randint(1, 2)):
                try:
                    self.driver.get(url)
                    time.sleep(random.uniform(2, 4))
                    self.simulate_human_behavior()
                    logger.debug("Warmed up on: %s", url)
                except Exception as e:
                    logger.debug("Error warming up on %s: %s", url, e)

        except Exception as e:
            logger.debug("Error in warm_up_browser: %s", e)

    def navigate_to_url(self, url: str, max_retries: int = 3) -> bool:
        if not self.driver:
            logger.error("Driver not initialized")
            return False

        for attempt in range(max_retries):
            try:
                logger.info("Navigating to: %s (attempt %d/%d)", url, attempt + 1, max_retries)

                # Имитируем человеческое поведение перед загрузкой
                if attempt > 0:
                    time.sleep(random.uniform(1, 3))
                    self.simulate_human_behavior()

                self.driver.get(url)

                # Рандомизированная задержка для имитации человеческой реакции
                time.sleep(random.uniform(0.5, 2.0))

                # Имитируем человеческое поведение после загрузки
                self.simulate_human_behavior()

                try:
                    title = self.driver.title
                except Exception:
                    title = "<no title>"

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

                    if attempt < max_retries - 1:
                        # Меняем стратегию перед следующей попыткой
                        self.change_navigation_strategy()
                        continue
                    return False

                if "Access denied" in (title or "") or "Cloudflare" in (title or ""):
                    logger.warning("Detected anti-bot protection by title")
                    if attempt < max_retries - 1:
                        continue
                    return False

                return True

            except TimeoutException:
                logger.error(f"Timeout while loading: {url} (attempt {attempt + 1})")
                if attempt < max_retries - 1:
                    time.sleep(random.uniform(2, 5))
                    continue
                return False

            except WebDriverException as e:
                logger.error(f"WebDriver error: {e} (attempt {attempt + 1})")
                if attempt < max_retries - 1:
                    time.sleep(random.uniform(2, 5))
                    continue
                return False

        return False

    def change_navigation_strategy(self):
        """Изменяет стратегию навигации при обнаружении блокировки"""
        try:
            # Добавляем новые аргументы при следующем запуске
            if self.driver:
                # Меняем User-Agent
                new_ua = self.get_random_user_agent()
                self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                    "userAgent": new_ua,
                    "platform": "Windows"
                })

                # Очищаем куки
                self.driver.delete_all_cookies()

                # Ждем случайное время
                time.sleep(random.uniform(3, 7))

        except Exception as e:
            logger.debug("Error changing navigation strategy: %s", e)

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
                "antibot captcha",
                "confirm that you're not a bot",
                "slide the slider",
                "капча",
                "captcha"
            ]

            page_source = self.driver.page_source.lower()

            # Также проверяем заголовок
            title = self.driver.title.lower()

            for indicator in blocked_indicators:
                if indicator in page_source or indicator in title:
                    logger.warning("Anti-bot indicator detected: %r", indicator)
                    return True

            return False

        except Exception:
            return True

    def wait_for_json_response(self, timeout: int = 30) -> Optional[str]:
        if not self.driver:
            return None

        try:
            start_time = time.time()

            # Используем ожидание с рандомизацией
            wait_time = random.uniform(0.5, 1.5)
            time.sleep(wait_time)

            # Ждём полной загрузки страницы
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

                    # Рандомизированная задержка
                    time.sleep(random.uniform(0.3, 0.8))

                except Exception as e:
                    logger.debug(f"Error checking page source: {e}")
                    time.sleep(random.uniform(0.5, 1.0))
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

            # Сначала ищем JSON в script тегах
            script_pattern = r'<script[^>]*>\s*window\.__APP_STATE__\s*=\s*(\{.*?\})\s*</script>'
            script_match = re.search(script_pattern, html_content, re.DOTALL | re.IGNORECASE)

            if script_match:
                json_content = script_match.group(1).strip()
                logger.debug("Found JSON in window.__APP_STATE__")
                return json_content

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
            logger.error(f"Error extracting JSON from HTML: %s", e)
            return None

    def _find_chrome_binary(self) -> Optional[str]:
        """Locate Chrome/Chromium executable."""
        env_path = settings.CHROME_BINARY
        if env_path and os.path.isfile(env_path):
            return env_path

        candidates = ["google-chrome", "chromium", "chromium-browser", "chrome"]
        for name in candidates:
            path = shutil.which(name)
            if path:
                return path

        return None

    def check_proxy_alive(self, proxy: ProxyInfo, timeout: int = 10) -> bool:
        import requests

        proxy_url = f"http://{proxy.login}:{proxy.password}@{proxy.host}:{proxy.port}"
        proxies = {
            "http": proxy_url,
            "https": proxy_url,
        }

        try:
            resp = requests.get(
                "https://www.ozon.ru/",
                proxies=proxies,
                timeout=timeout,
                allow_redirects=False,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
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
            return False

    def close(self):
        """Close driver and cleanup"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Driver closed successfully")
            except Exception as e:
                logger.error(f"Error closing driver: %s", e)
            finally:
                self.driver = None
                self.wait = None

        # Чистим временную директорию расширения
        if self._proxy_ext_dir:
            try:
                shutil.rmtree(self._proxy_ext_dir, ignore_errors=True)
                logger.info("Proxy extension directory %s removed", self._proxy_ext_dir)
            except Exception as e:
                logger.error("Error removing proxy extension directory %s: %s",
                             self._proxy_ext_dir, e)
            finally:
                self._proxy_ext_dir = None

        # Чистим профиль
        if self._profile_path and os.path.exists(self._profile_path):
            try:
                shutil.rmtree(self._profile_path, ignore_errors=True)
                logger.info("Profile directory %s removed", self._profile_path)
            except Exception as e:
                logger.debug("Error removing profile directory %s: %s", self._profile_path, e)
            finally:
                self._profile_path = None