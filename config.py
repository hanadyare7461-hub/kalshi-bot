from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List


def _split_csv(value: str) -> List[str]:
    return [x.strip() for x in value.split(',') if x.strip()]


@dataclass(frozen=True)
class Settings:
    base_url: str = os.getenv('KALSHI_BASE_URL', 'https://demo-api.kalshi.co')
    ws_url: str = os.getenv('KALSHI_WS_URL', 'wss://demo-api.kalshi.co/trade-api/ws/v2')
    api_key_id: str = os.getenv('KALSHI_API_KEY_ID', '')
    private_key_pem: str = os.getenv('KALSHI_PRIVATE_KEY_PEM', '')
    market_tickers: List[str] = tuple(_split_csv(os.getenv('KALSHI_MARKET_TICKERS', '')))
    poll_interval: float = float(os.getenv('POLL_INTERVAL', '1.0'))
    order_size: int = int(os.getenv('ORDER_SIZE', '1'))
    max_position_per_market: int = int(os.getenv('MAX_POSITION_PER_MARKET', '1'))
    entry_floor: int = int(os.getenv('ENTRY_FLOOR', '98'))
    entry_ceiling: int = int(os.getenv('ENTRY_CEILING', '99'))
    entry_price: int = int(os.getenv('ENTRY_PRICE', '98'))
    stop_below: int = int(os.getenv('STOP_BELOW', '80'))
    sqlite_path: str = os.getenv('SQLITE_PATH', 'data/kalshi_bot.db')
    dashboard_host: str = os.getenv('DASHBOARD_HOST', '0.0.0.0')
    dashboard_port: int = int(os.getenv('PORT', os.getenv('DASHBOARD_PORT', '8000')))


settings = Settings()
