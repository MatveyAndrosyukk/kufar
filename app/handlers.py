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
from notify import flip_photo
from regions import PRICE_PRESETS, REGIONS

router = Router()
BTN_LIST = "📋 Текущие мониторинги"
BTN_NEW = "➕ Новый мониторинг"

MAIN_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=BTN_NEW)], [KeyboardButton(text=BTN_LIST)]],
    resize_keyboard=True,
)


class New(StatesGroup):
    query = State()
    region = State()
    city = State()
    currency = State()
    price = State()
    custom_price = State()


def ikb(rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=d) for t, d in row] for row in rows
    ])


def chunks(items, n):
    return [items[i:i + n] for i in range(0, len(items), n)]


def money(v, cur):
    return f"{v:,}".replace(",", " ") + (" р." if cur == "BYN" else " $")


def describe(m: dict) -> str:
    region = REGIONS.get(m["region_id"], ("Вся Беларусь",))[0] if m["region_id"] else "Вся Беларусь"
    place = f"{m['city']} ({region})" if m.get("city") else region
    if m["price_min"] is None and m["price_max"] is None:
        pr = "любая"
    else:
        pr = f"{money(m['price_min'] or 0, m['currency'])} – {money(m['price_max'], m['currency'])}" \
            if m["price_max"] is not None else f"от {money(m['price_min'], m['currency'])}"
    status = "🟢 активен" if m["active"] else "⏸ на паузе"
    return (f"🔎 <b>{html.escape(m['query'])}</b>\n📍 {html.escape(place)}\n"
            f"💰 {pr}\n{status}")


def allowed(user_id: int) -> bool:
    return not ALLOWED_USERS or user_id in ALLOWED_USERS


# ---------------- главное меню ----------------

@router.message(CommandStart())
async def start(msg: Message, state: FSMContext):
    await state.clear()
    if not allowed(msg.from_user.id):
        await msg.answer(f"⛔ Доступ закрыт. Ваш ID: <code>{msg.from_user.id}</code>", parse_mode="HTML")
        return
    await msg.answer(
        "👋 Я слежу за Kufar и присылаю новые объявления сразу, как они появляются.\n\n"
        "Нажми «➕ Новый мониторинг», чтобы начать.",
        reply_markup=MAIN_KB,
    )


@router.message(F.text == BTN_LIST)
async def list_monitors(msg: Message, state: FSMContext):
    await state.clear()
    if not allowed(msg.from_user.id):
        return
    items = await db.user_monitors(msg.chat.id)
    if not items:
        await msg.answer("Пока нет мониторингов. Нажми «➕ Новый мониторинг».", reply_markup=MAIN_KB)
        return
    for m in items:
        await msg.answer(describe(m), parse_mode="HTML", reply_markup=monitor_kb(m))


def monitor_kb(m):
    toggle = ("⏸ Пауза", f"m:pause:{m['id']}") if m["active"] else ("▶️ Включить", f"m:resume:{m['id']}")
    return ikb([[toggle, ("🗑 Удалить", f"m:del:{m['id']}")]])


@router.callback_query(F.data.startswith("m:"))
async def monitor_action(cb: CallbackQuery):
    _, action, mid = cb.data.split(":")
    m = await db.get_monitor(int(mid))
    if not m or m["chat_id"] != cb.message.chat.id:
        await cb.answer("Мониторинг не найден")
        return
    if action == "del":
        await db.delete_monitor(m["id"])
        await cb.message.edit_text("🗑 Мониторинг удалён")
        await cb.answer()
        return
    await db.set_active(m["id"], action == "resume")
    m = await db.get_monitor(m["id"])
    await cb.message.edit_text(describe(m), parse_mode="HTML", reply_markup=monitor_kb(m))
    await cb.answer("Готово")


# ---------------- создание мониторинга ----------------

@router.message(F.text == BTN_NEW)
async def new_start(msg: Message, state: FSMContext):
    if not allowed(msg.from_user.id):
        return
    await state.clear()
    await state.set_state(New.query)
    await msg.answer("✍️ Что ищем? Напиши так же, как в поиске Kufar.\nНапример: <i>квартира</i>, "
                     "<i>iphone 13</i>, <i>велосипед</i>", parse_mode="HTML")


