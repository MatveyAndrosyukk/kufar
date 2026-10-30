"""HTTP-сессия, курс валют, загрузка фото с конвертацией в JPEG."""
import io
import logging
import time

import aiohttp
from PIL import Image

log = logging.getLogger("net")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/129.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
}
_session: aiohttp.ClientSession | None = None
_usd = {"rate": 3.0, "ts": 0.0}


def session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(headers=HEADERS, timeout=aiohttp.ClientTimeout(total=30))
    return _session


async def close():
    if _session and not _session.closed:
        await _session.close()


async def get_text(url: str, params=None) -> str:
    async with session().get(url, params=params) as r:
        r.raise_for_status()
        return await r.text()


async def get_json(url: str, params=None):
    async with session().get(url, params=params) as r:
        r.raise_for_status()
        return await r.json(content_type=None)


async def usd_rate() -> float:
    """Курс НБРБ: сколько BYN за 1 USD (кэш 6 часов)."""
    if time.time() - _usd["ts"] > 6 * 3600:
        try:
            d = await get_json("https://api.nbrb.by/exrates/rates/USD", {"parammode": "2"})
            _usd["rate"] = float(d["Cur_OfficialRate"]) / float(d.get("Cur_Scale", 1))
        except Exception as e:  # noqa: BLE001
            log.warning("nbrb: %s", e)
        _usd["ts"] = time.time()
    return _usd["rate"]


async def image_jpeg(url: str) -> bytes | None:
    try:
        async with session().get(url) as r:
            if r.status != 200:
                return None
            raw = await r.read()
        im = Image.open(io.BytesIO(raw))
        im = im.convert("RGB")
        im.thumbnail((1600, 1600))
        out = io.BytesIO()
        im.save(out, "JPEG", quality=88)
        return out.getvalue()
    except Exception as e:  # noqa: BLE001
        log.warning("image %s: %s", url, e)
        return None
