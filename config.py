import os

# إعدادات البوت
BOT_TOKEN = os.environ.get("BOT_TOKEN", "948954784:AAHbcsz-flD6ekzT5i2IN6MorYnoY4EGsPI")
API_ID = "int(os.environ.get("API_ID", 23269382))"
API_HASH = os.environ.get("API_HASH", "fe19c565fb4378bd5128885428ff8e26")

# مجلدات التخزين
SESSIONS_DIR = "sessions"
DATA_DIR = "data"

os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
