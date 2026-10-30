"""Формирование и отправка карточки объявления с листанием фото."""
import html
import logging

from aiogram import Bot
from aiogram.types import (BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup,
                           InputMediaPhoto, URLInputFile)

import kufar
from db import db

log = logging.getLogger("notify")
CAPTION_LIMIT = 1024


def build_caption(ad: dict, desc: str, title: str) -> tuple[str, bool]:
    """Возвращает (подпись, описание_обрезано)."""
    e = html.escape
    region, area = kufar.location(ad)
    lines = [f"🔔 <b>{e(title)}</b>", "", f"<b>{e(ad.get('subject') or 'Без названия')}</b>",
             f"💰 <b>{e(kufar.fmt_price(ad))}</b>"]
    loc = ", ".join(x for x in (area, region) if x)
    if loc:
        lines.append(f"📍 {e(loc)}")
    params = kufar.params_lines(ad)
    if params:
        lines.append("")
        lines += [f"• {e(p)}" for p in params]
    when = kufar.fmt_time(ad)
    footer = f"\n🕒 {when}" if when else ""
    head = "\n".join(lines)
    room = CAPTION_LIMIT - len(head) - len(footer) - 10
    d = (desc or "").strip()
    cut = False
    if d:
        if room < 60:
            cut = True
        else:
            if len(e(d)) > room:
                cut = True
                d = d[: room - 30].rsplit(" ", 1)[0] + "…"
                while len(e(d)) > room:
                    d = d[:-40] + "…"
            head += "\n\n📝 " + e(d)
    return (head + footer)[:CAPTION_LIMIT], cut


def keyboard(ad_id: int, idx: int, total: int, link: str, long_desc: bool) -> InlineKeyboardMarkup:
    rows = []
    if total > 1:
        rows.append([
            InlineKeyboardButton(text="◀️", callback_data=f"ph:{ad_id}:{(idx - 1) % total}"),
            InlineKeyboardButton(text=f"📷 {idx + 1}/{total}", callback_data="noop"),
            InlineKeyboardButton(text="▶️", callback_data=f"ph:{ad_id}:{(idx + 1) % total}"),
        ])
    if long_desc:
        rows.append([InlineKeyboardButton(text="📝 Полное описание", callback_data=f"desc:{ad_id}")])
    rows.append([InlineKeyboardButton(text="🔗 Открыть на Kufar", url=link)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def photo_input(url: str, ad_id: int, idx: int):
    data = await kufar.download(url)
    if data:
        return BufferedInputFile(data, filename=f"{ad_id}_{idx}.jpg")
    return URLInputFile(url)


async def send_ad(bot: Bot, chat_id: int, ad: dict, title: str = "Новое объявление"):
    ad_id = int(ad["ad_id"])
    desc = await kufar.full_description(ad)
    images = kufar.image_urls(ad)
    link = ad.get("ad_link") or f"https://www.kufar.by/item/{ad_id}"
    caption, long_desc = build_caption(ad, desc, title)
    await db.save_ad(ad_id, {"images": images, "caption": caption, "desc": desc, "link": link,
                             "long": long_desc})
    kb = keyboard(ad_id, 0, len(images), link, long_desc)
    if images:
        try:
            await bot.send_photo(chat_id, await photo_input(images[0], ad_id, 0), caption=caption,
                                 parse_mode="HTML", reply_markup=kb)
            return
        except Exception as e:  # noqa: BLE001
            log.warning("send_photo failed %s: %s", ad_id, e)
    await bot.send_message(chat_id, caption, parse_mode="HTML", reply_markup=kb,
                           disable_web_page_preview=True)


async def flip_photo(bot: Bot, chat_id: int, message_id: int, ad_id: int, idx: int) -> bool:
    data = await db.get_ad(ad_id)
    if not data or not data["images"]:
        return False
    imgs = data["images"]
    idx %= len(imgs)
    await bot.edit_message_media(
        chat_id=chat_id, message_id=message_id,
        media=InputMediaPhoto(media=await photo_input(imgs[idx], ad_id, idx),
                              caption=data["caption"], parse_mode="HTML"),
        reply_markup=keyboard(ad_id, idx, len(imgs), data["link"], data.get("long", True)),
    )
    return True
