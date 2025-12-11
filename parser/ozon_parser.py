import json
import logging
import time
import random
import concurrent.futures
from typing import List, Optional
# Замените импорт SeleniumManager на PlaywrightManager
from driver_manager.playwright_manager import PlaywrightManager
from models.schemas import ArticleResult, PriceInfo, SellerInfo
from utils.helpers import (
    build_ozon_api_url,
    find_web_price_property,
    find_product_title,
    find_seller_name,
    parse_price_data,
    is_valid_json_response
)
from config.settings import settings

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

            logger.info(f"Worker {i + 1}: {len(worker_group)} articles")
            start_idx = end_idx

        return worker_groups

    def _parse_with_single_worker(self, articles: List[int]) -> List[ArticleResult]:
        worker = OzonWorker()
        try:
            worker.initialize()
            return worker.parse_articles(articles)
        finally:
            worker.close()

    def _parse_with_multiple_workers(self, worker_groups: List[List[int]], original_articles: List[int]) -> List[
        ArticleResult]:
        start_time = time.time()

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(worker_groups)) as executor:
            # Запускаем все воркеры параллельно
            futures = []
            for i, group in enumerate(worker_groups):
                future = executor.submit(self._parse_worker_group, group, i + 1)
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

    def _sort_results_by_original_order(self, results: List[ArticleResult], original_articles: List[int]) -> List[
        ArticleResult]:
        result_dict = {result.article: result for result in results}
        return [result_dict[article] for article in original_articles if article in result_dict]

    def close(self):
        logger.info("Parser closed successfully")


class OzonWorker:
    def __init__(self, worker_id: int = 1):
        self.worker_id = worker_id
        self.playwright_manager = PlaywrightManager()  # Используем Playwright вместо Selenium
        self.page = None

    def initialize(self):
        try:
            self.page = self.playwright_manager.setup_driver()

            # Прогрев: заходим на Ozon
            self.warm_up_ozon()

            logger.info(f"Worker {self.worker_id} initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize worker {self.worker_id}: {e}")
            raise

    def warm_up_ozon(self):
        """Прогрев Ozon"""
        try:
            success = self.playwright_manager.navigate_to_url(settings.OZON_BASE_URL)
            if success:
                time.sleep(random.uniform(3, 5))
                logger.info(f"Worker {self.worker_id}: Ozon warmed up")
            else:
                logger.warning(f"Worker {self.worker_id}: Failed to warm up Ozon")
        except Exception as e:
            logger.debug(f"Worker {self.worker_id}: Error warming up: {e}")

    def parse_articles(self, articles: List[int]) -> List[ArticleResult]:
        if not self.page:
            raise RuntimeError(f"Worker {self.worker_id} not initialized")

        results = []
        start_time = time.time()

        for i, article in enumerate(articles, 1):
            article_start = time.time()
            result = self.parse_article(article)
            results.append(result)

            article_time = time.time() - article_start
            elapsed_total = time.time() - start_time
            avg_time = elapsed_total / i

            logger.info(f"Worker {self.worker_id}: {i}/{len(articles)} articles, "
                        f"current: {article_time:.1f}s, avg: {avg_time:.1f}s")

            # Пауза между артикулами
            if i < len(articles):
                time.sleep(random.uniform(1.0, 2.5))

        total_time = time.time() - start_time
        logger.info(f"Worker {self.worker_id} completed in {total_time:.1f}s")

        return results

    def parse_article(self, article: int, max_retries: int = 2) -> ArticleResult:
        """Парсинг одного артикула"""
        for attempt in range(max_retries):
            try:
                api_url = build_ozon_api_url(article)

                # 1. Открываем карточку товара
                product_url = f"{settings.OZON_BASE_URL}/product/{article}/"
                success = self.playwright_manager.navigate_to_url(product_url)

                if not success:
                    if attempt < max_retries - 1:
                        time.sleep(random.uniform(2, 4))
                        continue
                    return ArticleResult(article=article, success=False,
                                         error="Failed to navigate to product page")

                time.sleep(random.uniform(2, 3))

                # 2. Открываем API URL
                success = self.playwright_manager.navigate_to_url(api_url)

                if not success:
                    if attempt < max_retries - 1:
                        time.sleep(random.uniform(2, 4))
                        continue
                    return ArticleResult(article=article, success=False,
                                         error="Failed to navigate to API")

                # 3. Ждем JSON
                json_content = self.playwright_manager.wait_for_json_response(timeout=20)

                if not json_content:
                    if attempt < max_retries - 1:
                        time.sleep(random.uniform(2, 4))
                        continue
                    return ArticleResult(article=article, success=False,
                                         error="No JSON response")

                # 4. Извлекаем данные
                result = self.extract_price_info(json_content, article)

                if result and result.success:
                    return result
                elif attempt < max_retries - 1:
                    time.sleep(random.uniform(2, 4))
                    continue
                else:
                    return ArticleResult(article=article, success=False,
                                         error="Failed to extract price info")

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.debug(f"Retry {attempt + 1} for article {article}: {e}")
                    time.sleep(random.uniform(3, 6))
                    continue
                return ArticleResult(article=article, success=False, error=str(e))

        return ArticleResult(article=article, success=False, error="Max retries exceeded")

    def extract_price_info(self, json_content: str, article: int) -> Optional[ArticleResult]:
        try:
            if not is_valid_json_response(json_content):
                return None

            data = json.loads(json_content)
            widget_states = data.get('widgetStates', {})

            if not widget_states:
                return None

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
        if self.playwright_manager:
            self.playwright_manager.close()
        logger.info(f"Worker {self.worker_id} closed successfully")