import json
import re

from net import get_json, get_text
from regions import norm

SEARCH = "https://api.kufar.by/search-api/v2/search/rendered-paginated"
TYP = {"long": "let", "sale": "sell"}
SHOW = ("rooms", "size", "floor", "re_number_floors", "flat_repair", "year_built", "house_type")


def _param(ad, key):
    for p in ad.get("ad_parameters") or []:
        if p.get("p") == key:
            v = p.get("vl")
            return ", ".join(map(str, v)) if isinstance(v, list) else v
    return None


def _norm_ad(ad: dict, deal: str) -> dict:
    def money(k):
        try:
            return int(ad.get(k)) / 100 or None
        except (TypeError, ValueError):
            return None
    params = []
    labels = {"rooms": "Комнат", "size": "Площадь", "floor": "Этаж", "re_number_floors": "Этажей",
              "flat_repair": "Ремонт", "year_built": "Год", "house_type": "Дом"}
    for k in SHOW:
        v = _param(ad, k)
        if v not in (None, "", []):
            params.append(f"{labels[k]}: {v}{' м²' if k == 'size' else ''}")
    imgs = [f"https://rms.kufar.by/v1/gallery/{i['path']}" for i in ad.get("images") or [] if i.get("path")]
    return {
        "uid": f"kufar:{ad['ad_id']}", "source": "kufar", "id": ad["ad_id"],
        "title": ad.get("subject") or "Квартира",
        "byn": money("price_byn"), "usd": money("price_usd"), "unit": "/мес" if deal == "long" else "",
        "city": _param(ad, "area"), "region": _param(ad, "region"), "address": None,
        "params": params, "desc": ad.get("body") or ad.get("body_short") or "",
        "images": imgs, "link": ad.get("ad_link"), "created": ad.get("list_time"),
    }


async def fetch(deal: str, region_id, city) -> list[dict]:
    if deal not in TYP:
        return []
    params = {"cat": "1010", "typ": TYP[deal], "lang": "ru", "size": "50", "sort": "lst.d"}
    if region_id:
        params["rgn"] = str(region_id)
    data = await get_json(SEARCH, params)
    out = [_norm_ad(a, deal) for a in data.get("ads") or []]
    if city:
        out = [x for x in out if not x["city"] or norm(city) in norm(x["city"])]
    return out


async def full_desc(item: dict) -> str:
    try:
        html = await get_text(f"https://www.kufar.by/item/{item['id']}")
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
        if m:
            stack = [json.loads(m.group(1))]
            while stack:
                cur = stack.pop()
                if isinstance(cur, dict):
                    if isinstance(cur.get("body"), str) and str(cur.get("ad_id")) == str(item["id"]):
                        return cur["body"]
                    stack.extend(cur.values())
                elif isinstance(cur, list):
                    stack.extend(cur)
    except Exception:  # noqa: BLE001
        pass
    return item.get("desc") or ""
