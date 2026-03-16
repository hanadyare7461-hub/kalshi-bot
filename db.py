from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SCHEMA = '''
CREATE TABLE IF NOT EXISTS ticks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    ticker TEXT NOT NULL,
    best_yes_bid INTEGER,
    best_no_bid INTEGER,
    yes_position INTEGER DEFAULT 0,
    no_position INTEGER DEFAULT 0,
    realized_pnl_cents INTEGER DEFAULT 0,
    unrealized_pnl_cents INTEGER DEFAULT 0,
    note TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS bot_state (
    ticker TEXT PRIMARY KEY,
    resting_entry_order_id TEXT,
    last_entry_client_order_id TEXT,
    last_exit_client_order_id TEXT,
    yes_position INTEGER DEFAULT 0,
    no_position INTEGER DEFAULT 0,
    avg_yes_price REAL DEFAULT 0,
    realized_pnl_cents INTEGER DEFAULT 0,
    stop_armed INTEGER DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    action TEXT NOT NULL,
    count INTEGER NOT NULL,
    price INTEGER NOT NULL,
    order_id TEXT,
    client_order_id TEXT,
    raw_json TEXT NOT NULL
);
'''


class Database:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def upsert_state(self, ticker: str, state: dict) -> None:
        with self.connect() as conn:
            conn.execute(
                '''
                INSERT INTO bot_state (
                    ticker, resting_entry_order_id, last_entry_client_order_id,
                    last_exit_client_order_id, yes_position, no_position,
                    avg_yes_price, realized_pnl_cents, stop_armed, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    resting_entry_order_id=excluded.resting_entry_order_id,
                    last_entry_client_order_id=excluded.last_entry_client_order_id,
                    last_exit_client_order_id=excluded.last_exit_client_order_id,
                    yes_position=excluded.yes_position,
                    no_position=excluded.no_position,
                    avg_yes_price=excluded.avg_yes_price,
                    realized_pnl_cents=excluded.realized_pnl_cents,
                    stop_armed=excluded.stop_armed,
                    updated_at=excluded.updated_at
                ''',
                (
                    ticker,
                    state.get('resting_entry_order_id'),
                    state.get('last_entry_client_order_id'),
                    state.get('last_exit_client_order_id'),
                    int(state.get('yes_position', 0)),
                    int(state.get('no_position', 0)),
                    float(state.get('avg_yes_price', 0)),
                    int(state.get('realized_pnl_cents', 0)),
                    int(bool(state.get('stop_armed', False))),
                    state['updated_at'],
                ),
            )

    def get_state(self, ticker: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute('SELECT * FROM bot_state WHERE ticker = ?', (ticker,)).fetchone()
            return dict(row) if row else None

    def insert_tick(self, row: dict) -> None:
        with self.connect() as conn:
            conn.execute(
                '''
                INSERT INTO ticks (
                    ts, ticker, best_yes_bid, best_no_bid, yes_position, no_position,
                    realized_pnl_cents, unrealized_pnl_cents, note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    row['ts'], row['ticker'], row.get('best_yes_bid'), row.get('best_no_bid'),
                    row.get('yes_position', 0), row.get('no_position', 0),
                    row.get('realized_pnl_cents', 0), row.get('unrealized_pnl_cents', 0), row.get('note', ''),
                ),
            )

    def insert_fill(self, row: dict) -> None:
        with self.connect() as conn:
            conn.execute(
                '''
                INSERT INTO fills (ts, ticker, side, action, count, price, order_id, client_order_id, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    row['ts'], row['ticker'], row['side'], row['action'], row['count'], row['price'],
                    row.get('order_id'), row.get('client_order_id'), row['raw_json'],
                ),
            )

    def dashboard_summary(self) -> dict:
        with self.connect() as conn:
            totals = conn.execute(
                '''
                SELECT
                    COALESCE(SUM(realized_pnl_cents), 0) AS realized_pnl_cents,
                    COUNT(*) AS rows
                FROM bot_state
                '''
            ).fetchone()
            states = conn.execute('SELECT * FROM bot_state ORDER BY ticker').fetchall()
            recent_ticks = conn.execute(
                'SELECT ts, ticker, best_yes_bid, yes_position, realized_pnl_cents, unrealized_pnl_cents FROM ticks ORDER BY id DESC LIMIT 200'
            ).fetchall()
            recent_fills = conn.execute('SELECT * FROM fills ORDER BY id DESC LIMIT 50').fetchall()
        return {
            'totals': dict(totals),
            'markets': [dict(x) for x in states],
            'recent_ticks': [dict(x) for x in reversed(recent_ticks)],
            'recent_fills': [dict(x) for x in recent_fills],
        }
