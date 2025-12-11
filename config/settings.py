from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # API settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_DEBUG: bool = True
    
    # Selenium settings
    HEADLESS: bool = False
    IMPLICIT_WAIT: int = 20
    PAGE_LOAD_TIMEOUT: int = 60
    
    # Ozon settings
    OZON_BASE_URL: str = "https://www.ozon.ru"
    OZON_API_URL: str = "https://www.ozon.ru/api/composer-api.bx/page/json/v2"
    MAX_ARTICLES_PER_REQUEST: int = 150
    
    # Parser settings - оптимизировано для скорости
    MAX_RETRIES: int = 2  # Уменьшено для скорости
    RETRY_DELAY: int = 1  # Уменьшено для скорости
    REQUEST_TIMEOUT: int = 30  # Уменьшено для скорости
    
    # Worker settings - динамическое распределение
    MAX_ARTICLES_PER_WORKER: int = 30  # Увеличено
    MAX_WORKERS: int = 5  # Увеличено до 7
    
    # Browser settings
    USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"

    # Proxy settings
    ENABLE_PROXY: bool = True
    PROXY_LIST_PATH: str = "config/proxies.txt"
    CHROME_BINARY: Optional[str] = None

    class Config:
        env_file = ".env"


settings = Settings()