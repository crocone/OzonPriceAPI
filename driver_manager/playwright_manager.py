# playwright_sync_manager.py
import logging
import random
import tempfile
import os
import time
import json
import re
from typing import Optional
from playwright.sync_api import sync_playwright, Browser, Page, BrowserContext
from config.settings import settings
from utils.proxy_manager import proxy_manager, ProxyInfo
import shutil

logger = logging.getLogger(__name__)


class PlaywrightSyncManager:
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.proxy: Optional[ProxyInfo] = None
        self._proxy_auth_dir: Optional[str] = None
        self._user_data_dir: Optional[str] = None
        self.playwright = None

    def get_random_user_agent(self) -> str:
        """Возвращает случайный User-Agent"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
        ]
        return random.choice(user_agents)

    def create_proxy_auth_extension(self, proxy: ProxyInfo) -> str:
        """Создает расширение для прокси с авторизацией"""
        manifest_json = {
            "version": "1.0.0",
            "manifest_version": 2,
            "name": "Proxy Auth Helper",
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

        temp_dir = tempfile.mkdtemp(prefix="proxy_ext_")

        with open(os.path.join(temp_dir, "manifest.json"), "w", encoding="utf-8") as f:
            f.write(json.dumps(manifest_json, indent=2))

        with open(os.path.join(temp_dir, "background.js"), "w", encoding="utf-8") as f:
            f.write(background_js)

        self._proxy_auth_dir = temp_dir
        logger.info(f"Created proxy auth extension at {temp_dir}")
        return temp_dir

    def setup_driver(self):
        """Синхронно настраивает и запускает браузер"""
        try:
            self.playwright = sync_playwright().start()

            # Базовые опции запуска
            launch_options = {
                "headless": settings.HEADLESS,
                "args": [
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    f"--window-size={random.randint(1200, 1920)},{random.randint(800, 1080)}",
                ]
            }

            # Выбираем прокси
            self.proxy = proxy_manager.get_random_proxy()

            if self.proxy:
                # Создаем расширение для прокси
                proxy_extension = self.create_proxy_auth_extension(self.proxy)
                launch_options["args"].extend([
                    f"--disable-extensions-except={proxy_extension}",
                    f"--load-extension={proxy_extension}"
                ])
                logger.info(f"Using proxy: {self.proxy.host}:{self.proxy.port}")

            # User-Agent
            user_agent = self.get_random_user_agent()
            launch_options["args"].append(f"--user-agent={user_agent}")

            # Профиль пользователя
            self._user_data_dir = tempfile.mkdtemp(prefix="playwright_profile_")
            launch_options["args"].append(f"--user-data-dir={self._user_data_dir}")

            # Запускаем браузер
            self.browser = self.playwright.chromium.launch(**launch_options)

            # Создаем контекст
            self.context = self.browser.new_context(
                user_agent=user_agent,
                viewport={
                    "width": random.randint(1200, 1920),
                    "height": random.randint(800, 1080)
                },
                locale="ru-RU"
            )

            # Добавляем stealth-скрипт
            self.context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            # Создаем страницу
            self.page = self.context.new_page()

            # Устанавливаем заголовки
            self.page.set_extra_http_headers({
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
            })

            logger.info("Playwright browser setup completed successfully")

            # Проверяем IP
            self.check_ip()

            return self.page

        except Exception as e:
            logger.error(f"Failed to setup browser: {e}")
            self.close()
            raise

    def check_ip(self):
        """Проверяет внешний IP адрес"""
        try:
            self.page.goto("https://api.ipify.org?format=text", wait_until="networkidle")
            ip = self.page.text_content("body")
            logger.info(f"Current IP: {ip.strip()}")
        except Exception as e:
            logger.warning(f"Could not check IP: {e}")

    def navigate_to_url(self, url: str, max_retries: int = 2) -> bool:
        """Переходит по URL с повторными попытками"""
        for attempt in range(max_retries):
            try:
                logger.info(f"Navigating to {url} (attempt {attempt + 1}/{max_retries})")

                if attempt > 0:
                    time.sleep(random.uniform(2, 4))

                self.page.goto(url, wait_until="networkidle", timeout=30000)

                # Проверяем на блокировку
                if self.is_blocked():
                    logger.warning(f"Page appears to be blocked (attempt {attempt + 1})")

                    if attempt < max_retries - 1:
                        # Очищаем куки и пробуем снова
                        self.context.clear_cookies()
                        time.sleep(random.uniform(2, 4))
                        continue
                    return False

                logger.info(f"Successfully navigated to {url}")
                return True

            except Exception as e:
                logger.error(f"Navigation error (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(random.uniform(3, 5))
                    continue
                return False

        return False

    def is_blocked(self) -> bool:
        """Проверяет, заблокирован ли доступ"""
        try:
            content = self.page.content().lower()
            title = self.page.title().lower()

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
            ]

            for indicator in blocked_indicators:
                if indicator in content or indicator in title:
                    logger.warning(f"Blocked indicator found: {indicator}")
                    return True

            return False

        except Exception as e:
            logger.error(f"Error checking if blocked: {e}")
            return True

    def wait_for_json_response(self, timeout: int = 20) -> Optional[str]:
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

            if self.context:
                self.context.close()

            if self.browser:
                self.browser.close()

            if self.playwright:
                self.playwright.stop()

            # Чистим временные файлы
            if self._proxy_auth_dir and os.path.exists(self._proxy_auth_dir):
                shutil.rmtree(self._proxy_auth_dir, ignore_errors=True)

            if self._user_data_dir and os.path.exists(self._user_data_dir):
                shutil.rmtree(self._user_data_dir, ignore_errors=True)

            logger.info("Playwright browser closed successfully")

        except Exception as e:
            logger.error(f"Error closing browser: {e}")