import os

BOT_TOKEN = os.environ["BOT_TOKEN"]
DB_PATH = os.getenv("DB_PATH", "/data/bot.db")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))  # секунд между проверками
# Список Telegram ID через запятую, кому разрешён бот. Пусто — всем.
ALLOWED_USERS = {int(x) for x in os.getenv("ALLOWED_USERS", "").replace(" ", "").split(",") if x}
MAX_NOTIFY_PER_CHECK = 10
