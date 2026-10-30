import html as htmllib
import re
import time

from net import get_text, usd_rate
from regions import REGIONS, norm, region_cities

BASE = "https://flatly.by"
_cache = {"ts": 0.0, "cards": []}


def _attr(block: str, name: str):
    m = re.search(rf'\b{name}="([^"]*)"', block)
    return htmllib.unescape(m.group(1)) if m else None


def parse(page: str) -> list[dict]:
    cards = []
    parts = re.split(r'<div class="card[^"]*" onclick="openDetails', page)[1:]
    for p in parts:
        cid = _attr(p, "data-id")
        if not cid:
            continue
        end = p.find('class="card-price-box"')
        body = p if end < 0 else p[:end + 3000]
        imgs = re.findall(r'<img class="card-photo" src="([^"]+)"', body)
        title = re.search(r'class="cb-title">([^<]+)<', body)
        addr = re.search(r'class="address-icon".*?</svg>\s*<span>([^<]+)</span>', body, re.S)
        cards.append({
            "id": int(cid), "slug": _attr(p, "data-slug") or "",
            "title": htmllib.unescape(title.group(1).strip()) if title else (_attr(p, "data-title") or ""),
            "price": float(_attr(p, "data-price") or 0) or None,
            "city": _attr(p, "data-city"), "address": htmllib.unescape(addr.group(1).strip()) if addr else None,
            "rooms": _attr(p, "data-bedrooms"), "guests": _attr(p, "data-guests"),
            "floor": _attr(p, "data-floor"), "floors": _attr(p, "data-total-floors"),
            "category": _attr(p, "data-category"),
            "images": [i if i.startswith("http") else BASE + i for i in imgs],
        })
    return cards


async def fetch(deal: str, region_id, city) -> list[dict]:
    if deal != "day":
        return []
    if time.time() - _cache["ts"] > 50:
        _cache["cards"] = parse(await get_text(BASE + "/?type=apartments"))
        _cache["ts"] = time.time()
    rate = await usd_rate()
    if city:
        wanted = {norm(city)}
    elif region_id in REGIONS:
        wanted = {norm(c) for c in region_cities(region_id)}
    else:
        wanted = None
    out = []
    for c in _cache["cards"]:
        if wanted is not None and norm(c["city"]) not in wanted:
            continue
        params = []
        if c["rooms"]:
            params.append(f"Комнат: {c['rooms']}")
        if c["guests"]:
            params.append(f"Гостей: до {c['guests']}")
        if c["floor"]:
            params.append(f"Этаж: {c['floor']}" + (f"/{c['floors']}" if c["floors"] else ""))
        out.append({
            "uid": f"flatly:{c['id']}", "source": "flatly", "id": c["id"],
            "title": c["title"] or "Квартира", "byn": c["price"], "usd": c["price"] / rate if c["price"] else None,
            "unit": "/сутки", "city": c["city"], "region": None, "address": c["address"],
            "params": params, "desc": "", "images": c["images"],
            "link": f"{BASE}/listings/{c['id']}" + (f"-{c['slug']}" if c["slug"] else ""),
            "created": None,
        })
    out.sort(key=lambda x: -x["id"])  # новые id — новые объявления
    return out


async def full_desc(item: dict) -> str:
    try:
        page = await get_text(item["link"])
        for pat in (r'class="desc-text"[^>]*>(.*?)</div>',
                    r'<meta name="description" content="([^"]+)"'):
            m = re.search(pat, page, re.S)
            if m:
                text = re.sub(r"<[^>]+>", "\n", m.group(1))
                text = re.sub(r"\n\s*\n+", "\n", htmllib.unescape(text)).strip()
                if len(text) > 20:
                    return text
    except Exception:  # noqa: BLE001
        pass
    return ""
