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


def build_caption(ad: dict, title: str) -> str:
    """Короткая карточка, чтобы кнопки листания были рядом с фото."""
    e = html.escape
    region, area = kufar.location(ad)
    subject = ad.get("subject") or "Без названия"
    if len(subject) > 90:
        subject = subject[:88] + "…"
    lines = [f"🔔 {e(title)}", f"<b>{e(subject)}</b>", f"💰 <b>{e(kufar.fmt_price(ad))}</b>"]
    loc = ", ".join(x for x in (area, region) if x)
    if loc:
        lines.append(f"📍 {e(loc)}")
    params = [p for p in kufar.params_lines(ad, limit=3) if len(p) <= 40]
    if params:
        lines.append("ℹ️ " + e(" · ".join(params)))
    when = kufar.fmt_time(ad)
    if when:
        lines.append(f"🕒 {when}")
    return "\n".join(lines)[:CAPTION_LIMIT]


def details_text(ad: dict, desc: str) -> str:
    """Полное описание и все характеристики — по кнопке."""
    parts = [f"<b>{html.escape(ad.get('subject') or '')}</b>", f"💰 {html.escape(kufar.fmt_price(ad))}"]
    params = kufar.params_lines(ad, limit=40)
    if params:
        parts.append("\n".join("• " + html.escape(p) for p in params))
    if desc:
        parts.append("📝 " + html.escape(desc.strip()))
    return "\n\n".join(parts)


def keyboard(ad_id: int, idx: int, total: int, link: str) -> InlineKeyboardMarkup:
    rows = []
    if total > 1:
        rows.append([
            InlineKeyboardButton(text="◀️", callback_data=f"ph:{ad_id}:{(idx - 1) % total}"),
            InlineKeyboardButton(text=f"📷 {idx + 1}/{total}", callback_data="noop"),
            InlineKeyboardButton(text="▶️", callback_data=f"ph:{ad_id}:{(idx + 1) % total}"),
        ])
    rows.append([InlineKeyboardButton(text="📝 Описание", callback_data=f"desc:{ad_id}"),
                 InlineKeyboardButton(text="🔗 На Kufar", url=link)])
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
    caption = build_caption(ad, title)
    await db.save_ad(ad_id, {"images": images, "caption": caption, "details": details_text(ad, desc),
                             "desc": desc, "link": link})
    kb = keyboard(ad_id, 0, len(images), link)
    if images:
        try:
            await bot.send_photo(chat_id, await photo_input(images[0], ad_id, 0), caption=caption,
                                 parse_mode="HTML", reply_markup=kb, show_caption_above_media=True)
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
                              caption=data["caption"], parse_mode="HTML",
                              show_caption_above_media=True),
        reply_markup=keyboard(ad_id, idx, len(imgs), data["link"]),
    )
    return True
