import json
import logging
import time
import concurrent.futures
from typing import List, Optional
from driver_manager.selenium_manager import SeleniumManager
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
        self.workers = []
    
    def initialize(self):
        logger.info("Ozon parser initialized successfully")
    
    def parse_articles(self, articles: List[int]) -> List[ArticleResult]:
        return self._parse_with_single_worker(articles)
    
    def _distribute_articles(self, articles: List[int]) -> List[List[int]]:
        total = len(articles)
        if total <= settings.MAX_ARTICLES_PER_WORKER:
            return [articles]
        
        groups = []
        for i in range(0, total, settings.MAX_ARTICLES_PER_WORKER):
            group = articles[i:i + settings.MAX_ARTICLES_PER_WORKER]
            groups.append(group)
            if len(groups) >= settings.MAX_WORKERS:
                break
        return groups
    
    def _parse_with_single_worker(self, articles: List[int]) -> List[ArticleResult]:
        worker = OzonWorker()
        try:
            worker.initialize()
            return worker.parse_articles(articles)
        finally:
            worker.close()
    
    def _parse_with_multiple_workers(self, worker_groups: List[List[int]], original_articles: List[int]) -> List[ArticleResult]:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(worker_groups)) as executor:
            futures = [executor.submit(self._parse_worker_group, group) for group in worker_groups]
            all_results = []
            for future in concurrent.futures.as_completed(futures):
                all_results.extend(future.result())
        return self._sort_results_by_original_order(all_results, original_articles)
    
    def _parse_worker_group(self, articles: List[int]) -> List[ArticleResult]:
        worker = OzonWorker()
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
    def __init__(self):
        self.selenium_manager = SeleniumManager()
        self.driver = None
    
    def initialize(self):
        try:
            self.driver = self.selenium_manager.setup_driver()
            logger.info("Worker initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize worker: {e}")
            raise
    
    def parse_articles(self, articles: List[int]) -> List[ArticleResult]:
        if not self.driver:
            raise RuntimeError("Worker not initialized")
        
        results = []
        for article in articles:
            result = self.parse_single_article(article)
            results.append(result)
        return results
    
    def parse_single_article(self, article: int) -> ArticleResult:
        import random
        delay = random.uniform(3.0, 8.0)
        logger.info(f"Adding random delay of {delay:.2f} seconds before parsing article {article}")
        time.sleep(delay)
        
        for attempt in range(settings.MAX_RETRIES):
            try:
                logger.info(f"Parsing article {article}, attempt {attempt + 1}")
                
                api_url = build_ozon_api_url(article)
                logger.info(f"API URL: {api_url}")
                
                navigation_success = self.selenium_manager.navigate_to_url(api_url)
                logger.info(f"Navigation success: {navigation_success}")
                
                if not navigation_success:
                    logger.warning(f"Failed to navigate for article {article}")
                    if attempt < settings.MAX_RETRIES - 1:
                        time.sleep(settings.RETRY_DELAY)
                        continue
                    return ArticleResult(article=article, success=False, error="Navigation failed")
                
                json_content = self.selenium_manager.wait_for_json_response()
                
                if not json_content:
                    logger.warning(f"No JSON response for article {article}")
                    if attempt < settings.MAX_RETRIES - 1:
                        time.sleep(settings.RETRY_DELAY)
                        continue
                    return ArticleResult(article=article, success=False, error="No JSON response")
                
                logger.info(f"Got JSON response for article {article}")
                
                result = self.extract_price_info(json_content, article)
                
                if not result or not result.success:
                    logger.warning(f"Failed to parse JSON for article {article}")
                    if attempt < settings.MAX_RETRIES - 1:
                        time.sleep(settings.RETRY_DELAY)
                        continue
                    return ArticleResult(article=article, success=False, error="JSON parsing failed")
                
                logger.info(f"Successfully parsed article {article}")
                return result
                
            except Exception as e:
                logger.error(f"Error parsing article {article}: {e}")
                if attempt < settings.MAX_RETRIES - 1:
                    time.sleep(settings.RETRY_DELAY)
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
            
            logger.info(f"Found {len(widget_states)} widget states")
            
            from utils.helpers import debug_widget_states
            debug_widget_states(widget_states)
            
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
                
            except Exception as e:
                logger.error(f"Error parsing price data: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting price info: {e}")
            return None
    
    def close(self):
        if self.selenium_manager:
            self.selenium_manager.close()
        logger.info("Worker closed successfully")