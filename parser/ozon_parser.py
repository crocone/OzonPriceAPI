import json
import logging
import time
import concurrent.futures
from typing import List, Optional
from driver_manager.selenium_manager import SeleniumManager
from models.schemas import ArticleResult, PriceInfo, SellerInfo
from utils.captcha_solver import OzonCaptchaSolverV3
from utils.helpers import (
    build_ozon_api_url, 
    find_web_price_property, 
    find_product_title,
    find_seller_name,
    parse_price_data,
    is_valid_json_response
)
from config.settings import settings
from selenium.webdriver.common.by import By


logger = logging.getLogger(__name__)


class OzonParser:
    def __init__(self):
        self.MAX_WORKERS = settings.MAX_WORKERS
        self.MIN_ARTICLES_PER_WORKER = settings.MAX_ARTICLES_PER_WORKER
        self.TARGET_TIME_SECONDS = 90  # 1.5 минуты
        self.ESTIMATED_TIME_PER_ARTICLE = 6  # секунд на артикул

    def initialize(self):
        logger.info("Ozon parser initialized successfully")

    def parse_articles(self, articles: List[int]) -> List[ArticleResult]:
        total_articles = len(articles)
        logger.info(f"Starting to parse {total_articles} articles with target time {self.TARGET_TIME_SECONDS}s")
        
        if total_articles <= self.MIN_ARTICLES_PER_WORKER:
            # Мало артикулов - используем один воркер
            logger.info("Using single worker for small batch")
            return self._parse_with_single_worker(articles)
        
        # Рассчитываем оптимальное количество воркеров
        worker_groups = self._calculate_optimal_workers(articles)
        logger.info(f"Using {len(worker_groups)} workers for {total_articles} articles")
        
        return self._parse_with_multiple_workers(worker_groups, articles)
    
    def _calculate_optimal_workers(self, articles: List[int]) -> List[List[int]]:
        total_articles = len(articles)
        
        # Рассчитываем сколько воркеров нужно для укладывания в 1.5 минуты
        estimated_total_time = total_articles * self.ESTIMATED_TIME_PER_ARTICLE
        needed_workers = max(1, int(estimated_total_time / self.TARGET_TIME_SECONDS))
        
        # Ограничиваем максимальным количеством воркеров
        optimal_workers = min(needed_workers, self.MAX_WORKERS)
        
        # Убеждаемся что в каждом воркере минимум 3 артикула (кроме остатка)
        if total_articles / optimal_workers < self.MIN_ARTICLES_PER_WORKER:
            optimal_workers = max(1, total_articles // self.MIN_ARTICLES_PER_WORKER)
        
        logger.info(f"Calculated optimal workers: {optimal_workers} for {total_articles} articles")
        logger.info(f"Estimated time per worker: {estimated_total_time / optimal_workers:.1f}s")
        
        # Распределяем артикулы по воркерам
        articles_per_worker = total_articles // optimal_workers
        remainder = total_articles % optimal_workers
        
        worker_groups = []
        start_idx = 0
        
        for i in range(optimal_workers):
            # Добавляем по одному дополнительному артикулу первым воркерам для остатка
            current_batch_size = articles_per_worker + (1 if i < remainder else 0)
            end_idx = start_idx + current_batch_size
            
            worker_group = articles[start_idx:end_idx]
            worker_groups.append(worker_group)
            
            logger.info(f"Worker {i+1}: {len(worker_group)} articles")
            start_idx = end_idx
        
        return worker_groups
    
    def _parse_with_single_worker(self, articles: List[int]) -> List[ArticleResult]:
        worker = OzonWorker()
        try:
            worker.initialize()
            return worker.parse_articles(articles)
        finally:
            worker.close()
    
    def _parse_with_multiple_workers(self, worker_groups: List[List[int]], original_articles: List[int]) -> List[ArticleResult]:
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(worker_groups)) as executor:
            # Запускаем все воркеры параллельно
            futures = []
            for i, group in enumerate(worker_groups):
                future = executor.submit(self._parse_worker_group, group, i+1)
                futures.append(future)
            
            # Собираем результаты по мере готовности
            all_results = []
            completed = 0
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    worker_results = future.result()
                    all_results.extend(worker_results)
                    completed += 1
                    
                    elapsed = time.time() - start_time
                    logger.info(f"Worker {completed}/{len(worker_groups)} completed in {elapsed:.1f}s")
                    
                except Exception as e:
                    logger.error(f"Worker failed: {e}")
        
        total_time = time.time() - start_time
        logger.info(f"All workers completed in {total_time:.1f}s (target: {self.TARGET_TIME_SECONDS}s)")
        
        return self._sort_results_by_original_order(all_results, original_articles)
    
    def _parse_worker_group(self, articles: List[int], worker_id: int) -> List[ArticleResult]:
        logger.info(f"Worker {worker_id} starting with {len(articles)} articles")
        worker = OzonWorker(worker_id)
        try:
            worker.initialize()
            return worker.parse_articles(articles)
        finally:
            worker.close()
    
    def _sort_results_by_original_order(self, results: List[ArticleResult], original_articles: List[int]) -> List[ArticleResult]:
        result_dict = {result.article: result for result in results}
        return [result_dict[article] for article in original_articles if article in result_dict]
    
    def close(self):
        logger.info("Parser closed successfully")


