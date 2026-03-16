from __future__ import annotations

import asyncio
import logging

from .auth import load_private_key
from .config import settings
from .db import Database
from .kalshi_client import KalshiClient
from .market_data import OrderbookWatcher
from .strategy import StrategyEngine

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')


async def main() -> None:
    if not settings.market_tickers:
        raise RuntimeError('Set KALSHI_MARKET_TICKERS to a comma-separated list of market tickers.')
    if not settings.api_key_id or not settings.private_key_pem:
        raise RuntimeError('Set KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY_PEM.')

    private_key = load_private_key(settings.private_key_pem)
    db = Database(settings.sqlite_path)
    client = KalshiClient(settings.base_url, settings.api_key_id, private_key)
    engine = StrategyEngine(
        client=client,
        db=db,
        entry_floor=settings.entry_floor,
        entry_ceiling=settings.entry_ceiling,
        entry_price=settings.entry_price,
        stop_below=settings.stop_below,
        order_size=settings.order_size,
        max_position_per_market=settings.max_position_per_market,
    )
    watcher = OrderbookWatcher(settings.ws_url, settings.api_key_id, private_key, list(settings.market_tickers))

    logging.info('Connected balance=%s', client.get_balance())

    while True:
        try:
            async for ticker, best_yes_bid, best_no_bid, event in watcher.stream():
                logging.info('%s yes=%s no=%s event=%s', ticker, best_yes_bid, best_no_bid, event)
                engine.process_tick(ticker, best_yes_bid, best_no_bid, note=event)
        except Exception as exc:
            logging.exception('stream error: %s', exc)
            await asyncio.sleep(3)


if __name__ == '__main__':
    asyncio.run(main())
