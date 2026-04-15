import os
import asyncio
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ------------------------- إعدادات البوت -------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
PORT = int(os.getenv("PORT", 8080))

# إنشاء تطبيق Flask
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "✅ Bot is running!"

def run_flask():
    """تشغيل خادم Flask في خيط منفصل"""
    flask_app.run(host='0.0.0.0', port=PORT)

# ------------------------- دوال البوت -------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ إضافة حساب", callback_data="add_account")],
        [InlineKeyboardButton("📋 الحسابات المخزنة", callback_data="list_accounts")],
        [InlineKeyboardButton("🗑️ حذف حساب", callback_data="remove_account")],
        [InlineKeyboardButton("🎤 هجوم DoS", callback_data="dos_attack")],
        [InlineKeyboardButton("📊 الحالة", callback_data="status")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🎯 **بوت اختبار المكالمات الجماعية**\n\nاختر من القائمة أدناه:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "add_account":
        await query.edit_message_text("📱 **إضافة حساب جديد**\n\nالرجاء إرسال رقم الهاتف:", parse_mode="Markdown")
    elif data == "list_accounts":
        await query.edit_message_text("📋 **الحسابات المخزنة**\n\nلا توجد حسابات بعد.", parse_mode="Markdown")
    elif data == "remove_account":
        await query.edit_message_text("🗑️ **حذف حساب**\n\nاختر الحساب لحذفه:", parse_mode="Markdown")
    elif data == "dos_attack":
        await query.edit_message_text("🎤 **هجوم DoS**\n\nجاري تجهيز الهجوم...", parse_mode="Markdown")
    elif data == "status":
        await query.edit_message_text("📊 **الحالة**\n\nالبوت يعمل بشكل طبيعي.", parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ أمر غير معروف. استخدم /start")

# ------------------------- إعداد وتشغيل البوت -------------------------
def setup_bot():
    """إعداد البوت وتشغيله"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة المعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # تشغيل البوت باستخدام Polling (السحب المستمر)
    application.run_polling()

# ------------------------- نقطة الدخول الرئيسية -------------------------
if __name__ == "__main__":
    # تشغيل خادم Flask في خيط منفصل
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
    
    # تشغيل البوت
    setup_bot()
