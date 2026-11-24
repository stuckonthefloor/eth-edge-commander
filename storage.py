import os
import json
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get(
    "DB_PATH",
    "commander.db"
)


class Storage:

    def __init__(self, path=DB_PATH):
        self.path = path

        directory = os.path.dirname(path)

        if directory:
            os.makedirs(directory, exist_ok=True)

        self.initialize()

    def connect(self):
        connection = sqlite3.connect(
            self.path,
            timeout=30
        )

        connection.execute(
            "PRAGMA journal_mode=WAL"
        )

        connection.execute(
            "PRAGMA synchronous=FULL"
        )

        return connection

    def initialize(self):
        with self.connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS account (
                    id INTEGER PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            db.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

    def save(self, engine, events=None):
        snapshot = {
            "starting_equity": engine.starting_equity,
            "balance": engine.balance,
            "position": engine.position,
            "history": engine.history,
            "last_signal_id": engine.last_signal_id,
            "used_signals": sorted(engine.used_signals),
            "trading_locked": engine.trading_locked,
            "lock_reason": engine.lock_reason,
            "peak_equity": engine.peak_equity,
            "max_drawdown": engine.max_drawdown
        }

        now = datetime.now(
            timezone.utc
        ).isoformat()

        payload = json.dumps(
            snapshot,
            allow_nan=False
        )

        with self.connect() as db:
            db.execute("""
                INSERT INTO account (
                    id, payload, updated_at
                )
                VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
            """, (payload, now))

            for event in events or []:
                db.execute("""
                    INSERT INTO events (
                        event_type,
                        payload,
                        created_at
                    )
                    VALUES (?, ?, ?)
                """, (
                    event.get("type", "UNKNOWN"),
                    json.dumps(
                        event,
                        allow_nan=False
                    ),
                    now
                ))

    def restore(self, engine):
        with self.connect() as db:
            row = db.execute("""
                SELECT payload FROM account
                WHERE id = 1
            """).fetchone()

        if row is None:
            return False

        data = json.loads(row[0])

        engine.starting_equity = data["starting_equity"]
        engine.balance = data["balance"]
        engine.position = data["position"]
        engine.history = data["history"]
        engine.last_signal_id = data["last_signal_id"]
        engine.used_signals = set(data["used_signals"])
        engine.trading_locked = data["trading_locked"]
        engine.lock_reason = data["lock_reason"]
        engine.peak_equity = data["peak_equity"]
        engine.max_drawdown = data["max_drawdown"]

        return True

    def log_event(self, event_type, payload):
        now = datetime.now(
            timezone.utc
        ).isoformat()

        with self.connect() as db:
            db.execute("""
                INSERT INTO events (
                    event_type,
                    payload,
                    created_at
                )
                VALUES (?, ?, ?)
            """, (
                event_type,
                json.dumps(
                    payload,
                    allow_nan=False
                ),
                now
            ))

    def recent_events(self, limit=100):
        limit = max(1, min(int(limit), 1000))

        with self.connect() as db:
            rows = db.execute("""
                SELECT
                    id,
                    event_type,
                    payload,
                    created_at
                FROM events
                ORDER BY id DESC
                LIMIT ?
            """, (limit,)).fetchall()

        return [
            {
                "id": row[0],
                "type": row[1],
                "data": json.loads(row[2]),
                "time": row[3]
            }
            for row in rows
        ]