@router.message(New.query, F.text)
async def new_query(msg: Message, state: FSMContext):
    q = msg.text.strip()
    if q in (BTN_NEW, BTN_LIST) or len(q) < 2:
        await msg.answer("Напиши, что ищем (минимум 2 символа).")
        return
    await state.update_data(query=q[:100])
    await state.set_state(New.region)
    rows = chunks([(name, f"r:{rid}") for rid, (name, _) in REGIONS.items()], 2)
    rows.append([("🇧🇾 Вся Беларусь", "r:0")])
    await msg.answer(f"🔎 «{html.escape(q)}»\n\n📍 Выбери область:", parse_mode="HTML", reply_markup=ikb(rows))


@router.callback_query(New.region, F.data.startswith("r:"))
async def new_region(cb: CallbackQuery, state: FSMContext):
    rid = int(cb.data[2:])
    await state.update_data(region_id=rid or None, city=None)
    cities = REGIONS.get(rid, ("", []))[1]
    if cities:
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


async def ask_currency(cb: CallbackQuery, state: FSMContext):
    await state.set_state(New.currency)
    await cb.message.edit_text("💱 В какой валюте задаём цену?", reply_markup=ikb([
        [("🇧🇾 BYN (рубли)", "cur:BYN"), ("💵 USD", "cur:USD")],
        [("♾ Любая цена", "p:any")],
    ]))


@router.callback_query(New.currency, F.data.startswith("cur:"))
async def new_currency(cb: CallbackQuery, state: FSMContext):
    cur = cb.data[4:]
    await state.update_data(currency=cur)
    await state.set_state(New.price)
    presets = [(f"{money(a, cur)} – {money(b, cur)}", f"p:{a}:{b}") for a, b in PRICE_PRESETS[cur]]
    rows = chunks(presets, 2)
    rows.append([("✍️ Свой диапазон", "p:custom"), ("♾ Любая", "p:any")])
    await cb.message.edit_text(f"💰 Диапазон цен ({cur}):", reply_markup=ikb(rows))
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
        await cb.message.edit_text(f"✍️ Напиши диапазон в {cur} через дефис, например <code>200-800</code>.\n"
                                   f"Можно только минимум: <code>300-</code> или только максимум: <code>-1000</code>",
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
        lo = int(lo) if lo else None
        hi = int(hi) if hi else None
    except ValueError:
        await msg.answer("Не понял 🙈 Пример: <code>200-800</code>", parse_mode="HTML")
        return
    if lo is not None and hi is not None and lo > hi:
        lo, hi = hi, lo
    await state.update_data(price_min=lo, price_max=hi)
    await finish(msg, state, bot)


async def finish(msg: Message, state: FSMContext, bot: Bot):
    d = await state.get_data()
    await state.clear()
    mid = await db.add_monitor(msg.chat.id, d["query"], d.get("region_id"), d.get("city"),
                               d.get("currency", "BYN"), d.get("price_min"), d.get("price_max"))
    m = await db.get_monitor(mid)
    await bot.send_message(msg.chat.id, "✅ Мониторинг создан!\n\n" + describe(m) +
                           "\n\n⏳ Смотрю, что сейчас есть на Kufar…", parse_mode="HTML", reply_markup=MAIN_KB)
    try:
        n = await init_monitor(bot, m)
        text = (f"👀 Сейчас подходящих объявлений: {n}. Выше — самое свежее для примера.\n"
                "Как только появится новое — сразу пришлю 🔔") if n else \
            ("Сейчас подходящих объявлений нет. Как только появятся — пришлю 🔔")
    except Exception as e:  # noqa: BLE001
        text = f"⚠️ Не удалось сразу проверить Kufar ({e.__class__.__name__}). Попробую ещё раз автоматически."
    await bot.send_message(msg.chat.id, text)


# ---------------- листание фото ----------------

@router.callback_query(F.data.startswith("ph:"))
async def photo_flip(cb: CallbackQuery, bot: Bot):
    _, ad_id, idx = cb.data.split(":")
    await cb.answer()
    try:
        ok = await flip_photo(bot, cb.message.chat.id, cb.message.message_id, int(ad_id), int(idx))
        if not ok:
            await cb.answer("Фото больше недоступны", show_alert=True)
    except Exception as e:  # noqa: BLE001
        if "not modified" not in str(e):
            raise


@router.callback_query(F.data.startswith("desc:"))
async def full_desc(cb: CallbackQuery):
    data = await db.get_ad(int(cb.data[5:]))
    await cb.answer()
    if not data or not data.get("desc"):
        await cb.message.answer("Описание недоступно")
        return
    text = data["desc"]
    for i in range(0, len(text), 4000):
        await cb.message.reply(text[i:i + 4000])


@router.callback_query(F.data == "noop")
async def noop(cb: CallbackQuery):
    await cb.answer()
