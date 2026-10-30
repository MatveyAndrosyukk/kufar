import html
import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.types import (BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup,
                           InputMediaPhoto, URLInputFile)

import net
from db import db
from sources import BADGES, NAMES, SOURCES

log = logging.getLogger("notify")
MINSK = timezone(timedelta(hours=3))


def fmt_money(v, cur):
    s = f"{v:,.0f}".replace(",", " ")
    return f"{s} р." if cur == "BYN" else f"${s}"


def price_text(it: dict) -> str:
    unit = it.get("unit") or ""
    if not it.get("byn") and not it.get("usd"):
        return "Цена договорная"
    if it.get("byn") and it.get("usd"):
        return f"{fmt_money(it['byn'], 'BYN')}{unit} (≈ {fmt_money(it['usd'], 'USD')})"
    return fmt_money(it["byn"], "BYN") + unit if it.get("byn") else fmt_money(it["usd"], "USD") + unit


def fmt_time(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(MINSK).strftime("%d.%m %H:%M")
    except Exception:  # noqa: BLE001
        return ""


def caption(it: dict, title: str) -> str:
    e = html.escape
    t = it["title"] if len(it["title"]) <= 90 else it["title"][:88] + "…"
    lines = [f"{BADGES[it['source']]} · {e(title)}", f"<b>{e(t)}</b>", f"💰 <b>{e(price_text(it))}</b>"]
    loc = it.get("address") or it.get("city")
    if it.get("city") and it.get("address") and it["city"] not in it["address"]:
        loc = f"{it['city']}, {it['address']}"
    if loc:
        lines.append(f"📍 {e(loc)}")
    if it.get("params"):
        lines.append("ℹ️ " + e(" · ".join(it["params"][:3])))
    when = fmt_time(it.get("created"))
    if when:
        lines.append(f"🕒 {when}")
    return "\n".join(lines)[:1024]


def details(it: dict, desc: str) -> str:
    e = html.escape
    parts = [f"<b>{e(it['title'])}</b>", f"💰 {e(price_text(it))}"]
    if it.get("params"):
        parts.append("\n".join("• " + e(p) for p in it["params"]))
    parts.append("📝 " + e(desc.strip()) if desc else "📝 Описание не указано")
    return "\n\n".join(parts)


def keyboard(ad_id, idx, total, link, source) -> InlineKeyboardMarkup:
    rows = []
    if total > 1:
        rows.append([
            InlineKeyboardButton(text="◀️", callback_data=f"ph:{ad_id}:{(idx - 1) % total}"),
            InlineKeyboardButton(text=f"📷 {idx + 1}/{total}", callback_data="noop"),
            InlineKeyboardButton(text="▶️", callback_data=f"ph:{ad_id}:{(idx + 1) % total}"),
        ])
    rows.append([InlineKeyboardButton(text="📝 Описание", callback_data=f"desc:{ad_id}"),
                 InlineKeyboardButton(text=f"🔗 На {NAMES[source]}", url=link)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def photo(url, name):
    data = await net.image_jpeg(url)
    return BufferedInputFile(data, filename=f"{name}.jpg") if data else URLInputFile(url)


async def send(bot: Bot, chat_id: int, it: dict, title: str):
    desc = await SOURCES[it["source"]].full_desc(it)
    cap = caption(it, title)
    imgs = it["images"][:30]
    ad_id = await db.save_ad(it["uid"], {"images": imgs, "caption": cap, "details": details(it, desc),
                                         "link": it["link"], "source": it["source"]})
    kb = keyboard(ad_id, 0, len(imgs), it["link"], it["source"])
    if imgs:
        try:
            await bot.send_photo(chat_id, await photo(imgs[0], f"{ad_id}_0"), caption=cap, parse_mode="HTML",
                                 reply_markup=kb, show_caption_above_media=True)
            return
        except Exception as ex:  # noqa: BLE001
            log.warning("send_photo %s: %s", it["uid"], ex)
    await bot.send_message(chat_id, cap, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)


async def flip(bot: Bot, chat_id, message_id, ad_id, idx) -> bool:
    d = await db.get_ad(ad_id)
    if not d or not d["images"]:
        return False
    idx %= len(d["images"])
    await bot.edit_message_media(
        chat_id=chat_id, message_id=message_id,
        media=InputMediaPhoto(media=await photo(d["images"][idx], f"{ad_id}_{idx}"), caption=d["caption"],
                              parse_mode="HTML", show_caption_above_media=True),
        reply_markup=keyboard(ad_id, idx, len(d["images"]), d["link"], d["source"]))
    return True
