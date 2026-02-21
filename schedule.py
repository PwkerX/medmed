import os
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db

logger = logging.getLogger(__name__)
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))


async def schedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    parts = data.split(':')
    action = parts[1] if len(parts) > 1 else 'main'

    if action == 'main':
        keyboard = [
            [InlineKeyboardButton("📖 کلاس‌ها", callback_data='schedule:type:class'),
             InlineKeyboardButton("📝 امتحانات", callback_data='schedule:type:exam')],
            [InlineKeyboardButton("🔄 جبرانی", callback_data='schedule:type:makeup'),
             InlineKeyboardButton("📅 برنامه هفتگی", callback_data='schedule:week')],
            [InlineKeyboardButton("⏳ امتحانات نزدیک", callback_data='schedule:upcoming')]
        ]
        await query.edit_message_text(
            "📅 <b>برنامه و امتحانات</b>",
            parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif action == 'type':
        stype = parts[2]
        names = {'class': '📖 کلاس‌ها', 'exam': '📝 امتحانات', 'makeup': '🔄 جبرانی'}
        items = await db.get_schedules(stype=stype)
        await _show_schedule_list(query, items, names.get(stype, stype))

    elif action == 'week':
        today = datetime.now()
        from datetime import timedelta
        week_end = (today + timedelta(days=7)).strftime('%Y-%m-%d')
        today_str = today.strftime('%Y-%m-%d')
        all_items = await db.get_schedules(upcoming=True)
        items = [i for i in all_items if i.get('date', '') <= week_end]
        await _show_schedule_list(query, items, "📅 برنامه ۷ روز آینده")

    elif action == 'upcoming':
        items = await db.upcoming_exams(14)
        await _show_schedule_list(query, items, "⏳ امتحانات ۱۴ روز آینده")


async def _show_schedule_list(query, items, title):
    if not items:
        await query.edit_message_text(
            f"{title}\n\n❌ موردی ثبت نشده است.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data='schedule:main')]])
        )
        return

    text = f"{title}\n━━━━━━━━━━━━━━━━\n\n"
    type_icons = {'class': '📖', 'exam': '📝', 'makeup': '🔄'}

    for s in items:
        icon = type_icons.get(s.get('type', ''), '📌')
        try:
            d = datetime.strptime(s['date'], '%Y-%m-%d')
            days = (d - datetime.now()).days
            if days == 0: days_str = " ⚠️ امروز!"
            elif days == 1: days_str = " ⏰ فردا!"
            elif days < 0: days_str = f" ({abs(days)} روز پیش)"
            else: days_str = f" ({days} روز دیگر)"
        except:
            days_str = ''

        text += (
            f"{icon} <b>{s.get('lesson','')}</b>{days_str}\n"
            f"   👨‍🏫 {s.get('teacher','')} | ⏰ {s.get('date','')} {s.get('time','')}\n"
            f"   📍 {s.get('location','')}\n"
        )
        if s.get('notes'):
            text += f"   📝 {s['notes']}\n"
        text += "\n"

    await query.edit_message_text(
        text, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data='schedule:main')]])
    )
