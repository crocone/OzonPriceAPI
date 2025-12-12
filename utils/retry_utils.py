import time
import random
from functools import wraps
import logging

logger = logging.getLogger(__name__)

def retry_on_stale_element(max_retries=3, delay=1):
    """Декоратор для повторной попытки при stale element exception"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if "stale element" in str(e).lower() and attempt < max_retries - 1:
                        logger.warning(f"Stale element on attempt {attempt + 1}, retrying...")
                        time.sleep(delay * (attempt + 1) + random.random())
                        continue
                    raise
            return func(*args, **kwargs)
        return wrapper
    return decorator