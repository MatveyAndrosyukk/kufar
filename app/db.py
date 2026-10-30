import json
import os
import time

import aiosqlite

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS monitors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    query TEXT NOT NULL,
    region_id INTEGER,
    city TEXT,
    currency TEXT DEFAULT 'BYN',
    price_min INTEGER,
    price_max INTEGER,
    active INTEGER DEFAULT 1,
    initialized INTEGER DEFAULT 0,
    created_at INTEGER
);
CREATE TABLE IF NOT EXISTS seen (
    monitor_id INTEGER NOT NULL,
    ad_id INTEGER NOT NULL,
    seen_at INTEGER,
    PRIMARY KEY (monitor_id, ad_id)
);
CREATE TABLE IF NOT EXISTS ads (
    ad_id INTEGER PRIMARY KEY,
    data TEXT NOT NULL,
    saved_at INTEGER
);
"""


class DB:
    def __init__(self, path: str = DB_PATH):
        self.path = path
        self.conn: aiosqlite.Connection | None = None

    async def connect(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.executescript(SCHEMA)
        await self.conn.commit()

    async def close(self):
        if self.conn:
            await self.conn.close()

    # --- мониторинги ---
    async def add_monitor(self, chat_id, query, region_id, city, currency, pmin, pmax) -> int:
        cur = await self.conn.execute(
            "INSERT INTO monitors (chat_id, query, region_id, city, currency, price_min, price_max, created_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (chat_id, query, region_id, city, currency, pmin, pmax, int(time.time())),
        )
        await self.conn.commit()
        return cur.lastrowid

    async def get_monitor(self, mid: int):
        cur = await self.conn.execute("SELECT * FROM monitors WHERE id=?", (mid,))
        row = await cur.fetchone()
        return dict(row) if row else None

    async def user_monitors(self, chat_id: int):
        cur = await self.conn.execute("SELECT * FROM monitors WHERE chat_id=? ORDER BY id", (chat_id,))
        return [dict(r) for r in await cur.fetchall()]

    async def active_monitors(self):
        cur = await self.conn.execute("SELECT * FROM monitors WHERE active=1")
        return [dict(r) for r in await cur.fetchall()]

    async def set_active(self, mid: int, active: bool):
        await self.conn.execute("UPDATE monitors SET active=? WHERE id=?", (int(active), mid))
        await self.conn.commit()

    async def set_initialized(self, mid: int):
        await self.conn.execute("UPDATE monitors SET initialized=1 WHERE id=?", (mid,))
        await self.conn.commit()

    async def delete_monitor(self, mid: int):
        await self.conn.execute("DELETE FROM monitors WHERE id=?", (mid,))
        await self.conn.execute("DELETE FROM seen WHERE monitor_id=?", (mid,))
        await self.conn.commit()

    # --- просмотренные ---
    async def filter_unseen(self, mid: int, ad_ids: list[int]) -> set[int]:
        if not ad_ids:
            return set()
        q = ",".join("?" * len(ad_ids))
        cur = await self.conn.execute(f"SELECT ad_id FROM seen WHERE monitor_id=? AND ad_id IN ({q})", (mid, *ad_ids))
        seen = {r[0] for r in await cur.fetchall()}
        return set(ad_ids) - seen

    async def mark_seen(self, mid: int, ad_ids):
        now = int(time.time())
        await self.conn.executemany(
            "INSERT OR IGNORE INTO seen (monitor_id, ad_id, seen_at) VALUES (?,?,?)",
            [(mid, a, now) for a in ad_ids],
        )
        await self.conn.commit()

    # --- кэш объявлений (для листания фото) ---
    async def save_ad(self, ad_id: int, data: dict):
        await self.conn.execute(
            "INSERT OR REPLACE INTO ads (ad_id, data, saved_at) VALUES (?,?,?)",
            (ad_id, json.dumps(data, ensure_ascii=False), int(time.time())),
        )
        await self.conn.commit()

    async def get_ad(self, ad_id: int):
        cur = await self.conn.execute("SELECT data FROM ads WHERE ad_id=?", (ad_id,))
        row = await cur.fetchone()
        return json.loads(row[0]) if row else None

    async def cleanup(self, days: int = 30):
        border = int(time.time()) - days * 86400
        await self.conn.execute("DELETE FROM ads WHERE saved_at < ?", (border,))
        await self.conn.execute("DELETE FROM seen WHERE seen_at < ?", (border - 60 * 86400,))
        await self.conn.commit()


db = DB()
