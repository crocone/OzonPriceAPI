import logging
import random
import tempfile
import os
from typing import Optional
from playwright.sync_api import sync_playwright, Browser, Page, BrowserContext
from config.settings import settings
from utils.proxy_manager import proxy_manager, ProxyInfo
import zipfile
import json

logger = logging.getLogger(__name__)


class SyncPlaywrightManager:
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.proxy: Optional[ProxyInfo] = None
        self._proxy_auth_zip: Optional[str] = None
        self._user_data_dir: Optional[str] = None
        self.playwright = None

    def get_random_user_agent(self) -> str:
        """Возвращает случайный User-Agent"""
        user_agents = [
            # Desktop
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
            # Mobile
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
            "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
        ]
        return random.choice(user_agents)

    def create_proxy_extension(self, proxy: ProxyInfo) -> str:
        """Создает расширение для прокси с авторизацией"""
        manifest_json = {
            "version": "1.0.0",
            "manifest_version": 2,
            "name": "Proxy Auth Extension",
            "permissions": ["proxy", "webRequest", "webRequestBlocking", "<all_urls>"],
            "background": {
                "scripts": ["background.js"]
            }
        }

        background_js = f"""
        var config = {{
            mode: "fixed_servers",
            rules: {{
                singleProxy: {{
                    scheme: "http",
                    host: "{proxy.host}",
                    port: {proxy.port}
                }}
            }}
        }};

        chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});

        chrome.webRequest.onAuthRequired.addListener(
            function(details) {{
                return {{
                    authCredentials: {{
                        username: "{proxy.login}",
                        password: "{proxy.password}"
                    }}
                }};
            }},
            {{urls: ["<all_urls>"]}},
            ["blocking"]
        );
        """

        # Создаем временную директорию для расширения
        temp_dir = tempfile.mkdtemp(prefix="proxy_ext_")
        extension_path = os.path.join(temp_dir, "proxy_auth.zip")

        with zipfile.ZipFile(extension_path, 'w') as zp:
            zp.writestr("manifest.json", json.dumps(manifest_json, indent=2))
            zp.writestr("background.js", background_js)

        self._proxy_auth_zip = extension_path
        return extension_path

    def setup_driver(self):
        """Настраивает и запускает браузер"""
        self.playwright = sync_playwright().start()

        # Настройка параметров запуска
        launch_options = {
            "headless": settings.HEADLESS,
            "args": [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                f"--window-size={random.randint(1200, 1920)},{random.randint(800, 1080)}",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-site-isolation-trials",
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
                "--disable-backgrounding-occluded-windows",
                "--disable-ipc-flooding-protection",
                "--disable-hang-monitor",
                "--disable-popup-blocking",
                "--disable-prompt-on-repost",
                "--disable-client-side-phishing-detection",
                "--disable-component-update",
                "--disable-default-apps",
                "--disable-domain-reliability",
                "--disable-sync",
                "--disable-breakpad",
                "--password-store=basic",
                "--use-mock-keychain",
                "--disable-infobars",
                "--lang=ru-RU,ru"
            ]
        }

        # Выбираем прокси
        self.proxy = proxy_manager.get_random_proxy()
        proxy_extension = None

        if self.proxy:
            # Создаем расширение для прокси
            proxy_extension = self.create_proxy_extension(self.proxy)
            launch_options["args"].append(f"--disable-extensions-except={proxy_extension}")
            launch_options["args"].append(f"--load-extension={proxy_extension}")
            logger.info(f"Using proxy: {self.proxy.host}:{self.proxy.port}")

        # User-Agent
        user_agent = self.get_random_user_agent()
        launch_options["args"].append(f"--user-agent={user_agent}")

        # Профиль пользователя
        self._user_data_dir = tempfile.mkdtemp(prefix="playwright_profile_")
        launch_options["args"].append(f"--user-data-dir={self._user_data_dir}")

        try:
            # Запускаем браузер
            self.browser = self.playwright.chromium.launch(**launch_options)

            # Создаем контекст с дополнительными настройками
            context_options = {
                "user_agent": user_agent,
                "viewport": {
                    "width": random.randint(1200, 1920),
                    "height": random.randint(800, 1080)
                },
                "locale": "ru-RU",
                "timezone_id": "Europe/Moscow",
                "permissions": ["geolocation"],
                "geolocation": {
                    "latitude": random.uniform(55.0, 56.0),
                    "longitude": random.uniform(37.0, 38.0)
                }
            }

            self.context = self.browser.new_context(**context_options)

            # Добавляем дополнительные заголовки
            self.context.add_init_script("""
                // Удаляем webdriver свойство
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });

                // Патчим plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });

                // Патчим languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['ru-RU', 'ru', 'en-US', 'en']
                });

                // Патчим permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """)

            # Создаем страницу
            self.page = self.context.new_page()

            # Устанавливаем дополнительные заголовки
            self.page.set_extra_http_headers({
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
                "Cache-Control": "max-age=0"
            })

            # Включаем JavaScript
            self.page.route("**/*", self.block_undesired_resources)

            logger.info("Playwright browser setup completed successfully")

            # Проверяем IP
            self.check_ip()

            return self.page

        except Exception as e:
            logger.error(f"Failed to setup browser: {e}")
            self.close()
            raise

    def block_undesired_resources(self, route):
        """Блокирует нежелательные ресурсы для ускорения загрузки"""
        resource_type = route.request.resource_type
        if resource_type in ["image", "media", "font", "stylesheet"]:
            route.abort()
        else:
            route.continue_()

    def check_ip(self):
        """Проверяет внешний IP адрес"""
        try:
            self.page.goto("https://api.ipify.org?format=text", wait_until="networkidle")
            ip = self.page.text_content("body")
            logger.info(f"Current IP: {ip.strip()}")
        except Exception as e:
            logger.warning(f"Could not check IP: {e}")

    def navigate_to_url(self, url: str, max_retries: int = 3) -> bool:
        """Переходит по URL с повторными попытками"""
        for attempt in range(max_retries):
            try:
                logger.info(f"Navigating to {url} (attempt {attempt + 1}/{max_retries})")

                # Имитируем человеческую задержку
                if attempt > 0:
                    import time
                    time.sleep(random.uniform(2, 5))

                # Переходим по URL
                self.page.goto(
                    url,
                    wait_until="networkidle",
                    timeout=30000
                )

                # Имитируем человеческое поведение
                self.simulate_human_behavior()

                # Проверяем на блокировку
                if self.is_blocked():
                    logger.warning(f"Page appears to be blocked (attempt {attempt + 1})")

                    if attempt < max_retries - 1:
                        # Меняем стратегию
                        self.change_strategy()
                        continue
                    return False

                logger.info(f"Successfully navigated to {url}")
                return True

            except Exception as e:
                logger.error(f"Navigation error (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(random.uniform(3, 7))
                    continue
                return False

        return False

    def simulate_human_behavior(self):
        """Имитирует человеческое поведение"""
        try:
            # Случайный скроллинг
            scroll_amount = random.randint(200, 800)
            self.page.mouse.wheel(0, scroll_amount)
            time.sleep(random.uniform(0.5, 1.5))

            # Небольшой обратный скроллинг
            self.page.mouse.wheel(0, -random.randint(50, 200))
            time.sleep(random.uniform(0.3, 0.8))

            # Случайные движения мыши
            for _ in range(random.randint(2, 4)):
                x = random.randint(100, 500)
                y = random.randint(100, 400)
                self.page.mouse.move(x, y)
                time.sleep(random.uniform(0.1, 0.3))

            # Случайный клик
            if random.random() > 0.7:
                self.page.mouse.click(
                    random.randint(100, 500),
                    random.randint(100, 400),
                    delay=random.randint(100, 300)
                )
                time.sleep(random.uniform(0.5, 1.0))

        except Exception as e:
            logger.debug(f"Error simulating human behavior: {e}")

    def change_strategy(self):
        """Изменяет стратегию при обнаружении блокировки"""
        try:
            # Очищаем куки
            self.context.clear_cookies()

            # Меняем User-Agent
            new_ua = self.get_random_user_agent()
            self.context.set_extra_http_headers({"User-Agent": new_ua})

            # Перезагружаем страницу
            self.page.reload()
            time.sleep(random.uniform(2, 4))

        except Exception as e:
            logger.debug(f"Error changing strategy: {e}")

    def is_blocked(self) -> bool:
        """Проверяет, заблокирован ли доступ"""
        try:
            content = self.page.content()
            title = self.page.title()

            content_lower = content.lower()
            title_lower = title.lower()

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

            for indicator in blocked_indicators:
                if indicator in content_lower or indicator in title_lower:
                    logger.warning(f"Blocked indicator found: {indicator}")
                    return True

            return False

        except Exception as e:
            logger.error(f"Error checking if blocked: {e}")
            return True

    def wait_for_json_response(self, timeout: int = 30) -> Optional[str]:
        """Ждет JSON ответ"""
        try:
            start_time = time.time()

            while time.time() - start_time < timeout:
                content = self.page.content()

                # Пытаемся извлечь JSON
                json_content = self.extract_json_from_html(content)
                if json_content:
                    try:
                        data = json.loads(json_content)
                        if "widgetStates" in data:
                            logger.info("Found JSON with widgetStates")
                            return json_content
                    except json.JSONDecodeError:
                        pass

                # Проверяем, не появился ли JSON в теле страницы
                body_text = self.page.text_content("body")
                if body_text and body_text.strip().startswith("{"):
                    logger.info("Found JSON directly in body")
                    return body_text.strip()

                time.sleep(random.uniform(0.5, 1.0))

            logger.warning(f"Timeout waiting for JSON response after {timeout} seconds")
            return None

        except Exception as e:
            logger.error(f"Error waiting for JSON response: {e}")
            return None

    def extract_json_from_html(self, html_content: str) -> Optional[str]:
        """Извлекает JSON из HTML"""
        try:
            import re

            # Ищем в script тегах
            script_pattern = r'<script[^>]*>\s*window\.__APP_STATE__\s*=\s*(\{.*?\})\s*</script>'
            script_match = re.search(script_pattern, html_content, re.DOTALL | re.IGNORECASE)

            if script_match:
                return script_match.group(1).strip()

            # Ищем в pre тегах
            pre_pattern = r'<pre[^>]*>(.*?)</pre>'
            pre_match = re.search(pre_pattern, html_content, re.DOTALL | re.IGNORECASE)

            if pre_match:
                return pre_match.group(1).strip()

            # Ищем JSON напрямую
            first_brace = html_content.find('{')
            last_brace = html_content.rfind('}')

            if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
                return html_content[first_brace:last_brace + 1]

            return None

        except Exception as e:
            logger.error(f"Error extracting JSON: {e}")
            return None

    def close(self):
        """Закрывает браузер и чистит ресурсы"""
        try:
            if self.page:
                self.page.close()
                self.page = None

            if self.context:
                self.context.close()
                self.context = None

            if self.browser:
                self.browser.close()
                self.browser = None

            if self.playwright:
                self.playwright.stop()
                self.playwright = None

            # Чистим временные файлы
            if self._proxy_auth_zip and os.path.exists(self._proxy_auth_zip):
                os.remove(self._proxy_auth_zip)

            if self._user_data_dir and os.path.exists(self._user_data_dir):
                import shutil
                shutil.rmtree(self._user_data_dir, ignore_errors=True)

            logger.info("Playwright browser closed successfully")

        except Exception as e:
            logger.error(f"Error closing browser: {e}")