from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .db import Database
from .kalshi_client import KalshiClient


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class StrategyEngine:
    def __init__(self, client: KalshiClient, db: Database, entry_floor: int, entry_ceiling: int, entry_price: int, stop_below: int, order_size: int, max_position_per_market: int):
        self.client = client
        self.db = db
        self.entry_floor = entry_floor
        self.entry_ceiling = entry_ceiling
        self.entry_price = entry_price
        self.stop_below = stop_below
        self.order_size = order_size
        self.max_position_per_market = max_position_per_market

    def ensure_state(self, ticker: str) -> dict[str, Any]:
        state = self.db.get_state(ticker)
        if state:
            state['stop_armed'] = bool(state['stop_armed'])
            return state
        state = {
            'resting_entry_order_id': None,
            'last_entry_client_order_id': None,
            'last_exit_client_order_id': None,
            'yes_position': 0,
            'no_position': 0,
            'avg_yes_price': 0.0,
            'realized_pnl_cents': 0,
            'stop_armed': False,
            'updated_at': utc_now(),
        }
        self.db.upsert_state(ticker, state)
        return state

    def position_from_rest(self, payload: dict[str, Any]) -> int:
        rows = payload.get('market_positions') or payload.get('positions') or []
        if not rows:
            return 0
        row = rows[0]
        for key in ('position', 'yes_position', 'yes_count'):
            if key in row and row[key] is not None:
                try:
                    return int(float(row[key]))
                except Exception:
                    pass
        return 0

    def order_id_from_create(self, payload: dict[str, Any]) -> str | None:
        order = payload.get('order') or payload
        return order.get('id') if isinstance(order, dict) else None

    def maybe_place_or_cancel_entry(self, ticker: str, best_yes_bid: int | None, state: dict[str, Any]) -> str:
        if state['yes_position'] >= self.max_position_per_market:
            return 'max position reached'
        triggered = best_yes_bid is not None and self.entry_floor <= best_yes_bid <= self.entry_ceiling
        resting_id = state.get('resting_entry_order_id')
        if triggered and not resting_id:
            resp = self.client.create_yes_buy(ticker, self.order_size, self.entry_price)
            state['resting_entry_order_id'] = self.order_id_from_create(resp)
            state['last_entry_client_order_id'] = (resp.get('order') or {}).get('client_order_id')
            state['updated_at'] = utc_now()
            self.db.upsert_state(ticker, state)
            return f'placed entry @ {self.entry_price}'
        if not triggered and resting_id:
            self.client.cancel_order(resting_id)
            state['resting_entry_order_id'] = None
            state['updated_at'] = utc_now()
            self.db.upsert_state(ticker, state)
            return 'canceled stale entry'
        return 'idle'

    def refresh_position(self, ticker: str, state: dict[str, Any]) -> None:
        pos = self.position_from_rest(self.client.get_positions(ticker))
        state['yes_position'] = pos
        state['stop_armed'] = pos > 0
        if pos > 0 and not state.get('avg_yes_price'):
            state['avg_yes_price'] = float(self.entry_price)
        if pos > 0:
            state['resting_entry_order_id'] = None
        state['updated_at'] = utc_now()
        self.db.upsert_state(ticker, state)

    def maybe_stop_out(self, ticker: str, best_yes_bid: int | None, state: dict[str, Any]) -> str:
        if not state.get('stop_armed') or state.get('yes_position', 0) <= 0:
            return 'no stop'
        if best_yes_bid is None or best_yes_bid >= self.stop_below:
            return 'hold'
        exit_price = max(1, min(99, 100 - best_yes_bid))
        count = int(state['yes_position'])
        resp = self.client.create_no_buy(ticker, count, exit_price)
        state['last_exit_client_order_id'] = (resp.get('order') or {}).get('client_order_id')
        realized = (best_yes_bid - state.get('avg_yes_price', self.entry_price)) * count
        state['realized_pnl_cents'] = int(state.get('realized_pnl_cents', 0) + realized)
        state['yes_position'] = 0
        state['stop_armed'] = False
        state['updated_at'] = utc_now()
        self.db.upsert_state(ticker, state)
        self.db.insert_fill({
            'ts': utc_now(),
            'ticker': ticker,
            'side': 'no',
            'action': 'buy',
            'count': count,
            'price': exit_price,
            'order_id': self.order_id_from_create(resp),
            'client_order_id': state.get('last_exit_client_order_id'),
            'raw_json': json.dumps(resp),
        })
        return f'exit sent at no={exit_price}'

    def process_tick(self, ticker: str, best_yes_bid: int | None, best_no_bid: int | None, note: str = '') -> None:
        state = self.ensure_state(ticker)
        self.refresh_position(ticker, state)
        action_note = self.maybe_place_or_cancel_entry(ticker, best_yes_bid, state)
        self.refresh_position(ticker, state)
        stop_note = self.maybe_stop_out(ticker, best_yes_bid, state)
        unrealized = 0
        if state.get('yes_position', 0) > 0 and best_yes_bid is not None:
            unrealized = int((best_yes_bid - state.get('avg_yes_price', self.entry_price)) * state['yes_position'])
        self.db.insert_tick({
            'ts': utc_now(),
            'ticker': ticker,
            'best_yes_bid': best_yes_bid,
            'best_no_bid': best_no_bid,
            'yes_position': state.get('yes_position', 0),
            'no_position': state.get('no_position', 0),
            'realized_pnl_cents': state.get('realized_pnl_cents', 0),
            'unrealized_pnl_cents': unrealized,
            'note': ' | '.join(x for x in [note, action_note, stop_note] if x),
        })
