"""Самопроверка бота квартир на сервере: все источники отвечают, ссылки и фото открываются."""
import asyncio
import sys
import time

sys.path.insert(0, "/flats")

import net
from sources import SOURCES


async def main():
    ok = True
    for deal, rid, city in [("long", 1, "Брест"), ("day", 1, "Брест"), ("sale", 1, "Брест"), ("long", 7, None), ("day", 7, None)]:
        for name in {"long": ["kufar", "realt"], "day": ["realt", "flatly"], "sale": ["kufar", "realt"]}[deal]:
            t0 = time.time()
            try:
                items = await SOURCES[name].fetch(deal, rid, city)
            except Exception as e:  # noqa: BLE001
                print("BAD ", deal, rid, city, name, "ERROR", repr(e), f"{time.time() - t0:.1f}s")
                ok = False
                continue
            first = items[0] if items else None
            status = img = "-"
            if first:
                async with net.session().get(first["link"]) as r:
                    status = r.status
                if first["images"]:
                    img = "ok" if await net.image_jpeg(first["images"][0]) else "FAIL"
            good = bool(items) and status in (200, 429) and img != "FAIL"
            ok &= good
            print(("OK  " if good else "BAD "), deal, rid, city, name, len(items), status, img, f"{time.time() - t0:.1f}s",
                  first and (first["title"][:40], first["city"], first["byn"]))
    await net.close()
    print("FLATS_OK" if ok else "FLATS_FAIL")
    assert ok

asyncio.run(main())
