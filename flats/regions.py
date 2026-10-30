"""Области и города. Для каждого города — slug на realt.by (None = на Realt нет такого адреса)."""

# id (rgn Куфара) -> (название, realt-префикс области, {город: realt-slug})
# realt-slug "" — областной центр (корень раздела области)
REGIONS = {
    7: ("Минск", "", {"Минск": ""}),
    1: ("Брестская обл.", "brest-region", {
        "Брест": "", "Барановичи": "baranovichi", "Пинск": "pinsk", "Кобрин": "kobrin",
        "Берёза": "bereza", "Лунинец": "luninec", "Пружаны": "pruzhany", "Жабинка": "zhabinka"}),
    5: ("Минская обл.", None, {
        "Борисов": None, "Солигорск": None, "Молодечно": None, "Жодино": None,
        "Слуцк": None, "Дзержинск": None, "Заславль": None, "Фаниполь": None}),
    2: ("Гомельская обл.", "gomel-region", {
        "Гомель": "", "Мозырь": "mozyr", "Жлобин": "zhlobin", "Светлогорск": "svetlogorsk",
        "Речица": "rechica", "Калинковичи": "kalinkovichi"}),
    3: ("Гродненская обл.", "grodno-region", {
        "Гродно": "", "Лида": "lida", "Слоним": "slonim", "Волковыск": "volkovysk",
        "Сморгонь": "smorgon", "Новогрудок": "novogrudok"}),
    4: ("Могилёвская обл.", "mogilev-region", {
        "Могилёв": "", "Бобруйск": "bobrujsk", "Горки": "gorki", "Осиповичи": "osipovichi", "Кричев": "krichev"}),
    6: ("Витебская обл.", "vitebsk-region", {
        "Витебск": "", "Орша": "orsha", "Новополоцк": "novopolock", "Полоцк": "polock",
        "Поставы": "postavy", "Глубокое": "glubokoe"}),
}

DEALS = {
    "long": ("🏠 Снять надолго", "Kufar + Realt"),
    "day": ("🛏 Посуточно", "Realt + Flatly"),
    "sale": ("🔑 Купить", "Kufar + Realt"),
}
DEAL_SOURCES = {"long": ["kufar", "realt"], "day": ["realt", "flatly"], "sale": ["kufar", "realt"]}

PRICE_PRESETS = {
    ("long", "BYN"): [(0, 600), (600, 900), (900, 1200), (1200, 1600), (1600, 2500)],
    ("long", "USD"): [(0, 200), (200, 300), (300, 400), (400, 550), (550, 800)],
    ("day", "BYN"): [(0, 60), (60, 90), (90, 120), (120, 180), (180, 400)],
    ("day", "USD"): [(0, 20), (20, 30), (30, 40), (40, 60), (60, 130)],
    ("sale", "BYN"): [(0, 100000), (100000, 150000), (150000, 200000), (200000, 300000), (300000, 600000)],
    ("sale", "USD"): [(0, 30000), (30000, 45000), (45000, 60000), (60000, 90000), (90000, 200000)],
}



def norm(s) -> str:
    return (str(s or "")).strip().lower().replace("ё", "е")


def region_cities(region_id) -> list[str]:
    return list(REGIONS[region_id][2].keys()) if region_id in REGIONS else []
