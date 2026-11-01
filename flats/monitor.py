import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError

from config import CHECK_INTERVAL, MAX_NOTIFY_PER_CHECK
from db import db
from notify import send
from regions import DEAL_SOURCES, DEALS
from sources import NAMES, SOURCES

log = logging.getLogger("monitor")
_busy: set[int] = set()


def price_ok(it: dict, m: dict) -> bool:
    lo, hi = m.get("price_min"), m.get("price_max")
    if lo is None and hi is None:
        return True
    p = it.get("byn") if m.get("currency", "BYN") == "BYN" else it.get("usd")
    if not p:
        return False
    return (lo is None or p >= lo) and (hi is None or p <= hi)


async def collect(m: dict) -> tuple[dict[str, list], dict[str, str]]:
    """Объявления по каждому источнику (новые первыми) и ошибки источников."""
    res, errors = {}, {}
    for src in DEAL_SOURCES[m["deal"]]:
        try:
            items = await SOURCES[src].fetch(m["deal"], m["region_id"], m["city"])
            res[src] = [it for it in items if price_ok(it, m)]
        except Exception as e:  # noqa: BLE001
            log.warning("%s for monitor %s: %s", src, m["id"], e)
            errors[src] = e.__class__.__name__
    return res, errors


async def init_monitor(bot: Bot, m: dict) -> tuple[dict, dict]:
    if m["id"] in _busy:
        return {}, {}
    _busy.add(m["id"])
    try:
        res, errors = await collect(m)
        await db.mark_seen(m["id"], [it["uid"] for items in res.values() for it in items])
        if not errors:
            await db.set_initialized(m["id"])
        for src, items in res.items():
            if items:
                try:
                    await send(bot, m["chat_id"], items[0], f"пример: свежее с {NAMES[src]}")
                except Exception as e:  # noqa: BLE001
                    log.warning("example %s: %s", src, e)
        return {s: len(v) for s, v in res.items()}, errors
    finally:
        _busy.discard(m["id"])


async def check(bot: Bot, m: dict):
    if not m["initialized"]:
        await init_monitor(bot, m)
        return
    if m["id"] in _busy:
        return
    res, _ = await collect(m)
    items = [it for v in res.values() for it in v]
    new = await db.unseen(m["id"], [it["uid"] for it in items])
    if not new:
        return
    fresh = [it for it in items if it["uid"] in new]
    await db.mark_seen(m["id"], list(new))
    title = "новое: " + DEALS[m["deal"]][0].split(" ", 1)[1].lower()
    for it in list(reversed(fresh))[-MAX_NOTIFY_PER_CHECK:]:
        try:
            await send(bot, m["chat_id"], it, title)
        except TelegramForbiddenError:
            log.info("chat %s: бот не запущен/заблокирован, пропускаю", m["chat_id"])
            return
        except Exception as e:  # noqa: BLE001
            log.exception("send %s: %s", it["uid"], e)
        await asyncio.sleep(0.5)
    log.info("monitor %s: %d new", m["id"], len(fresh))


async def loop(bot: Bot):
    n = 0
    while True:
        try:
            for m in await db.active_monitors():
                try:
                    await check(bot, m)
                except Exception as e:  # noqa: BLE001
                    log.warning("monitor %s: %s", m["id"], e)
                await asyncio.sleep(1)
            n += 1
            if n % 500 == 0:
                await db.cleanup()
        except Exception as e:  # noqa: BLE001
            log.exception("loop: %s", e)
        await asyncio.sleep(CHECK_INTERVAL)
