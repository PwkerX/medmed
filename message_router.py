import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import db
from utils import NOTIF_LABELS

logger = logging.getLogger(__name__)
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))
SEARCH = 3


async def route_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text

    # ── حالت‌های فعال ادمین اصلی ──
    if uid == ADMIN_ID:
        mode = context.user_data.get('mode', '')
        if mode in ('add_lesson', 'add_topic', 'edit_user'):
            from admin import handle_admin_text
            handled = await handle_admin_text(update, context)
            if handled:
                return
        if mode == 'broadcast':
            from admin import admin_broadcast_handler
            return await admin_broadcast_handler(update, context)

    # ── حالت ساخت سوال (همه کاربران) ──
    mode_all = context.user_data.get('mode', '')
    if mode_all == 'creating_question':
        from questions import handle_create_question_steps
        return await handle_create_question_steps(update, context)

    # ── حالت ادمین محتوا ──
    ca_mode = context.user_data.get('ca_mode', '')
    if ca_mode in ('add_lesson', 'add_session', 'waiting_description', 'add_faq'):
        if await db.is_content_admin(uid):
            from content_admin import ca_text_handler
            return await ca_text_handler(update, context)

    # ── جستجو ──
    awaiting = context.user_data.get('awaiting_search', False)
    if awaiting:
        from search import search_handler
        return await search_handler(update, context)

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

    elif text == "🔬 علوم پایه":
        keyboard = []
        terms = ['ترم ۱', 'ترم ۲', 'ترم ۳', 'ترم ۴', 'ترم ۵']
        for i in range(0, len(terms), 2):
            row = [InlineKeyboardButton(f"📘 {terms[i]}", callback_data=f'bs:term:{i}')]
            if i + 1 < len(terms):
                row.append(InlineKeyboardButton(f"📘 {terms[i+1]}", callback_data=f'bs:term:{i+1}'))
            keyboard.append(row)
        await update.message.reply_text(
            "🔬 <b>علوم پایه پزشکی</b>\n\n"
            "━━━━━━━━━━━━━━━━\n"
            "ترم تحصیلی خود را انتخاب کنید:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif text == "🧪 بانک سوال":
        keyboard = [
            [InlineKeyboardButton("📁 بانک سوال ادمین (دانلود فایل)", callback_data='questions:file_bank')],
            [InlineKeyboardButton("🧪 تمرین تستی", callback_data='questions:practice')],
            [InlineKeyboardButton("✏️ طراحی سوال", callback_data='questions:create')],
            [InlineKeyboardButton("📊 آمار تمرین من", callback_data='questions:stats')]
        ]
        await update.message.reply_text(
            "🧪 <b>بانک سوال</b>\n\n"
            "📁 <b>بانک ادمین:</b> فایل PDF/عکس\n"
            "🧪 <b>تمرین تستی:</b> سوالات چهارگزینه‌ای\n"
            "✏️ <b>طراحی سوال:</b> سوال بسازید",
            parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

    elif text == "❓ سوالات متداول":
        cats = await db.faq_get_categories()
        keyboard = [[InlineKeyboardButton(f"📂 {c}", callback_data=f'faq:cat:{c}')] for c in cats]
        keyboard.append([InlineKeyboardButton("📋 همه سوالات", callback_data='faq:cat:همه')])
        await update.message.reply_text(
            "❓ <b>سوالات متداول</b>\n\n"
            "━━━━━━━━━━━━━━━━\n"
            "دسته‌بندی مورد نظر را انتخاب کنید:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

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
        context.user_data['search_mode'] = 'bs'
        context.user_data['awaiting_search'] = True
        await update.message.reply_text("🔍 کلمه کلیدی را وارد کنید:")
        return SEARCH

    elif text == "👨‍⚕️ پنل ادمین" and uid == ADMIN_ID:
        await _show_admin_panel(update, uid)

    elif text == "🎓 پنل محتوا" and await db.is_content_admin(uid):
        keyboard = [
            [InlineKeyboardButton("📘 مدیریت درس‌های ترم", callback_data='ca:terms')],
            [InlineKeyboardButton("❓ مدیریت سوالات متداول", callback_data='ca:faq')],
        ]
        await update.message.reply_text(
            "🎓 <b>پنل ادمین محتوا</b>\n\n"
            "از این پنل می‌توانید محتوای علوم پایه را مدیریت کنید:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def _show_admin_panel(update, uid):
    keyboard = [
        [InlineKeyboardButton("📊 آمار سیستم", callback_data='admin:stats')],
        [InlineKeyboardButton("👥 مدیریت کاربران", callback_data='admin:users'),
         InlineKeyboardButton("⏳ تأیید", callback_data='admin:pending')],
        [InlineKeyboardButton("🎓 مدیریت ادمین محتوا", callback_data='admin:content_admins')],
        [InlineKeyboardButton("📘 مدیریت درس‌های ترم", callback_data='ca:terms')],
        [InlineKeyboardButton("❓ مدیریت FAQ", callback_data='ca:faq')],
        [InlineKeyboardButton("🧪 بانک سوال", callback_data='admin:qbank_manage')],
        [InlineKeyboardButton("➕ سوال جدید", callback_data='admin:add_question'),
         InlineKeyboardButton("⏳ تأیید سوالات", callback_data='admin:pending_q')],
        [InlineKeyboardButton("📅 برنامه جدید", callback_data='admin:add_schedule')],
        [InlineKeyboardButton("📢 ارسال همگانی", callback_data='admin:broadcast')]
    ]
    await update.message.reply_text(
        "👨‍⚕️ <b>پنل مدیریت</b>\n\n"
        "به پنل ادمین خوش آمدید:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
