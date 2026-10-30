"""Работа с API Куфара."""
import json
import logging
import re
from datetime import datetime, timezone, timedelta

import aiohttp

log = logging.getLogger("kufar")

SEARCH_URL = "https://api.kufar.by/search-api/v2/search/rendered-paginated"
ITEM_PAGE = "https://www.kufar.by/item/{ad_id}"
IMG_URL = "https://rms.kufar.by/v1/gallery/{path}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/129.0 Safari/537.36",
    "Accept": "application/json, text/html;q=0.9",
    "Accept-Language": "ru-RU,ru;q=0.9",
}
MINSK_TZ = timezone(timedelta(hours=3))
_session: aiohttp.ClientSession | None = None


def session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(headers=HEADERS, timeout=aiohttp.ClientTimeout(total=25))
    return _session


async def close():
    if _session and not _session.closed:
        await _session.close()


def _norm(s: str) -> str:
    return (s or "").strip().lower().replace("ё", "е")


# ---------------- поиск ----------------

async def search(m: dict, size: int = 50) -> list[dict]:
    """Последние объявления под мониторинг m (уже отфильтрованные по городу и цене)."""
    params = {"query": m["query"], "lang": "ru", "size": str(size), "sort": "lst.d"}
    if m.get("region_id"):
        params["rgn"] = str(m["region_id"])
    if m.get("currency", "BYN") == "BYN" and (m.get("price_min") or m.get("price_max")):
        lo = (m.get("price_min") or 0) * 100
        hi = (m.get("price_max") or 1_000_000_000) * 100
        params["cur"] = "BYR"
        params["prc"] = f"r:{lo},{hi}"
    async with session().get(SEARCH_URL, params=params) as r:
        r.raise_for_status()
        data = await r.json(content_type=None)
    ads = data.get("ads") or []
    return [a for a in ads if matches(a, m)]


def param(ad: dict, *keys: str):
    for p in ad.get("ad_parameters") or []:
        if p.get("p") in keys:
            v = p.get("vl")
            if isinstance(v, list):
                v = ", ".join(map(str, v))
            return v
    return None


def location(ad: dict) -> tuple[str | None, str | None]:
    return param(ad, "region", "rgn"), param(ad, "area", "ar")


def price(ad: dict, currency: str) -> float | None:
    raw = ad.get("price_byn" if currency == "BYN" else "price_usd")
    try:
        val = int(raw) / 100
    except (TypeError, ValueError):
        return None
    return val or None  # 0 = «договорная»


def matches(ad: dict, m: dict) -> bool:
    if m.get("city"):
        _, area = location(ad)
        if area and _norm(m["city"]) not in _norm(area):
            return False
    lo, hi = m.get("price_min"), m.get("price_max")
    if lo is not None or hi is not None:
        p = price(ad, m.get("currency", "BYN"))
        if p is None:
            return False
        if lo is not None and p < lo:
            return False
        if hi is not None and p > hi:
            return False
    return True


# ---------------- детали ----------------

def image_urls(ad: dict) -> list[str]:
    urls = []
    for img in ad.get("images") or []:
        path = img.get("path")
        if path:
            urls.append(IMG_URL.format(path=path))
        elif img.get("id"):
            i = str(img["id"])
            urls.append(f"https://yams.kufar.by/api/v1/kufar-ads/images/{i[:2]}/{i}.jpg?rule=gallery")
    return urls


def _find_body(obj, ad_id: int):
    """Ищем полное описание в __NEXT_DATA__ страницы объявления."""
    stack, fallback = [obj], None
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            body = cur.get("body")
            if isinstance(body, str) and body.strip():
                if str(cur.get("ad_id") or cur.get("adId") or "") == str(ad_id):
                    return body
                fallback = fallback or body
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return fallback


async def full_description(ad: dict) -> str:
    if ad.get("body"):
        return ad["body"]
    try:
        async with session().get(ITEM_PAGE.format(ad_id=ad["ad_id"])) as r:
            html = await r.text()
        mt = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
        if mt:
            body = _find_body(json.loads(mt.group(1)), ad["ad_id"])
            if body:
                return body
    except Exception as e:  # noqa: BLE001
        log.warning("description %s: %s", ad.get("ad_id"), e)
    return ad.get("body_short") or ""


async def download(url: str) -> bytes | None:
    try:
        async with session().get(url) as r:
            if r.status == 200:
                return await r.read()
    except Exception as e:  # noqa: BLE001
        log.warning("image %s: %s", url, e)
    return None


def fmt_price(ad: dict) -> str:
    byn, usd = price(ad, "BYN"), price(ad, "USD")
    if not byn and not usd:
        return "Договорная"
    parts = []
    if byn:
        parts.append(f"{byn:,.0f} р.".replace(",", " "))
    if usd:
        parts.append(f"≈ ${usd:,.0f}".replace(",", " "))
    return " / ".join(parts)


def fmt_time(ad: dict) -> str:
    t = ad.get("list_time")
    try:
        dt = datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(MINSK_TZ)
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:  # noqa: BLE001
        return ""


SKIP_PARAMS = {"region", "rgn", "area", "ar", "category", "cat", "remuneration_type"}


def params_lines(ad: dict, limit: int = 8) -> list[str]:
    out = []
    for p in ad.get("ad_parameters") or []:
        if p.get("p") in SKIP_PARAMS or not p.get("pl"):
            continue
        v = p.get("vl")
        if isinstance(v, list):
            v = ", ".join(map(str, v))
        if v in (None, "", True, False):
            continue
        out.append(f"{p['pl']}: {v}")
        if len(out) >= limit:
            break
    return out
