"""
بخش علوم پایه — دانشجو
ساختار: ترم → درس → جلسه → محتوا
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db

logger = logging.getLogger(__name__)

TERMS = ['ترم ۱', 'ترم ۲', 'ترم ۳', 'ترم ۴', 'ترم ۵']

CONTENT_ICONS = {
    'video': '🎥 ویدیو کلاس',
    'ppt': '📊 پاورپوینت',
    'pdf': '📄 جزوه PDF',
    'note': '📝 نکات',
    'test': '🧪 تست',
    'voice': '🎙 ویس استاد'
}


async def basic_science_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    parts = data.split(':')
    action = parts[1] if len(parts) > 1 else 'main'

    if action == 'main':
        await _show_terms(query)

    elif action == 'term':
        idx = int(parts[2])
        term = TERMS[idx]
        context.user_data['bs_term'] = term
        await _show_lessons(query, context, term)

    elif action == 'lesson':
        lesson_id = parts[2]
        context.user_data['bs_lesson_id'] = lesson_id
        await _show_sessions(query, context, lesson_id)

    elif action == 'session':
        session_id = parts[2]
        context.user_data['bs_session_id'] = session_id
        await _show_content(query, context, session_id)

    elif data.startswith('bs_dl:'):
        # دانلود محتوا
        content_id = parts[1]
        await _download_content(query, context, content_id, update.effective_user.id)


async def _show_terms(query):
    keyboard = []
    for i in range(0, len(TERMS), 2):
        row = [InlineKeyboardButton(f"📘 {TERMS[i]}", callback_data=f'bs:term:{i}')]
        if i + 1 < len(TERMS):
            row.append(InlineKeyboardButton(f"📘 {TERMS[i+1]}", callback_data=f'bs:term:{i+1}'))
        keyboard.append(row)

    await query.edit_message_text(
        "🔬 <b>علوم پایه پزشکی</b>\n\n"
        "━━━━━━━━━━━━━━━━\n"
        "ترم تحصیلی خود را انتخاب کنید:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _show_lessons(query, context, term):
    lessons = await db.bs_get_lessons(term)

    if not lessons:
        await query.edit_message_text(
            f"📘 <b>{term}</b>\n\n"
            "❌ هنوز درسی برای این ترم تعریف نشده.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 بازگشت", callback_data='bs:main')
            ]])
        )
        return

    keyboard = []
    for l in lessons:
        lid = str(l['_id'])
        teacher_txt = f" | {l.get('teacher','')}" if l.get('teacher') else ''
        keyboard.append([InlineKeyboardButton(
            f"📖 {l['name']}{teacher_txt}",
            callback_data=f'bs:lesson:{lid}'
        )])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='bs:main')])

    await query.edit_message_text(
        f"📘 <b>{term}</b>\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"درس مورد نظر را انتخاب کنید:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _show_sessions(query, context, lesson_id):
    lesson = await db.bs_get_lesson(lesson_id)
    if not lesson:
        await query.answer("❌ درس پیدا نشد!", show_alert=True)
        return

    sessions = await db.bs_get_sessions(lesson_id)
    term = context.user_data.get('bs_term', '')

    if not sessions:
        await query.edit_message_text(
            f"📖 <b>{lesson['name']}</b>\n\n"
            "❌ هنوز جلسه‌ای ثبت نشده.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 بازگشت", callback_data=f'bs:term:{TERMS.index(term) if term in TERMS else 0}')
            ]])
        )
        return

    keyboard = []
    for s in sessions:
        sid = str(s['_id'])
        keyboard.append([InlineKeyboardButton(
            f"📌 جلسه {s['number']} — {s.get('topic','')[:30]}",
            callback_data=f'bs:session:{sid}'
        )])
    term_idx = TERMS.index(term) if term in TERMS else 0
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f'bs:term:{term_idx}')])

    await query.edit_message_text(
        f"📖 <b>{lesson['name']}</b>\n"
        f"👨‍🏫 {lesson.get('teacher','')} | {term}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"جلسه مورد نظر را انتخاب کنید:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _show_content(query, context, session_id):
    session = await db.bs_get_session(session_id)
    if not session:
        await query.answer("❌ جلسه پیدا نشد!", show_alert=True)
        return

    contents = await db.bs_get_content(session_id)
    lesson_id = context.user_data.get('bs_lesson_id', '')

    if not contents:
        await query.edit_message_text(
            f"📌 <b>جلسه {session['number']}</b>\n"
            f"📚 {session.get('topic','')}\n"
            f"👨‍🏫 {session.get('teacher','')}\n\n"
            "❌ محتوایی برای این جلسه بارگذاری نشده.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 بازگشت", callback_data=f'bs:lesson:{lesson_id}')
            ]])
        )
        return

    # گروه‌بندی بر اساس نوع
    by_type = {}
    for c in contents:
        t = c.get('type', 'pdf')
        by_type.setdefault(t, []).append(c)

    keyboard = []
    for ctype, items in by_type.items():
        icon_label = CONTENT_ICONS.get(ctype, '📎 فایل')
        for item in items:
            cid = str(item['_id'])
            desc = item.get('description', '')[:20]
            label = f"{icon_label}" + (f" — {desc}" if desc else '')
            keyboard.append([InlineKeyboardButton(label, callback_data=f'bs_dl:{cid}')])

    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f'bs:lesson:{lesson_id}')])

    content_list = '\n'.join(f"  {CONTENT_ICONS.get(t,'📎')} {len(v)} فایل" for t, v in by_type.items())

    await query.edit_message_text(
        f"📌 <b>جلسه {session['number']}</b>\n"
        f"📚 موضوع: {session.get('topic','')}\n"
        f"👨‍🏫 استاد: {session.get('teacher','')}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"محتوای موجود:\n{content_list}\n\n"
        f"برای دانلود روی محتوا کلیک کنید:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _download_content(query, context, content_id, uid):
    item = await db.bs_get_content_item(content_id)
    if not item:
        await query.answer("❌ فایل پیدا نشد!", show_alert=True)
        return

    await db.bs_inc_download(content_id, uid)
    ctype = item.get('type', 'pdf')
    caption = (
        f"{CONTENT_ICONS.get(ctype,'📎')}\n"
        f"📝 {item.get('description','')}\n"
        f"📥 {item.get('downloads',0)} دانلود"
    )

    try:
        if ctype == 'video':
            await query.message.reply_video(item['file_id'], caption=caption, parse_mode='HTML')
        elif ctype == 'voice':
            await query.message.reply_audio(item['file_id'], caption=caption, parse_mode='HTML')
        else:
            await query.message.reply_document(item['file_id'], caption=caption, parse_mode='HTML')
    except:
        try:
            await query.message.reply_document(item['file_id'], caption=caption, parse_mode='HTML')
        except:
            await query.answer("❌ خطا در ارسال فایل!", show_alert=True)
