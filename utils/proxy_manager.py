import logging
import random
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class ProxyInfo:
    host: str
    port: str
    login: str
    password: str

    @property
    def browser_proxy(self) -> str:
        # То, что можно безопасно передавать в --proxy-server
        return f"https://{self.host}:{self.port}"



class ProxyManager:
    def __init__(self, proxy_file: str, enabled: bool = True):
        self.proxy_file = Path(proxy_file)
        self.enabled = enabled
        self._proxies: List[ProxyInfo] = []
        self._load_proxies()

    def _load_proxies(self) -> None:
        if not self.enabled:
            logger.info("Proxy usage is disabled via settings")
            return

        if not self.proxy_file.exists():
            logger.warning("Proxy file not found: %s", self.proxy_file)
            return

        try:
            with self.proxy_file.open("r", encoding="utf-8") as file:
                for line in file:
                    raw = line.strip()
                    if not raw or raw.startswith("#"):
                        continue

                    parts = raw.split(":")
                    if len(parts) != 4:
                        logger.warning("Invalid proxy format, expected host:port:login:password -> %s", raw)
                        continue

                    host, port, login, password = parts
                    proxy_info = ProxyInfo(host=host, port=port, login=login, password=password)
                    self._proxies.append(proxy_info)

            logger.info("Loaded %d proxies from %s", len(self._proxies), self.proxy_file)
        except Exception as exc:
            logger.error("Failed to load proxies: %s", exc)

    def has_proxies(self) -> bool:
        return bool(self._proxies)

    def get_random_proxy(self) -> Optional[ProxyInfo]:
        if not self._proxies:
            return None
        return random.choice(self._proxies)


proxy_manager = ProxyManager(settings.PROXY_LIST_PATH, enabled=settings.ENABLE_PROXY)