class OzonWorker:
    def __init__(self, worker_id: int = 1):
        self.worker_id = worker_id
        self.selenium_manager = SeleniumManager()
        self.driver = None
    
    def initialize(self):
        try:
            self.driver = self.selenium_manager.setup_driver()
            logger.info(f"Worker {self.worker_id} initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize worker {self.worker_id}: {e}")
            raise

    # В ozon_parser.py в методе handle_blocked_page:
    def handle_blocked_page(self, context: str = "unknown"):
        """
        Вызывается когда страница, скорее всего, заблокирована (капча / enable JS / антибот).
        """
        if not self.driver:
            logger.warning(f"Worker {self.worker_id}: no driver to handle blocked page")
            return False  # Возвращаем статус

        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"blocked_{context}_{timestamp}.png"

            # 1. Скриншот
            self.driver.save_screenshot(filename)
            logger.warning(
                f"Worker {self.worker_id}: blocked page screenshot saved to {filename} (context={context})"
            )

            # 2. Проверяем и пытаемся решить капчу
            try:
                page_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()

                if any(keyword in page_text for keyword in ['slide the', 'confirm that you', 'puzzle piece']):
                    logger.info(f"Worker {self.worker_id}: Attempting to solve slider captcha...")

                    # Пытаемся решить капчу
                    solver = OzonCaptchaSolverV3(self.driver)
                    time.sleep(2)
                    if solver.solve():
                        logger.info(f"Worker {self.worker_id}: Captcha solved successfully!")
                        return True
                    else:
                        logger.warning(f"Worker {self.worker_id}: Failed to solve captcha")

            except Exception as e:
                logger.debug(f"Worker {self.worker_id}: Error in captcha check: {e}")

            # 3. Выполняем JS — возвращаем полезную инфу о странице
            try:
                info = self.driver.execute_script(
                    """
                    return {
                        url: window.location.href,
                        ua: navigator.userAgent,
                        title: document.title
                    };
                    """
                )
                logger.warning(
                    f"Worker {self.worker_id}: blocked page info: "
                    f"url={info['url']}, title={info['title']}, ua={info['ua']}"
                )
            except Exception as e:
                logger.debug(
                    f"Worker {self.worker_id}: failed to run debug JS on blocked page: {e}"
                )

            return False  # Не удалось решить капчу

        except Exception as e:
            logger.error(f"Worker {self.worker_id}: failed to handle blocked page: {e}")
            return False

    def parse_articles(self, articles: List[int]) -> List[ArticleResult]:
        if not self.driver:
            raise RuntimeError(f"Worker {self.worker_id} not initialized")
        
        results = []
        start_time = time.time()
        
        for i, article in enumerate(articles, 1):
            article_start = time.time()
            result = self.parse_article_fast(article)
            results.append(result)
            
            article_time = time.time() - article_start
            elapsed_total = time.time() - start_time
            avg_time = elapsed_total / i
            remaining = len(articles) - i
            estimated_remaining = remaining * avg_time
            
            logger.info(f"Worker {self.worker_id}: {i}/{len(articles)} articles, "
                       f"current: {article_time:.1f}s, avg: {avg_time:.1f}s, "
                       f"ETA: {estimated_remaining:.1f}s")
        
        total_time = time.time() - start_time
        logger.info(f"Worker {self.worker_id} completed {len(articles)} articles in {total_time:.1f}s")
        
        return results

    def parse_article_fast(self, article: int) -> ArticleResult:
        """Быстрый парсинг с улучшенной обработкой капчи"""
        for attempt in range(3):  # Увеличиваем до 3 попыток
            try:
                api_url = build_ozon_api_url(article)

                # 0) Прогрев куков: сначала открываем обычную карточку товара
                product_url = f"{settings.OZON_BASE_URL}/product/{article}/"

                navigation_success = self.selenium_manager.navigate_to_url(product_url)

                if not navigation_success:
                    # Проверяем, точно ли это капча
                    time.sleep(2)  # Даем время для загрузки

                    if self.is_captcha_present():
                        logger.info(f"Captcha detected, attempting to solve...")
                        if self.solve_captcha():
                            logger.info("Captcha solved successfully")
                            # После решения капчи продолжаем
                            time.sleep(2)
                            # Пробуем перейти снова
                            navigation_success = self.selenium_manager.navigate_to_url(product_url)
                            if not navigation_success:
                                if attempt < 2:
                                    continue
                                return ArticleResult(article=article, success=False,
                                                     error="Navigation failed after captcha")
                        else:
                            logger.warning("Failed to solve captcha")
                            if attempt < 2:
                                # Пробуем обновить страницу и повторить
                                self.driver.refresh()
                                time.sleep(3)
                                continue
                            return ArticleResult(article=article, success=False,
                                                 error="Captcha solving failed")
                    else:
                        # Не капча, а другая ошибка
                        self.handle_blocked_page(context=f"product_{article}_attempt_{attempt + 1}")
                        if attempt < 2:
                            time.sleep(1)
                            continue
                        return ArticleResult(article=article, success=False,
                                             error="Navigation to product page failed")

                time.sleep(2)  # даём озону поставить куки/сессию

                # 1) Теперь идём в composer-api
                navigation_success = self.selenium_manager.navigate_to_url(api_url)

                if not navigation_success:
                    # Аналогичная обработка для API страницы
                    time.sleep(2)

                    if self.is_captcha_present():
                        logger.info(f"Captcha detected on API page, attempting to solve...")
                        if self.solve_captcha():
                            logger.info("Captcha solved on API page")
                            time.sleep(2)
                            navigation_success = self.selenium_manager.navigate_to_url(api_url)
                            if not navigation_success:
                                if attempt < 2:
                                    continue
                                return ArticleResult(article=article, success=False,
                                                     error="Navigation to API failed after captcha")
                        else:
                            logger.warning("Failed to solve captcha on API page")
                            if attempt < 2:
                                self.driver.refresh()
                                time.sleep(3)
                                continue
                    else:
                        self.handle_blocked_page(context=f"api_{article}_attempt_{attempt + 1}")
                        if attempt < 2:
                            continue

                # 2) Ждем JSON
                json_content = self.selenium_manager.wait_for_json_response(timeout=30)

                if not json_content:
                    if attempt < 2:
                        continue
                    return ArticleResult(article=article, success=False, error="No JSON response")

                # Парсинг данных
                result = self.extract_price_info(json_content, article)

                if result and result.success:
                    return result
                elif attempt < 2:
                    continue
                else:
                    return ArticleResult(article=article, success=False, error="JSON parsing failed")

            except Exception as e:
                self.handle_blocked_page(context=f"exception_article_{article}_attempt_{attempt + 1}")
                logger.error(f"Attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    time.sleep(1)
                    continue

        return ArticleResult(article=article, success=False, error="Max retries exceeded")

    def is_captcha_present(self):
        """Проверяет наличие капчи на странице"""
        try:
            page_text = self.driver.page_source.lower()
            captcha_indicators = [
                "confirm that you're not a bot",
                "slide the slider",
                "puzzle piece",
                "antibot captcha"
            ]

            return any(indicator in page_text for indicator in captcha_indicators)
        except:
            return False

    def solve_captcha(self):
        """Пытается решить капчу"""
        try:
            from utils.captcha_solver import OzonCaptchaSolverV3
            solver = OzonCaptchaSolverV3(self.driver)
            return solver.solve()
        except Exception as e:
            logger.error(f"Error solving captcha: {e}")
            return False
    
    def extract_price_info(self, json_content: str, article: int) -> Optional[ArticleResult]:
        try:
            if not is_valid_json_response(json_content):
                return None
            
            data = json.loads(json_content)
            widget_states = data.get('widgetStates', {})
            
            if not widget_states:
                return None
            
            # Быстрый поиск без отладки
            web_price_value = find_web_price_property(widget_states)
            if not web_price_value:
                return None
            
            try:
                price_json = json.loads(web_price_value)
                is_available = price_json.get('isAvailable', False)
                card_price = price_json.get('cardPrice')
                price = price_json.get('price')
                original_price = price_json.get('originalPrice')
                
                from utils.helpers import extract_price_from_string
                
                result = ArticleResult(
                    article=article,
                    success=True,
                    isAvailable=is_available,
                    price_info=PriceInfo(
                        cardPrice=extract_price_from_string(card_price),
                        price=extract_price_from_string(price),
                        originalPrice=extract_price_from_string(original_price)
                    )
                )
                
                # Быстрое получение дополнительных данных
                title = find_product_title(widget_states)
                if title:
                    result.title = title
                
                seller_name = find_seller_name(widget_states)
                if seller_name:
                    result.seller = SellerInfo(name=seller_name)
                
                return result
                
            except Exception:
                return None
                
        except Exception:
            return None
    
    def close(self):
        if self.selenium_manager:
            self.selenium_manager.close()
        logger.info("Worker closed successfully")