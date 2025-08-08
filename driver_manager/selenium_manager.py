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
import undetected_chromedriver as uc

logger = logging.getLogger(__name__)


class SeleniumManager:
    def __init__(self):
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None


    def setup_driver(self) -> uc.Chrome:
        chrome_options = Options()

        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
        ]
        chrome_options.add_argument(f"--user-agent={random.choice(user_agents)}")

        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--allow-running-insecure-content")
        chrome_options.add_argument("--disable-features=IsolateOrigins,site-per-process")
        chrome_options.add_argument("--disable-features=BlockInsecurePrivateNetworkRequests")


        # Performance options
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--blink-settings=imagesEnabled=false")

        chrome_options.add_argument("--window-size=1920,1080")

        try:
            driver = uc.Chrome(
                options=chrome_options,
                version_main=138,
                headless=False
            )

            driver.implicitly_wait(settings.IMPLICIT_WAIT)
            driver.set_page_load_timeout(settings.PAGE_LOAD_TIMEOUT)

            driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            self.driver = driver
            self.wait = WebDriverWait(driver, settings.IMPLICIT_WAIT)

            logger.info("Undetected Chrome driver setup successfully")
            return driver

        except WebDriverException as e:
            logger.error(f"Failed to setup undetected Chrome driver: {e}")
            raise

    
    def navigate_to_url(self, url: str) -> bool:
        if not self.driver:
            logger.error("Driver not initialized")
            return False
        
        try:
            logger.info(f"Navigating to: {url}")
            self.driver.get(url)
            
            time.sleep(random.uniform(1.0, 2.0))
            
            if self.is_blocked():
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
            
            WebDriverWait(self.driver, 10).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            
            while time.time() - start_time < timeout:
                try:
                    page_source = self.driver.page_source
                    json_content = self.extract_json_from_html(page_source)
                    
                    if json_content:
                        try:
                            data = json.loads(json_content)
                            if 'widgetStates' in data:
                                logger.info("JSON response with widgetStates found")
                                return json_content
                        except json.JSONDecodeError:
                            pass
                    
                    time.sleep(0.5)
                    
                except Exception as e:
                    logger.debug(f"Error checking page source: {e}")
                    time.sleep(0.5)
                    continue
            
            logger.warning(f"Timeout waiting for JSON response after {timeout} seconds")
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