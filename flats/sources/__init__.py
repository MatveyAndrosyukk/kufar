"""Каждый источник возвращает список нормализованных объявлений (dict):
uid, source, title, byn, usd, unit, city, region, address, params, desc, images, link, created
"""
from . import flatly, kufar, realt

SOURCES = {"kufar": kufar, "realt": realt, "flatly": flatly}
NAMES = {"kufar": "Kufar", "realt": "Realt", "flatly": "Flatly"}
BADGES = {"kufar": "🟢 Kufar", "realt": "🟡 Realt", "flatly": "🔵 Flatly"}
