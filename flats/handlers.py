import html

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
                           KeyboardButton, Message, ReplyKeyboardMarkup)

from config import ALLOWED_USERS
from db import db
from monitor import init_monitor
from notify import flip
from regions import DEAL_SOURCES, DEALS, PRICE_PRESETS, REGIONS
from sources import NAMES

router = Router()
BTN_LIST = "📋 Текущие мониторинги"
BTN_NEW = "➕ Новый мониторинг"
MAIN_KB = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BTN_NEW)], [KeyboardButton(text=BTN_LIST)]],
                              resize_keyboard=True)


class New(StatesGroup):
    deal = State()
    region = State()
    city = State()
    currency = State()
    price = State()
    custom_price = State()


def ikb(rows):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=d) for t, d in r]
                                                 for r in rows])


def chunks(a, n):
    return [a[i:i + n] for i in range(0, len(a), n)]


def money(v, cur):
    return f"{v:,}".replace(",", " ") + (" р." if cur == "BYN" else " $")


def allowed(uid):
    return not ALLOWED_USERS or uid in ALLOWED_USERS


def sources_text(deal, region_id):
    srcs = [NAMES[s] for s in DEAL_SOURCES[deal]]
    if region_id == 5 and "Realt" in srcs:
        srcs.remove("Realt")  # для городов Минской области у Realt нет разделов
    return " + ".join(srcs)


def describe(m):
    region = REGIONS[m["region_id"]][0] if m["region_id"] in REGIONS else "Вся Беларусь"
    place = f"{m['city']} ({region})" if m.get("city") and m["city"] != region else region
    cur = m["currency"]
    if m["price_min"] is None and m["price_max"] is None:
        pr = "любая"
    elif m["price_max"] is None:
        pr = f"от {money(m['price_min'], cur)}"
    else:
        pr = f"{money(m['price_min'] or 0, cur)} – {money(m['price_max'], cur)}"
    st = "🟢 активен" if m["active"] else "⏸ на паузе"
    return (f"{DEALS[m['deal']][0]}\n📍 {html.escape(place)}\n💰 {pr}\n"
            f"🌐 {sources_text(m['deal'], m['region_id'])}\n{st}")


def monitor_kb(m):
    t = ("⏸ Пауза", f"m:pause:{m['id']}") if m["active"] else ("▶️ Включить", f"m:resume:{m['id']}")
    return ikb([[t, ("🗑 Удалить", f"m:del:{m['id']}")]])


@router.message(CommandStart())
async def start(msg: Message, state: FSMContext):
    await state.clear()
    if not allowed(msg.from_user.id):
        await msg.answer(f"⛔ Доступ закрыт. Ваш ID: <code>{msg.from_user.id}</code>", parse_mode="HTML")
        return
    await msg.answer("👋 Я ищу квартиры сразу на нескольких сайтах — <b>Kufar, Realt и Flatly</b> — "
                     "и присылаю новые объявления, как только они появляются.\n\n"
                     "Нажми «➕ Новый мониторинг».", parse_mode="HTML", reply_markup=MAIN_KB)


@router.message(F.text == BTN_LIST)
async def list_monitors(msg: Message, state: FSMContext):
    await state.clear()
    if not allowed(msg.from_user.id):
        return
    items = await db.user_monitors(msg.chat.id)
    if not items:
        await msg.answer("Пока нет мониторингов. Нажми «➕ Новый мониторинг».", reply_markup=MAIN_KB)
    for m in items:
        await msg.answer(describe(m), parse_mode="HTML", reply_markup=monitor_kb(m))


