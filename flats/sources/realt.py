import json
import re
import time

from net import get_text, usd_rate
from regions import REGIONS

KIND = {"long": "rent/flat-for-long", "day": "rent/flat-for-day", "sale": "sale/flats"}
_cache: dict[str, tuple[float, list]] = {}


def _urls(deal, region_id, city) -> list[tuple[str, str]]:
    """[(url, префикс области)] для запроса."""
    if region_id not in REGIONS:
        regs = [(rid, None) for rid in REGIONS]
    else:
        regs = [(region_id, city)]
    out = []
    for rid, c in regs:
        _, prefix, cities = REGIONS[rid]
        if prefix is None:
            continue
        slugs = [cities.get(c)] if c else ([""] if region_id not in REGIONS else list(cities.values()))
        for slug in slugs:
            if slug is None:
                continue
            base = "https://realt.by" + (f"/{prefix}" if prefix else "") + f"/{KIND[deal]}/"
            out.append((base + (f"{slug}/" if slug else "") + "?sortType=createdAt", prefix))
    return out


def _objects(html: str) -> list[dict]:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return []
    pp = json.loads(m.group(1)).get("props", {}).get("pageProps", {})
    if "objects" in pp:
        return pp["objects"] or []
    return ((pp.get("objectsResponse") or {}).get("body") or {}).get("results") or []


def _norm(o: dict, deal: str, prefix: str, rate: float) -> dict:
    rates = o.get("priceRates") or {}
    byn = rates.get("933")
    usd = rates.get("840")
    if byn is None and usd is None:
        p, cur = o.get("price") or o.get("calculatedPrice"), o.get("priceCurrency") or 933
        if p:
            if cur == 840:
                usd, byn = p, p * rate
            else:
                byn, usd = p, p / rate
    elif byn is None and usd:
        byn = usd * rate
    elif usd is None and byn:
        usd = byn / rate
    params = []
    if o.get("rooms"):
        params.append(f"Комнат: {o['rooms']}")
    if o.get("areaTotal"):
        params.append(f"Площадь: {o['areaTotal']} м²")
    if o.get("storey"):
        params.append(f"Этаж: {o['storey']}" + (f"/{o['storeys']}" if o.get("storeys") else ""))
    if o.get("maxCapacity"):
        params.append(f"Гостей: до {o['maxCapacity']}")
    kind = KIND[deal].replace("/", "-")
    link = "https://realt.by" + (f"/{prefix}" if prefix else "") + f"/{kind}/object/{o['code']}/"
    return {
        "uid": f"realt:{o['code']}", "source": "realt", "id": o["code"],
        "title": o.get("title") or o.get("headline") or "Квартира",
        "byn": byn or None, "usd": usd or None, "unit": {"long": "/мес", "day": "/сутки"}.get(deal, ""),
        "city": o.get("townName"), "region": o.get("stateRegionName"), "address": o.get("address"),
        "params": params, "desc": o.get("description") or o.get("headline") or "",
        "images": [u for u in (o.get("images") or []) if isinstance(u, str)],
        "link": link, "created": o.get("createdAt"),
    }


async def fetch(deal: str, region_id, city) -> list[dict]:
    rate = await usd_rate()
    out = []
    for url, prefix in _urls(deal, region_id, city):
        ts, objs = _cache.get(url, (0, []))
        if time.time() - ts > 50:
            objs = _objects(await get_text(url))
            _cache[url] = (time.time(), objs)
        out += [_norm(o, deal, prefix, rate) for o in objs if o.get("code")]
    return out


async def full_desc(item: dict) -> str:
    if item.get("desc"):
        return item["desc"]
    try:
        html = await get_text(item["link"])
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
        obj = json.loads(m.group(1))["props"]["pageProps"].get("object") or {}
        return obj.get("description") or obj.get("headline") or ""
    except Exception:  # noqa: BLE001
        return ""
