import logging
import random
import tempfile
import os
import asyncio
import json
import re
from typing import Optional
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from config.settings import settings
from utils.proxy_manager import proxy_manager, ProxyInfo
import shutil

logger = logging.getLogger(__name__)


class AsyncPlaywrightManager:
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
            "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
        ]
        return random.choice(user_agents)

    def create_proxy_auth_extension(self, proxy: ProxyInfo) -> str:
        """Создает расширение для прокси с авторизацией"""
        import json

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

        # Создаем временную директорию для расширения
        temp_dir = tempfile.mkdtemp(prefix="proxy_ext_")

        with open(os.path.join(temp_dir, "manifest.json"), "w", encoding="utf-8") as f:
            f.write(json.dumps(manifest_json, indent=2))

        with open(os.path.join(temp_dir, "background.js"), "w", encoding="utf-8") as f:
            f.write(background_js)

        self._proxy_auth_dir = temp_dir
        logger.info(f"Created proxy auth extension at {temp_dir}")
        return temp_dir

    async def setup_driver(self):
        """Асинхронно настраивает и запускает браузер"""
        try:
            self.playwright = await async_playwright().start()

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
                    "--lang=ru-RU,ru"
                ]
            }

            # Выбираем прокси
            self.proxy = proxy_manager.get_random_proxy()

            if self.proxy:
                # Создаем расширение для прокси
                proxy_extension = self.create_proxy_auth_extension(self.proxy)
                launch_options["args"].append(f"--disable-extensions-except={proxy_extension}")
                launch_options["args"].append(f"--load-extension={proxy_extension}")
                logger.info(f"Using proxy: {self.proxy.host}:{self.proxy.port}")

            # User-Agent
            user_agent = self.get_random_user_agent()
            launch_options["args"].append(f"--user-agent={user_agent}")

            # Профиль пользователя
            self._user_data_dir = tempfile.mkdtemp(prefix="playwright_profile_")
            launch_options["args"].append(f"--user-data-dir={self._user_data_dir}")

            # Запускаем браузер
            self.browser = await self.playwright.chromium.launch(**launch_options)

            # Создаем контекст с дополнительными настройками
            context_options = {
                "user_agent": user_agent,
                "viewport": {
                    "width": random.randint(1200, 1920),
                    "height": random.randint(800, 1080)
                },
                "locale": "ru-RU",
                "timezone_id": "Europe/Moscow"
            }

            self.context = await self.browser.new_context(**context_options)

            # Добавляем дополнительные заголовки
            await self.context.add_init_script("""
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
            """)

            # Создаем страницу
            self.page = await self.context.new_page()

            # Устанавливаем дополнительные заголовки
            await self.page.set_extra_http_headers({
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1"
            })

            logger.info("Playwright browser setup completed successfully")

            # Проверяем IP
            await self.check_ip()

            return self.page

        except Exception as e:
            logger.error(f"Failed to setup browser: {e}")
            await self.close()
            raise

    async def check_ip(self):
        """Проверяет внешний IP адрес"""
        try:
            await self.page.goto("https://api.ipify.org?format=text", wait_until="networkidle")
            ip = await self.page.text_content("body")
            logger.info(f"Current IP: {ip.strip()}")
        except Exception as e:
            logger.warning(f"Could not check IP: {e}")

    async def navigate_to_url(self, url: str, max_retries: int = 3) -> bool:
        """Асинхронно переходит по URL с повторными попытками"""
        for attempt in range(max_retries):
            try:
                logger.info(f"Navigating to {url} (attempt {attempt + 1}/{max_retries})")

                # Имитируем человеческую задержку
                if attempt > 0:
                    await asyncio.sleep(random.uniform(2, 5))

                # Переходим по URL
                await self.page.goto(
                    url,
                    wait_until="networkidle",
                    timeout=30000
                )

                # Имитируем человеческое поведение
                await self.simulate_human_behavior()

                # Проверяем на блокировку
                if await self.is_blocked():
                    logger.warning(f"Page appears to be blocked (attempt {attempt + 1})")

                    if attempt < max_retries - 1:
                        # Меняем стратегию
                        await self.change_strategy()
                        continue
                    return False

                logger.info(f"Successfully navigated to {url}")
                return True

            except Exception as e:
                logger.error(f"Navigation error (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(random.uniform(3, 7))
                    continue
                return False

        return False

    async def simulate_human_behavior(self):
        """Имитирует человеческое поведение"""
        try:
            # Случайный скроллинг
            scroll_amount = random.randint(200, 800)
            await self.page.mouse.wheel(0, scroll_amount)
            await asyncio.sleep(random.uniform(0.5, 1.5))

            # Небольшой обратный скроллинг
            await self.page.mouse.wheel(0, -random.randint(50, 200))
            await asyncio.sleep(random.uniform(0.3, 0.8))

            # Случайные движения мыши
            for _ in range(random.randint(2, 4)):
                x = random.randint(100, 500)
                y = random.randint(100, 400)
                await self.page.mouse.move(x, y)
                await asyncio.sleep(random.uniform(0.1, 0.3))

        except Exception as e:
            logger.debug(f"Error simulating human behavior: {e}")

    async def change_strategy(self):
        """Изменяет стратегию при обнаружении блокировки"""
        try:
            # Очищаем куки
            await self.context.clear_cookies()

            # Меняем User-Agent
            new_ua = self.get_random_user_agent()
            await self.context.set_extra_http_headers({"User-Agent": new_ua})

            # Перезагружаем страницу
            await self.page.reload()
            await asyncio.sleep(random.uniform(2, 4))

        except Exception as e:
            logger.debug(f"Error changing strategy: {e}")

    async def is_blocked(self) -> bool:
        """Проверяет, заблокирован ли доступ"""
        try:
            content = await self.page.content()
            title = await self.page.title()

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

    async def wait_for_json_response(self, timeout: int = 30) -> Optional[str]:
        """Асинхронно ждет JSON ответ"""
        try:
            start_time = asyncio.get_event_loop().time()

            while asyncio.get_event_loop().time() - start_time < timeout:
                content = await self.page.content()

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
                body_text = await self.page.text_content("body")
                if body_text and body_text.strip().startswith("{"):
                    logger.info("Found JSON directly in body")
                    return body_text.strip()

                await asyncio.sleep(random.uniform(0.5, 1.0))

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

    async def close(self):
        """Асинхронно закрывает браузер и чистит ресурсы"""
        try:
            if self.page:
                await self.page.close()
                self.page = None

            if self.context:
                await self.context.close()
                self.context = None

            if self.browser:
                await self.browser.close()
                self.browser = None

            if self.playwright:
                await self.playwright.stop()
                self.playwright = None

            # Чистим временные файлы
            if self._proxy_auth_dir and os.path.exists(self._proxy_auth_dir):
                shutil.rmtree(self._proxy_auth_dir, ignore_errors=True)

            if self._user_data_dir and os.path.exists(self._user_data_dir):
                shutil.rmtree(self._user_data_dir, ignore_errors=True)

            logger.info("Playwright browser closed successfully")

        except Exception as e:
            logger.error(f"Error closing browser: {e}")


# Синхронная обертка для совместимости
class SyncPlaywrightWrapper:
    """Обертка для использования асинхронного Playwright в синхронном коде"""

    def __init__(self):
        self.manager = AsyncPlaywrightManager()
        self.loop = None

    def setup_driver(self):
        """Синхронная обертка для setup_driver"""
        if self.loop and not self.loop.is_closed():
            self.loop.close()

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        try:
            return self.loop.run_until_complete(self.manager.setup_driver())
        except Exception as e:
            self.loop.run_until_complete(self.manager.close())
            raise

    def navigate_to_url(self, url: str, max_retries: int = 3) -> bool:
        """Синхронная обертка для navigate_to_url"""
        if not self.loop or self.loop.is_closed():
            raise RuntimeError("Loop is closed or not initialized")

        return self.loop.run_until_complete(
            self.manager.navigate_to_url(url, max_retries)
        )

    def wait_for_json_response(self, timeout: int = 30) -> Optional[str]:
        """Синхронная обертка для wait_for_json_response"""
        if not self.loop or self.loop.is_closed():
            raise RuntimeError("Loop is closed or not initialized")

        return self.loop.run_until_complete(
            self.manager.wait_for_json_response(timeout)
        )

    def close(self):
        """Синхронная обертка для close"""
        if self.loop and not self.loop.is_closed():
            try:
                self.loop.run_until_complete(self.manager.close())
            finally:
                self.loop.close()
                self.loop = None