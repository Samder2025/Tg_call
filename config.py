import os

# ====================== إعدادات البوت ======================
# يتم قراءة هذه القيم من متغيرات البيئة (Environment Variables)
# إذا لم توجد، تُستخدم القيم الافتراضية الموضحة أدناه

BOT_TOKEN = os.getenv("BOT_TOKEN", "948954784:AAHbcsz-flD6ekzT5i2IN6MorYnoY4EGsPI")
API_ID = int(os.getenv("API_ID", "23269382"))
API_HASH = os.getenv("API_HASH", "fe19c565fb4378bd5128885428ff8e26")

# ====================== مجلدات التخزين ======================
SESSIONS_DIR = "sessions"
DATA_DIR = "data"

# إنشاء المجلدات إذا لم تكن موجودة
os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
