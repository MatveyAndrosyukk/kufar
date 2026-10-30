import json
import os
import time

import aiosqlite

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS monitors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    deal TEXT NOT NULL,
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
    uid TEXT NOT NULL,
    seen_at INTEGER,
    PRIMARY KEY (monitor_id, uid)
);
CREATE TABLE IF NOT EXISTS ads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uid TEXT UNIQUE,
    data TEXT NOT NULL,
    saved_at INTEGER
);
"""


class DB:
    def __init__(self, path=DB_PATH):
        self.path = path
        self.conn = None

    async def connect(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.executescript(SCHEMA)
        await self.conn.commit()

    async def close(self):
        if self.conn:
            await self.conn.close()

    async def add_monitor(self, chat_id, deal, region_id, city, currency, pmin, pmax) -> int:
        cur = await self.conn.execute(
            "INSERT INTO monitors (chat_id, deal, region_id, city, currency, price_min, price_max, created_at)"
            " VALUES (?,?,?,?,?,?,?,?)", (chat_id, deal, region_id, city, currency, pmin, pmax, int(time.time())))
        await self.conn.commit()
        return cur.lastrowid

    async def get_monitor(self, mid):
        cur = await self.conn.execute("SELECT * FROM monitors WHERE id=?", (mid,))
        row = await cur.fetchone()
        return dict(row) if row else None

    async def user_monitors(self, chat_id):
        cur = await self.conn.execute("SELECT * FROM monitors WHERE chat_id=? ORDER BY id", (chat_id,))
        return [dict(r) for r in await cur.fetchall()]

    async def active_monitors(self):
        cur = await self.conn.execute("SELECT * FROM monitors WHERE active=1")
        return [dict(r) for r in await cur.fetchall()]

    async def set_active(self, mid, active: bool):
        await self.conn.execute("UPDATE monitors SET active=? WHERE id=?", (int(active), mid))
        await self.conn.commit()

    async def set_initialized(self, mid):
        await self.conn.execute("UPDATE monitors SET initialized=1 WHERE id=?", (mid,))
        await self.conn.commit()

    async def delete_monitor(self, mid):
        await self.conn.execute("DELETE FROM monitors WHERE id=?", (mid,))
        await self.conn.execute("DELETE FROM seen WHERE monitor_id=?", (mid,))
        await self.conn.commit()

    async def unseen(self, mid, uids: list[str]) -> set[str]:
        if not uids:
            return set()
        seen = set()
        for i in range(0, len(uids), 500):
            part = uids[i:i + 500]
            q = ",".join("?" * len(part))
            cur = await self.conn.execute(f"SELECT uid FROM seen WHERE monitor_id=? AND uid IN ({q})", (mid, *part))
            seen |= {r[0] for r in await cur.fetchall()}
        return set(uids) - seen

    async def mark_seen(self, mid, uids):
        now = int(time.time())
        await self.conn.executemany("INSERT OR IGNORE INTO seen (monitor_id, uid, seen_at) VALUES (?,?,?)",
                                    [(mid, u, now) for u in uids])
        await self.conn.commit()

    async def save_ad(self, uid: str, data: dict) -> int:
        await self.conn.execute(
            "INSERT INTO ads (uid, data, saved_at) VALUES (?,?,?) "
            "ON CONFLICT(uid) DO UPDATE SET data=excluded.data, saved_at=excluded.saved_at",
            (uid, json.dumps(data, ensure_ascii=False), int(time.time())))
        await self.conn.commit()
        cur = await self.conn.execute("SELECT id FROM ads WHERE uid=?", (uid,))
        return (await cur.fetchone())[0]

    async def get_ad(self, ad_id: int):
        cur = await self.conn.execute("SELECT data FROM ads WHERE id=?", (ad_id,))
        row = await cur.fetchone()
        return json.loads(row[0]) if row else None

    async def cleanup(self):
        now = int(time.time())
        await self.conn.execute("DELETE FROM ads WHERE saved_at < ?", (now - 30 * 86400,))
        await self.conn.execute("DELETE FROM seen WHERE seen_at < ?", (now - 120 * 86400,))
        await self.conn.commit()


db = DB()
