"""Фоновая проверка новых объявлений."""
import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError

import kufar
from config import CHECK_INTERVAL, MAX_NOTIFY_PER_CHECK
from db import db
from notify import send_ad

log = logging.getLogger("monitor")
_busy: set[int] = set()  # мониторинги, которые сейчас проверяются


def title_for(m: dict) -> str:
    return f"Новое: «{m['query']}»"


async def init_monitor(bot: Bot, m: dict) -> int:
    """Первый запуск: запоминаем текущие объявления, показываем последнее как пример."""
    if m["id"] in _busy:
        return 0
    _busy.add(m["id"])
    try:
        return await _init(bot, m)
    finally:
        _busy.discard(m["id"])


async def _init(bot: Bot, m: dict) -> int:
    ads = await kufar.search(m)
    await db.mark_seen(m["id"], [int(a["ad_id"]) for a in ads])
    await db.set_initialized(m["id"])
    if ads:
        await send_ad(bot, m["chat_id"], ads[0], title=f"Пример: самое свежее по «{m['query']}»")
    return len(ads)


async def check_monitor(bot: Bot, m: dict):
    if not m["initialized"]:
        await init_monitor(bot, m)
        return
    if m["id"] in _busy:
        return
    ads = await kufar.search(m)
    ids = [int(a["ad_id"]) for a in ads]
    new = await db.filter_unseen(m["id"], ids)
    if not new:
        return
    fresh = [a for a in reversed(ads) if int(a["ad_id"]) in new][-MAX_NOTIFY_PER_CHECK:]
    await db.mark_seen(m["id"], new)
    for ad in fresh:
        try:
            await send_ad(bot, m["chat_id"], ad, title=title_for(m))
        except TelegramForbiddenError:
            log.info("chat %s blocked bot, pausing monitor %s", m["chat_id"], m["id"])
            await db.set_active(m["id"], False)
            return
        except Exception as e:  # noqa: BLE001
            log.exception("send %s: %s", ad.get("ad_id"), e)
        await asyncio.sleep(0.5)
    log.info("monitor %s: %d new", m["id"], len(fresh))


async def loop(bot: Bot):
    n = 0
    while True:
        try:
            for m in await db.active_monitors():
                try:
                    await check_monitor(bot, m)
                except Exception as e:  # noqa: BLE001
                    log.warning("monitor %s failed: %s", m["id"], e)
                await asyncio.sleep(1.5)
            n += 1
            if n % 500 == 0:
                await db.cleanup()
        except Exception as e:  # noqa: BLE001
            log.exception("loop: %s", e)
        await asyncio.sleep(CHECK_INTERVAL)
