from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any

import websockets

from .auth import auth_headers_for_ws


class OrderbookWatcher:
    def __init__(self, ws_url: str, api_key_id: str, private_key, tickers: list[str]):
        self.ws_url = ws_url
        self.api_key_id = api_key_id
        self.private_key = private_key
        self.tickers = tickers
        self.books: dict[str, dict[str, dict[int, int]]] = defaultdict(lambda: {'yes': {}, 'no': {}})

    @staticmethod
    def _best_bid(side_map: dict[int, int]) -> int | None:
        positive = [price for price, qty in side_map.items() if qty > 0]
        return max(positive) if positive else None

    def _apply_snapshot(self, ticker: str, msg: dict[str, Any]) -> tuple[int | None, int | None]:
        book = self.books[ticker]
        yes = msg.get('yes') or msg.get('yes_bids') or []
        no = msg.get('no') or msg.get('no_bids') or []
        book['yes'] = {int(level[0]): int(level[1]) for level in yes if isinstance(level, (list, tuple)) and len(level) >= 2}
        book['no'] = {int(level[0]): int(level[1]) for level in no if isinstance(level, (list, tuple)) and len(level) >= 2}
        return self._best_bid(book['yes']), self._best_bid(book['no'])

    def _apply_delta(self, ticker: str, msg: dict[str, Any]) -> tuple[int | None, int | None]:
        book = self.books[ticker]
        side = msg.get('side')
        price = msg.get('price')
        delta = msg.get('delta')
        if side in ('yes', 'no') and price is not None and delta is not None:
            side_map = book[side]
            new_qty = int(side_map.get(int(price), 0) + int(delta))
            if new_qty <= 0:
                side_map.pop(int(price), None)
            else:
                side_map[int(price)] = new_qty
        return self._best_bid(book['yes']), self._best_bid(book['no'])

    async def stream(self):
        headers = auth_headers_for_ws(self.api_key_id, self.private_key, self.ws_url)
        async with websockets.connect(self.ws_url, additional_headers=headers, ping_interval=20, ping_timeout=20) as ws:
            subscribe = {
                'id': 1,
                'cmd': 'subscribe',
                'params': {
                    'channels': ['orderbook_delta', 'user_orders', 'market_positions'],
                    'market_tickers': self.tickers,
                },
            }
            await ws.send(json.dumps(subscribe))
            async for raw in ws:
                msg = json.loads(raw)
                msg_type = msg.get('type') or msg.get('channel')
                market_ticker = msg.get('market_ticker') or msg.get('ticker')
                if msg_type == 'orderbook_snapshot' and market_ticker:
                    yield market_ticker, *self._apply_snapshot(market_ticker, msg), msg_type
                elif msg_type == 'orderbook_delta' and market_ticker:
                    yield market_ticker, *self._apply_delta(market_ticker, msg), msg_type
                elif market_ticker and market_ticker in self.books:
                    yield market_ticker, self._best_bid(self.books[market_ticker]['yes']), self._best_bid(self.books[market_ticker]['no']), msg_type or 'event'
                await asyncio.sleep(0)
