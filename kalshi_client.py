from __future__ import annotations

import json
import uuid
from typing import Any

import httpx

from .auth import auth_headers


class KalshiClient:
    def __init__(self, base_url: str, api_key_id: str, private_key):
        self.base_url = base_url.rstrip('/')
        self.api_key_id = api_key_id
        self.private_key = private_key
        self.http = httpx.Client(timeout=15.0)

    def _public_get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        r = self.http.get(f'{self.base_url}{path}', params=params)
        r.raise_for_status()
        return r.json()

    def _private_get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        headers = auth_headers(self.api_key_id, self.private_key, 'GET', path)
        r = self.http.get(f'{self.base_url}{path}', params=params, headers=headers)
        r.raise_for_status()
        return r.json()

    def _private_post(self, path: str, payload: dict) -> dict[str, Any]:
        headers = auth_headers(self.api_key_id, self.private_key, 'POST', path)
        r = self.http.post(f'{self.base_url}{path}', json=payload, headers=headers)
        r.raise_for_status()
        return r.json() if r.text.strip() else {}

    def _private_delete(self, path: str) -> dict[str, Any]:
        headers = auth_headers(self.api_key_id, self.private_key, 'DELETE', path)
        r = self.http.delete(f'{self.base_url}{path}', headers=headers)
        r.raise_for_status()
        return r.json() if r.text.strip() else {}

    def get_positions(self, ticker: str | None = None) -> dict[str, Any]:
        params = {'ticker': ticker} if ticker else None
        return self._private_get('/trade-api/v2/portfolio/positions', params=params)

    def get_balance(self) -> dict[str, Any]:
        return self._private_get('/trade-api/v2/portfolio/balance')

    def get_orders(self, ticker: str, status: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {'ticker': ticker}
        if status:
            params['status'] = status
        return self._private_get('/trade-api/v2/portfolio/orders', params=params)

    def get_order(self, order_id: str) -> dict[str, Any]:
        return self._private_get(f'/trade-api/v2/portfolio/orders/{order_id}')

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        return self._private_delete(f'/trade-api/v2/portfolio/orders/{order_id}')

    def create_order(self, ticker: str, side: str, action: str, count: int, yes_price: int | None = None, no_price: int | None = None, client_order_id: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            'ticker': ticker,
            'client_order_id': client_order_id or str(uuid.uuid4()),
            'side': side,
            'action': action,
            'count': count,
            'type': 'limit',
        }
        if yes_price is not None:
            payload['yes_price'] = yes_price
        if no_price is not None:
            payload['no_price'] = no_price
        return self._private_post('/trade-api/v2/portfolio/orders', payload)

    def create_yes_buy(self, ticker: str, count: int, yes_price: int, client_order_id: str | None = None) -> dict[str, Any]:
        return self.create_order(ticker, 'yes', 'buy', count, yes_price=yes_price, client_order_id=client_order_id)

    def create_no_buy(self, ticker: str, count: int, no_price: int, client_order_id: str | None = None) -> dict[str, Any]:
        return self.create_order(ticker, 'no', 'buy', count, no_price=no_price, client_order_id=client_order_id)
