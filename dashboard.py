import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db

ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))


def progress_bar(pct, length=12):
    filled = int(pct / 100 * length)
    return '▓' * filled + '░' * (length - filled)


async def build_dashboard_text(uid):
    user = await db.get_user(uid)
    if not user:
        return "❌ کاربر پیدا نشد.", None

    stats = await db.user_stats(uid)
    new_res = await db.new_resources_count(7)
    exams = await db.upcoming_exams(7)

    exam_line = "❌ امتحانی نزدیک نیست"
    if exams:
        e = exams[0]
        try:
            d = datetime.strptime(e['date'], '%Y-%m-%d')
            days = (d - datetime.now()).days
            exam_line = f"⚠️ {e['lesson']} — {'امروز!' if days == 0 else f'{days} روز دیگر'}"
        except:
            exam_line = f"📝 {e.get('lesson', '')}"

    bar = progress_bar(stats['percentage'])
    weak = ', '.join(stats['weak_topics'][:3]) if stats['weak_topics'] else 'ندارید 🎉'

    text = (
        f"🩺 <b>داشبورد — {user['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━\n\n"
        f"📊 آمادگی: {bar} <b>{stats['percentage']}%</b>\n\n"
        f"📥 دانلود: <b>{stats['downloads']}</b>  "
        f"🧪 سوال: <b>{stats['total_answers']}</b>  "
        f"✅ صحیح: <b>{stats['correct_answers']}</b>\n"
        f"📚 منابع جدید این هفته: <b>{new_res}</b>\n"
        f"🔥 فعالیت هفتگی: <b>{stats['week_activity']}</b>\n\n"
        f"⏳ <b>امتحان نزدیک:</b> {exam_line}\n"
        f"⚡ <b>نقاط ضعف:</b> {weak}"
    )

    keyboard = [
        [InlineKeyboardButton("🔄 بروزرسانی", callback_data='dashboard:refresh'),
         InlineKeyboardButton("📊 آمار کامل", callback_data='stats:main')],
        [InlineKeyboardButton("🧪 تمرین هوشمند", callback_data='questions:weak'),
         InlineKeyboardButton("🔔 اعلان‌ها", callback_data='notif:main')]
    ]
    if uid == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("👨‍⚕️ پنل ادمین", callback_data='admin:main')])

    return text, InlineKeyboardMarkup(keyboard)


async def dashboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    text, kb = await build_dashboard_text(uid)
    try:
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=kb)
    except:
        await update.effective_message.reply_text(text, parse_mode='HTML', reply_markup=kb)