@router.callback_query(F.data.startswith("m:"))
async def monitor_action(cb: CallbackQuery):
    _, action, mid = cb.data.split(":")
    m = await db.get_monitor(int(mid))
    if not m or m["chat_id"] != cb.message.chat.id:
        await cb.answer("Не найден")
        return
    if action == "del":
        await db.delete_monitor(m["id"])
        await cb.message.edit_text("🗑 Мониторинг удалён")
    else:
        await db.set_active(m["id"], action == "resume")
        m = await db.get_monitor(m["id"])
        await cb.message.edit_text(describe(m), parse_mode="HTML", reply_markup=monitor_kb(m))
    await cb.answer()


@router.message(F.text == BTN_NEW)
async def new_start(msg: Message, state: FSMContext):
    if not allowed(msg.from_user.id):
        return
    await state.clear()
    await state.set_state(New.deal)
    await msg.answer("Что ищем?", reply_markup=ikb(
        [[(f"{name}  ·  {src}", f"d:{k}")] for k, (name, src) in DEALS.items()]))


@router.callback_query(New.deal, F.data.startswith("d:"))
async def new_deal(cb: CallbackQuery, state: FSMContext):
    deal = cb.data[2:]
    await state.update_data(deal=deal)
    await state.set_state(New.region)
    rows = chunks([(name, f"r:{rid}") for rid, (name, _, _) in REGIONS.items()], 2)
    rows.append([("🇧🇾 Вся Беларусь", "r:0")])
    await cb.message.edit_text(f"{DEALS[deal][0]}\n\n📍 Выбери область:", reply_markup=ikb(rows))
    await cb.answer()


@router.callback_query(New.region, F.data.startswith("r:"))
async def new_region(cb: CallbackQuery, state: FSMContext):
    rid = int(cb.data[2:])
    await state.update_data(region_id=rid or None, city=None)
    cities = list(REGIONS[rid][2].keys()) if rid in REGIONS else []
    if len(cities) > 1:
        await state.set_state(New.city)
        rows = chunks([(c, f"c:{c}") for c in cities], 3)
        rows.append([("📍 Вся область", "c:")])
        await cb.message.edit_text(f"📍 {REGIONS[rid][0]}\n\nВыбери город:", reply_markup=ikb(rows))
    else:
        await ask_currency(cb, state)
    await cb.answer()


@router.callback_query(New.city, F.data.startswith("c:"))
async def new_city(cb: CallbackQuery, state: FSMContext):
    await state.update_data(city=cb.data[2:] or None)
    await ask_currency(cb, state)
    await cb.answer()


async def ask_currency(cb, state):
    await state.set_state(New.currency)
    await cb.message.edit_text("💱 В какой валюте задаём цену?", reply_markup=ikb([
        [("🇧🇾 BYN (рубли)", "cur:BYN"), ("💵 USD", "cur:USD")], [("♾ Любая цена", "p:any")]]))


@router.callback_query(New.currency, F.data.startswith("cur:"))
async def new_currency(cb: CallbackQuery, state: FSMContext):
    cur = cb.data[4:]
    d = await state.update_data(currency=cur)
    await state.set_state(New.price)
    unit = {"long": " в месяц", "day": " за сутки", "sale": ""}[d["deal"]]
    rows = chunks([(f"{money(a, cur)} – {money(b, cur)}", f"p:{a}:{b}")
                   for a, b in PRICE_PRESETS[(d["deal"], cur)]], 2)
    rows.append([("✍️ Свой диапазон", "p:custom"), ("♾ Любая", "p:any")])
    await cb.message.edit_text(f"💰 Цена{unit} ({cur}):", reply_markup=ikb(rows))
    await cb.answer()


@router.callback_query(F.data.startswith("p:"))
async def new_price(cb: CallbackQuery, state: FSMContext, bot: Bot):
    if await state.get_state() not in (New.currency.state, New.price.state):
        await cb.answer()
        return
    parts = cb.data.split(":")
    if parts[1] == "custom":
        await state.set_state(New.custom_price)
        cur = (await state.get_data()).get("currency", "BYN")
        await cb.message.edit_text(f"✍️ Напиши диапазон в {cur} через дефис, например <code>500-900</code>.\n"
                                   "Только минимум: <code>500-</code>, только максимум: <code>-900</code>",
                                   parse_mode="HTML")
        await cb.answer()
        return
    if parts[1] == "any":
        await state.update_data(price_min=None, price_max=None)
    else:
        await state.update_data(price_min=int(parts[1]), price_max=int(parts[2]))
    await cb.answer()
    await cb.message.edit_reply_markup(reply_markup=None)
    await finish(cb.message, state, bot)


