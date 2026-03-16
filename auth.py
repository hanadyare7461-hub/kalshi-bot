from __future__ import annotations

import base64
import time
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


def load_private_key(private_key_pem: str):
    key_data = private_key_pem.encode('utf-8')
    return serialization.load_pem_private_key(key_data, password=None)


def now_ms() -> str:
    return str(int(time.time() * 1000))


def sign_request(private_key, timestamp_ms: str, method: str, path: str) -> str:
    payload = f"{timestamp_ms}{method.upper()}{path}".encode('utf-8')
    sig = private_key.sign(
        payload,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
        hashes.SHA256(),
    )
    return base64.b64encode(sig).decode('utf-8')


def auth_headers(api_key_id: str, private_key, method: str, path: str) -> dict[str, str]:
    ts = now_ms()
    return {
        'KALSHI-ACCESS-KEY': api_key_id,
        'KALSHI-ACCESS-TIMESTAMP': ts,
        'KALSHI-ACCESS-SIGNATURE': sign_request(private_key, ts, method, path),
    }


def auth_headers_for_ws(api_key_id: str, private_key, ws_url: str) -> dict[str, str]:
    path = urlsplit(ws_url).path
    return auth_headers(api_key_id, private_key, 'GET', path)
