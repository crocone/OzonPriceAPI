import json
import re
import logging
from typing import Optional, Dict, Any
from models.schemas import PriceInfo, SellerInfo


logger = logging.getLogger(__name__)


def extract_price_from_string(price_str: str) -> Optional[int]:
    if not price_str:
        return None
    
    cleaned = re.sub(r'[^\d]', '', price_str)
    
    try:
        return int(cleaned) if cleaned else None
    except ValueError:
        logger.warning(f"Failed to parse price: {price_str}")
        return None


def parse_price_data(price_json_str: str) -> Optional[PriceInfo]:
    try:
        price_data = json.loads(price_json_str)
        return PriceInfo(
            cardPrice=extract_price_from_string(price_data.get('cardPrice')),
            price=extract_price_from_string(price_data.get('price')),
            originalPrice=extract_price_from_string(price_data.get('originalPrice'))
        )
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.error(f"Failed to parse price data: {e}")
        return None


def find_web_price_property(widget_states: Dict[str, Any]) -> Optional[str]:
    # Быстрый поиск без логирования
    for key, value in widget_states.items():
        if key.startswith('webPrice-') and isinstance(value, str):
            return value
    return None


def find_product_title(widget_states: Dict[str, Any]) -> Optional[str]:
    for key, value in widget_states.items():
        if key.startswith('webProductHeading-') and isinstance(value, str):
            try:
                heading_data = json.loads(value)
                title = heading_data.get('title')
                if title:
                    return title
            except (json.JSONDecodeError, KeyError):
                continue
    return None


def find_seller_name(widget_states: Dict[str, Any]) -> Optional[str]:
    for key, value in widget_states.items():
        if key.startswith('webStickyProducts-') and isinstance(value, str):
            try:
                cleaned_value = value.replace('&quot;', '"')
                sticky_data = json.loads(cleaned_value)
                if 'seller' in sticky_data and 'name' in sticky_data['seller']:
                    return sticky_data['seller']['name']
            except (json.JSONDecodeError, KeyError):
                continue
    return None


def build_ozon_api_url(article: int) -> str:
    base_url = "https://www.ozon.ru/api/composer-api.bx/page/json/v2"
    product_url = f"/product/{article}/"
    url = f"{base_url}?url={product_url}"
    return url


def is_valid_json_response(response_text: str) -> bool:
    try:
        json.loads(response_text)
        return True
    except json.JSONDecodeError:
        return False


def debug_widget_states(widget_states: Dict[str, Any]) -> None:
    logger.info(f"Total widgets: {len(widget_states)}")
    
    prefixes = {}
    for key in widget_states.keys():
        if '-' in key:
            prefix = key.split('-')[0]
            if prefix not in prefixes:
                prefixes[prefix] = []
            prefixes[prefix].append(key)
    
    for prefix, keys in prefixes.items():
        logger.info(f"Prefix '{prefix}': {len(keys)} widgets")
        if len(keys) <= 3:
            for key in keys:
                logger.info(f"  - {key}")
        else:
            for key in keys[:2]:
                logger.info(f"  - {key}")
            logger.info(f"  ... and {len(keys) - 2} more")
