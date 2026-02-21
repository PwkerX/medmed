import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import db
from utils import LESSONS, TERMS, NOTIF_LABELS

logger = logging.getLogger(__name__)
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))
SEARCH = 3


async def route_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text

    # ── حالت‌های فعال ──
    mode = context.user_data.get('mode', '')
    awaiting = context.user_data.get('awaiting_search', False)

    if awaiting or mode == 'search':
        from search import search_handler
        return await search_handler(update, context)

    if mode == 'add_question':
        context.user_data['search_mode'] = 'add_question'
        from search import search_handler
        return await search_handler(update, context)

    if mode == 'add_schedule':
        context.user_data['search_mode'] = 'add_schedule'
        from search import search_handler
        return await search_handler(update, context)

    if mode == 'broadcast':
        from admin import admin_broadcast_handler
        return await admin_broadcast_handler(update, context)

    # ── بررسی کاربر ──
    user = await db.get_user(uid)
    if not user:
        await update.message.reply_text("لطفاً /start را بزنید.")
        return

    if not user.get('approved') and uid != ADMIN_ID:
        await update.message.reply_text("⏳ دسترسی شما هنوز تأیید نشده است.")
        return

    # ── مسیریابی کیبورد ──
    if text == "🩺 داشبورد":
        from dashboard import build_dashboard_text
        t, kb = await build_dashboard_text(uid)
        await update.message.reply_text(t, parse_mode='HTML', reply_markup=kb)

    elif text == "📚 منابع":
        keyboard = []
        for i in range(0, len(TERMS), 2):
            row = [InlineKeyboardButton(TERMS[i], callback_data=f'resources:term:{TERMS[i]}'[:64])]
            if i + 1 < len(TERMS):
                row.append(InlineKeyboardButton(TERMS[i+1], callback_data=f'resources:term:{TERMS[i+1]}'[:64]))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔍 جستجو", callback_data='resources:search')])
        await update.message.reply_text("📚 <b>منابع درسی</b>", parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif text == "🎥 آرشیو":
        keyboard = []
        for i in range(0, len(LESSONS), 2):
            row = [InlineKeyboardButton(LESSONS[i], callback_data=f'archive:lesson:{LESSONS[i]}'[:64])]
            if i + 1 < len(LESSONS):
                row.append(InlineKeyboardButton(LESSONS[i+1], callback_data=f'archive:lesson:{LESSONS[i+1]}'[:64]))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("📅 آخرین کلاس‌ها", callback_data='archive:recent')])
        await update.message.reply_text("🎥 <b>آرشیو کلاس‌ها</b>", parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif text == "🧪 بانک سوال":
        keyboard = [
            [InlineKeyboardButton("📖 تمرین آزاد", callback_data='questions:free')],
            [InlineKeyboardButton("⚡ تمرین نقاط ضعف", callback_data='questions:weak')],
            [InlineKeyboardButton("📝 شبیه‌سازی امتحان", callback_data='questions:exam')],
            [InlineKeyboardButton("🔴 سوالات سخت", callback_data='questions:hard')],
            [InlineKeyboardButton("📊 آمار", callback_data='questions:stats')]
        ]
        await update.message.reply_text("🧪 <b>بانک سوال</b>", parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif text == "📅 برنامه":
        keyboard = [
            [InlineKeyboardButton("📖 کلاس‌ها", callback_data='schedule:type:class'),
             InlineKeyboardButton("📝 امتحانات", callback_data='schedule:type:exam')],
            [InlineKeyboardButton("🔄 جبرانی", callback_data='schedule:type:makeup'),
             InlineKeyboardButton("📅 هفتگی", callback_data='schedule:week')],
            [InlineKeyboardButton("⏳ امتحانات نزدیک", callback_data='schedule:upcoming')]
        ]
        await update.message.reply_text("📅 <b>برنامه و امتحانات</b>", parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif text == "📊 آمار من":
        keyboard = [
            [InlineKeyboardButton("📊 آمار کلی", callback_data='stats:main')],
            [InlineKeyboardButton("📅 فعالیت هفتگی", callback_data='stats:weekly'),
             InlineKeyboardButton("⚡ نقاط ضعف", callback_data='stats:weak')]
        ]
        await update.message.reply_text("📊 <b>آمار من</b>", parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif text == "🔔 اعلان‌ها":
        user_data = await db.get_user(uid)
        s = user_data.get('notification_settings', {}) if user_data else {}
        keyboard = []
        for key, label in NOTIF_LABELS.items():
            icon = "✅" if s.get(key, True) else "❌"
            keyboard.append([InlineKeyboardButton(f"{icon} {label}", callback_data=f'notif:toggle:{key}')])
        keyboard.append([
            InlineKeyboardButton("✅ همه روشن", callback_data='notif:all_on'),
            InlineKeyboardButton("❌ همه خاموش", callback_data='notif:all_off')
        ])
        await update.message.reply_text("🔔 <b>تنظیمات اعلان‌ها</b>", parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif text == "🔍 جستجو":
        context.user_data['search_mode'] = 'resources'
        context.user_data['awaiting_search'] = True
        await update.message.reply_text("🔍 کلمه کلیدی را وارد کنید:")
        return SEARCH

    elif text == "👨‍⚕️ پنل ادمین" and uid == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("📊 آمار سیستم", callback_data='admin:stats')],
            [InlineKeyboardButton("👥 کاربران", callback_data='admin:users'),
             InlineKeyboardButton("⏳ تأیید", callback_data='admin:pending')],
            [InlineKeyboardButton("📚 آپلود منبع", callback_data='admin:upload_resource'),
             InlineKeyboardButton("🎥 آپلود ویدیو", callback_data='admin:upload_video')],
            [InlineKeyboardButton("➕ سوال جدید", callback_data='admin:add_question'),
             InlineKeyboardButton("⏳ تأیید سوالات", callback_data='admin:pending_q')],
            [InlineKeyboardButton("📅 برنامه جدید", callback_data='admin:add_schedule')],
            [InlineKeyboardButton("📢 ارسال همگانی", callback_data='admin:broadcast')]
        ]
        await update.message.reply_text("👨‍⚕️ <b>پنل مدیریت</b>", parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard))
