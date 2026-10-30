import os

BOT_TOKEN = os.environ["BOT_TOKEN"]
DB_PATH = os.getenv("DB_PATH", "/data/flats.db")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "90"))
ALLOWED_USERS = {int(x) for x in os.getenv("ALLOWED_USERS", "").replace(" ", "").split(",") if x}
MAX_NOTIFY_PER_CHECK = 10
