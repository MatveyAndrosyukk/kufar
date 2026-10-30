import json, re, sys, urllib.request, time
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
def get(u):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA, "Accept-Language": "ru"}), timeout=30)
        return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return getattr(e, "code", 0), ""
def objs(h):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', h, re.S)
    if not m: return None, None, None
    pp = json.loads(m.group(1))["props"]["pageProps"]
    if "objects" in pp: return pp["objects"], pp.get("totalCount"), pp.get("objectListingFilters")
    r = pp.get("objectsResponse", {}).get("body", {})
    return r.get("results"), r.get("pagination", {}).get("totalCount") if isinstance(r.get("pagination"), dict) else r.get("totalCount"), list(r.keys())
out = {}
cities = {"brest-region": ["", "baranovichi", "pinsk", "kobrin", "bereza", "luninec", "pruzhany", "zhabinka"],
          "minsk-region": ["", "borisov", "soligorsk", "molodechno", "zhodino", "sluck", "dzerzhinsk", "zaslavl", "fanipol"],
          "gomel-region": ["", "mozyr", "zhlobin", "svetlogorsk", "rechica", "kalinkovichi"],
          "grodno-region": ["", "lida", "slonim", "volkovysk", "smorgon", "novogrudok"],
          "mogilev-region": ["", "bobrujsk", "gorki", "osipovichi", "krichev"],
          "vitebsk-region": ["", "orsha", "novopolock", "polock", "postavy", "glubokoe"]}
for reg, towns in cities.items():
    for t in towns:
        for kind in ["rent/flat-for-long", "sale/flats", "rent/flat-for-day"]:
            if kind != "rent/flat-for-long" and t not in ("", towns[1]): continue
            u = f"https://realt.by/{reg}/{kind}/" + (f"{t}/" if t else "")
            st, h = get(u); o, tot, flt = objs(h) if h else (None, None, None)
            out[u] = {"st": st, "n": len(o) if o else 0, "total": tot, "towns": sorted({x.get("townName") or "" for x in (o or [])})[:6], "f": str(flt)[:150]}
            time.sleep(0.5)
for q in ["", "?sortType=createdAt", "?sortType=createdAt&sortDirection=desc", "?sort=createdAt", "?sortType=updatedAt", "?sortType=raiseDate"]:
    for kind in ["rent/flat-for-long", "rent/flat-for-day"]:
        u = f"https://realt.by/{kind}/{q}"
        st, h = get(u); o, tot, _ = objs(h) if h else (None, None, None)
        out[u] = {"st": st, "total": tot, "created": [x.get("createdAt", "")[:16] for x in (o or [])[:8]], "raise": [str(x.get("raiseDate", ""))[:16] for x in (o or [])[:5]], "codes": [x.get("code") for x in (o or [])[:5]]}
st, h = get("https://realt.by/brest-region/rent-flat-for-long/object/4266607/")
o = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', h, re.S)
out["detail_keys"] = list(json.loads(o.group(1))["props"]["pageProps"].keys()) if o else st
if o:
    s = o.group(1); i = s.find('"description"'); out["detail_desc"] = s[i:i+300]
json.dump(out, open("out/realt_summary.json", "w"), ensure_ascii=False, indent=1)