@router.message(New.custom_price, F.text)
async def new_custom_price(msg: Message, state: FSMContext, bot: Bot):
    txt = msg.text.replace(" ", "").replace("—", "-").replace("–", "-")
    if "-" not in txt:
        txt += "-"
    lo, _, hi = txt.partition("-")
    try:
        lo, hi = (int(lo) if lo else None), (int(hi) if hi else None)
    except ValueError:
        await msg.answer("Не понял 🙈 Пример: <code>500-900</code>", parse_mode="HTML")
        return
    if lo is not None and hi is not None and lo > hi:
        lo, hi = hi, lo
    await state.update_data(price_min=lo, price_max=hi)
    await finish(msg, state, bot)


async def finish(msg: Message, state: FSMContext, bot: Bot):
    d = await state.get_data()
    await state.clear()
    mid = await db.add_monitor(msg.chat.id, d["deal"], d.get("region_id"), d.get("city"),
                               d.get("currency", "BYN"), d.get("price_min"), d.get("price_max"))
    m = await db.get_monitor(mid)
    await bot.send_message(msg.chat.id, "✅ Мониторинг создан!\n\n" + describe(m) +
                           "\n\n⏳ Смотрю, что сейчас есть на сайтах…", parse_mode="HTML", reply_markup=MAIN_KB)
    counts, errors = await init_monitor(bot, m)
    lines = [f"{'✅' if counts.get(s) else '▫️'} {NAMES[s]}: {counts.get(s, 0)}" for s in DEAL_SOURCES[m["deal"]]
             if s not in errors]
    lines += [f"⚠️ {NAMES[s]}: не ответил, попробую позже" for s in errors]
    await bot.send_message(msg.chat.id, "👀 Сейчас подходящих объявлений:\n" + "\n".join(lines) +
                           "\n\nВыше — самые свежие для примера. Новые пришлю сразу 🔔")


@router.callback_query(F.data.startswith("ph:"))
async def photo_flip(cb: CallbackQuery, bot: Bot):
    _, ad_id, idx = cb.data.split(":")
    await cb.answer()
    try:
        if not await flip(bot, cb.message.chat.id, cb.message.message_id, int(ad_id), int(idx)):
            await cb.answer("Фото недоступны", show_alert=True)
    except Exception as e:  # noqa: BLE001
        if "not modified" not in str(e):
            raise


@router.callback_query(F.data.startswith("desc:"))
async def full_desc(cb: CallbackQuery):
    d = await db.get_ad(int(cb.data[5:]))
    await cb.answer()
    text = d.get("details") if d else None
    if not text:
        await cb.message.answer("Описание недоступно")
        return
    chunk = ""
    for line in text.split("\n"):
        while len(line) > 4000:
            cut = line.rfind(" ", 0, 4000)
            cut = cut if cut > 0 else 4000
            if chunk:
                await cb.message.reply(chunk, parse_mode="HTML")
                chunk = ""
            await cb.message.reply(line[:cut], parse_mode="HTML")
            line = line[cut:]
        if len(chunk) + len(line) + 1 > 4000:
            await cb.message.reply(chunk, parse_mode="HTML")
            chunk = ""
        chunk += line + "\n"
    if chunk.strip():
        await cb.message.reply(chunk, parse_mode="HTML")


@router.callback_query(F.data == "noop")
async def noop(cb: CallbackQuery):
    await cb.answer()
