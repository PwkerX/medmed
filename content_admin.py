"""
پنل ادمین محتوا
قابلیت‌ها: مدیریت درس‌ها، جلسات، و محتوای علوم پایه
"""
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import db

logger = logging.getLogger(__name__)
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))

TERMS = ['ترم ۱', 'ترم ۲', 'ترم ۳', 'ترم ۴', 'ترم ۵']
CONTENT_TYPES = [
    ('video', '🎥 ویدیو کلاس'),
    ('ppt', '📊 پاورپوینت'),
    ('pdf', '📄 جزوه PDF'),
    ('note', '📝 نکات'),
    ('test', '🧪 تست'),
    ('voice', '🎙 ویس استاد'),
]

CA_WAITING_FILE = 50
CA_WAITING_TEXT = 51


async def content_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    data = query.data
    parts = data.split(':')
    action = parts[1] if len(parts) > 1 else 'main'

    # بررسی دسترسی
    if not await db.is_content_admin(uid):
        await query.answer("❌ دسترسی ندارید!", show_alert=True)
        return

    if action == 'main':
        await _ca_main(query)

    # ── مدیریت درس‌ها ──
    elif action == 'terms':
        await _ca_show_terms(query)

    elif action == 'term':
        idx = int(parts[2])
        term = TERMS[idx]
        context.user_data['ca_term'] = term
        context.user_data['ca_term_idx'] = idx
        await _ca_show_lessons(query, context, term)

    elif action == 'add_lesson_prompt':
        idx = int(parts[2])
        context.user_data['ca_term_idx'] = idx
        context.user_data['ca_term'] = TERMS[idx]
        context.user_data['ca_mode'] = 'add_lesson'
        await query.edit_message_text(
            f"➕ <b>درس جدید — {TERMS[idx]}</b>\n\n"
            "نام درس و نام استاد را بنویسید:\n"
            "<i>مثال: زبان پیش ۱, دکتر احمدی</i>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ لغو", callback_data=f'ca:term:{idx}')
            ]])
        )

    elif action == 'del_lesson':
        lesson_id = parts[2]
        lesson = await db.bs_get_lesson(lesson_id)
        if lesson:
            await query.edit_message_text(
                f"⚠️ <b>حذف درس</b>\n\n"
                f"آیا مطمئنید که می‌خواهید درس «{lesson['name']}» و تمام جلسات و محتوای آن را حذف کنید؟",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🗑 بله، حذف کن", callback_data=f'ca:confirm_del_lesson:{lesson_id}')],
                    [InlineKeyboardButton("❌ لغو", callback_data=f'ca:term:{context.user_data.get("ca_term_idx",0)}')]
                ])
            )

    elif action == 'confirm_del_lesson':
        lesson_id = parts[2]
        lesson = await db.bs_get_lesson(lesson_id)
        name = lesson.get('name','') if lesson else ''
        await db.bs_delete_lesson(lesson_id)
        idx = context.user_data.get('ca_term_idx', 0)
        await query.edit_message_text(
            f"✅ درس «{name}» و تمام محتوای آن حذف شد.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 بازگشت", callback_data=f'ca:term:{idx}')
            ]])
        )

    # ── مدیریت جلسات ──
    elif action == 'lesson':
        lesson_id = parts[2]
        context.user_data['ca_lesson_id'] = lesson_id
        await _ca_show_sessions(query, context, lesson_id)

    elif action == 'add_session_prompt':
        lesson_id = parts[2]
        context.user_data['ca_lesson_id'] = lesson_id
        context.user_data['ca_mode'] = 'add_session'
        lesson = await db.bs_get_lesson(lesson_id)
        sessions = await db.bs_get_sessions(lesson_id)
        next_num = len(sessions) + 1
        context.user_data['ca_next_session'] = next_num
        await query.edit_message_text(
            f"➕ <b>جلسه جدید — {lesson.get('name','')}</b>\n\n"
            f"شماره جلسه پیشنهادی: <b>{next_num}</b>\n\n"
            "اطلاعات جلسه را بنویسید:\n"
            "<i>فرمت: شماره, موضوع, نام استاد</i>\n"
            "<i>مثال: 3, فعل‌های بی‌قاعده, دکتر محمدی</i>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ لغو", callback_data=f'ca:lesson:{lesson_id}')
            ]])
        )

    elif action == 'del_session':
        session_id = parts[2]
        session = await db.bs_get_session(session_id)
        if session:
            await query.edit_message_text(
                f"⚠️ <b>حذف جلسه {session.get('number','')}</b>\n\n"
                f"موضوع: {session.get('topic','')}\n\n"
                "آیا مطمئنید؟",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🗑 حذف", callback_data=f'ca:confirm_del_session:{session_id}')],
                    [InlineKeyboardButton("❌ لغو", callback_data=f'ca:lesson:{context.user_data.get("ca_lesson_id","")}')]
                ])
            )

    elif action == 'confirm_del_session':
        session_id = parts[2]
        await db.bs_delete_session(session_id)
        lesson_id = context.user_data.get('ca_lesson_id', '')
        await query.edit_message_text(
            "✅ جلسه و محتوای آن حذف شد.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 بازگشت", callback_data=f'ca:lesson:{lesson_id}')
            ]])
        )

    # ── مدیریت محتوا ──
    elif action == 'session':
        session_id = parts[2]
        context.user_data['ca_session_id'] = session_id
        await _ca_show_session_content(query, context, session_id)

    elif action == 'upload_content':
        session_id = parts[2]
        context.user_data['ca_session_id'] = session_id
        context.user_data['ca_mode'] = 'select_content_type'
        keyboard = [[InlineKeyboardButton(label, callback_data=f'ca:sel_ctype:{session_id}:{ctype}')] for ctype, label in CONTENT_TYPES]
        keyboard.append([InlineKeyboardButton("❌ لغو", callback_data=f'ca:session:{session_id}')])
        await query.edit_message_text(
            "📤 <b>آپلود محتوا</b>\n\nنوع محتوا را انتخاب کنید:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif action == 'sel_ctype':
        session_id = parts[2]
        ctype = parts[3]
        context.user_data['ca_session_id'] = session_id
        context.user_data['ca_content_type'] = ctype
        context.user_data['ca_mode'] = 'waiting_file'
        type_label = dict(CONTENT_TYPES).get(ctype, ctype)
        await query.edit_message_text(
            f"📤 <b>آپلود {type_label}</b>\n\n"
            "فایل را ارسال کنید:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ لغو", callback_data=f'ca:session:{session_id}')
            ]])
        )
        return CA_WAITING_FILE

    elif action == 'del_content':
        content_id = parts[2]
        item = await db.bs_get_content_item(content_id)
        if item:
            ctype = item.get('type','')
            type_label = dict(CONTENT_TYPES).get(ctype, ctype)
            await query.edit_message_text(
                f"⚠️ <b>حذف محتوا</b>\n\nنوع: {type_label}\n\nآیا مطمئنید؟",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🗑 حذف", callback_data=f'ca:confirm_del_content:{content_id}')],
                    [InlineKeyboardButton("❌ لغو", callback_data=f'ca:session:{context.user_data.get("ca_session_id","")}')]
                ])
            )

    elif action == 'confirm_del_content':
        content_id = parts[2]
        await db.bs_delete_content(content_id)
        session_id = context.user_data.get('ca_session_id', '')
        await query.edit_message_text(
            "✅ محتوا حذف شد.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 بازگشت", callback_data=f'ca:session:{session_id}')
            ]])
        )

    # ── FAQ ──
    elif action == 'faq':
        await _ca_faq_manage(query)

    elif action == 'add_faq_prompt':
        context.user_data['ca_mode'] = 'add_faq'
        await query.edit_message_text(
            "➕ <b>سوال متداول جدید</b>\n\n"
            "سوال و جواب را بنویسید:\n"
            "<i>فرمت: سوال | جواب</i>\n"
            "<i>مثال: نحوه دانلود جزوه؟ | روی دکمه دانلود کلیک کنید</i>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ لغو", callback_data='ca:faq')
            ]])
        )

    elif action == 'del_faq':
        fid = parts[2]
        await db.faq_delete(fid)
        await query.edit_message_text(
            "✅ سوال حذف شد.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 بازگشت", callback_data='ca:faq')
            ]])
        )


# ── نمایش پنل ──

async def _ca_main(query):
    keyboard = [
        [InlineKeyboardButton("📘 مدیریت درس‌های ترم", callback_data='ca:terms')],
        [InlineKeyboardButton("❓ مدیریت سوالات متداول", callback_data='ca:faq')],
    ]
    await query.edit_message_text(
        "🎓 <b>پنل ادمین محتوا</b>\n\n"
        "از این پنل می‌توانید محتوای علوم پایه را مدیریت کنید:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _ca_show_terms(query):
    keyboard = []
    for i in range(0, len(TERMS), 2):
        row = [InlineKeyboardButton(f"📘 {TERMS[i]}", callback_data=f'ca:term:{i}')]
        if i + 1 < len(TERMS):
            row.append(InlineKeyboardButton(f"📘 {TERMS[i+1]}", callback_data=f'ca:term:{i+1}'))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='ca:main')])
    await query.edit_message_text(
        "📘 <b>انتخاب ترم</b>\n\nترم را برای مدیریت درس‌ها انتخاب کنید:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _ca_show_lessons(query, context, term):
    lessons = await db.bs_get_lessons(term)
    idx = context.user_data.get('ca_term_idx', 0)
    keyboard = []
    for l in lessons:
        lid = str(l['_id'])
        keyboard.append([
            InlineKeyboardButton(f"📖 {l['name']}", callback_data=f'ca:lesson:{lid}'),
            InlineKeyboardButton("🗑", callback_data=f'ca:del_lesson:{lid}')
        ])
    keyboard.append([InlineKeyboardButton(f"➕ درس جدید", callback_data=f'ca:add_lesson_prompt:{idx}')])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='ca:terms')])
    await query.edit_message_text(
        f"📘 <b>{term}</b> — {len(lessons)} درس\n\nبرای ویرایش روی درس کلیک کنید:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _ca_show_sessions(query, context, lesson_id):
    lesson = await db.bs_get_lesson(lesson_id)
    sessions = await db.bs_get_sessions(lesson_id)
    idx = context.user_data.get('ca_term_idx', 0)
    keyboard = []
    for s in sessions:
        sid = str(s['_id'])
        keyboard.append([
            InlineKeyboardButton(f"📌 جلسه {s['number']} — {s.get('topic','')[:20]}", callback_data=f'ca:session:{sid}'),
            InlineKeyboardButton("🗑", callback_data=f'ca:del_session:{sid}')
        ])
    keyboard.append([InlineKeyboardButton("➕ جلسه جدید", callback_data=f'ca:add_session_prompt:{lesson_id}')])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f'ca:term:{idx}')])
    name = lesson.get('name','') if lesson else ''
    await query.edit_message_text(
        f"📖 <b>{name}</b> — {len(sessions)} جلسه\n\nمدیریت جلسات:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _ca_show_session_content(query, context, session_id):
    session = await db.bs_get_session(session_id)
    contents = await db.bs_get_content(session_id)
    lesson_id = context.user_data.get('ca_lesson_id', '')

    keyboard = []
    ICONS = dict(CONTENT_TYPES)
    for c in contents:
        cid = str(c['_id'])
        ctype = c.get('type','pdf')
        label = f"{ICONS.get(ctype,'📎')} {c.get('description','')[:20]}"
        keyboard.append([
            InlineKeyboardButton(label, callback_data=f'ca:del_content:{cid}'),
            InlineKeyboardButton("🗑", callback_data=f'ca:del_content:{cid}')
        ])
    keyboard.append([InlineKeyboardButton("📤 آپلود محتوا", callback_data=f'ca:upload_content:{session_id}')])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f'ca:lesson:{lesson_id}')])

    snum = session.get('number','') if session else ''
    stopic = session.get('topic','') if session else ''
    await query.edit_message_text(
        f"📌 <b>جلسه {snum} — {stopic}</b>\n\n"
        f"{len(contents)} فایل موجود\nبرای حذف روی فایل کلیک کنید:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _ca_faq_manage(query):
    faqs = await db.faq_get_all()
    keyboard = []
    for f in faqs[:10]:
        fid = str(f['_id'])
        q_short = f.get('question','')[:30]
        keyboard.append([
            InlineKeyboardButton(f"❓ {q_short}", callback_data=f'ca:del_faq:{fid}'),
            InlineKeyboardButton("🗑", callback_data=f'ca:del_faq:{fid}')
        ])
    keyboard.append([InlineKeyboardButton("➕ سوال جدید", callback_data='ca:add_faq_prompt')])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='ca:main')])
    await query.edit_message_text(
        f"❓ <b>سوالات متداول</b> — {len(faqs)} سوال",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ── هندلر فایل برای ادمین محتوا ──

async def ca_file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not await db.is_content_admin(uid):
        return

    mode = context.user_data.get('ca_mode', '')
    if mode != 'waiting_file':
        return

    file_obj = (update.message.document or update.message.video or
                update.message.audio or update.message.voice)
    if not file_obj:
        await update.message.reply_text("❌ فایل معتبر ارسال کنید.")
        return CA_WAITING_FILE

    file_id = file_obj.file_id
    session_id = context.user_data.get('ca_session_id', '')
    ctype = context.user_data.get('ca_content_type', 'pdf')

    context.user_data['ca_pending_file'] = file_id
    context.user_data['ca_mode'] = 'waiting_description'

    await update.message.reply_text(
        "✅ فایل دریافت شد!\n\n"
        "توضیح کوتاهی بنویسید (یا - بزنید برای بدون توضیح):\n"
        "<i>مثال: جلسه اول — فعل‌های بی‌قاعده</i>",
        parse_mode='HTML'
    )
    return CA_WAITING_TEXT


async def ca_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not await db.is_content_admin(uid):
        return

    mode = context.user_data.get('ca_mode', '')
    text = update.message.text.strip()

    if mode == 'add_lesson':
        parts = [p.strip() for p in text.split(',')]
        name = parts[0]
        teacher = parts[1] if len(parts) > 1 else ''
        term = context.user_data.get('ca_term', '')
        result = await db.bs_add_lesson(term, name, teacher)
        if result:
            await update.message.reply_text(
                f"✅ درس «{name}» به {term} اضافه شد!",
            )
        else:
            await update.message.reply_text("⚠️ این درس قبلاً وجود دارد.")
        context.user_data['ca_mode'] = ''

    elif mode == 'add_session':
        parts = [p.strip() for p in text.split(',')]
        if len(parts) < 2:
            await update.message.reply_text("❌ فرمت اشتباه. مثال: 3, فعل‌های بی‌قاعده, دکتر احمدی")
            return CA_WAITING_TEXT
        try:
            number = int(parts[0])
        except:
            number = context.user_data.get('ca_next_session', 1)
        topic = parts[1]
        teacher = parts[2] if len(parts) > 2 else ''
        lesson_id = context.user_data.get('ca_lesson_id', '')
        await db.bs_add_session(lesson_id, number, topic, teacher)
        await update.message.reply_text(f"✅ جلسه {number} — «{topic}» اضافه شد!")
        context.user_data['ca_mode'] = ''

    elif mode == 'waiting_description':
        description = '' if text == '-' else text
        file_id = context.user_data.get('ca_pending_file', '')
        session_id = context.user_data.get('ca_session_id', '')
        ctype = context.user_data.get('ca_content_type', 'pdf')
        await db.bs_add_content(session_id, ctype, file_id, description)
        type_label = dict(CONTENT_TYPES).get(ctype, ctype)
        await update.message.reply_text(f"✅ {type_label} اضافه شد!")
        context.user_data['ca_mode'] = ''

    elif mode == 'add_faq':
        if '|' not in text:
            await update.message.reply_text("❌ فرمت اشتباه. مثال: سوال؟ | جواب")
            return CA_WAITING_TEXT
        q_part, a_part = text.split('|', 1)
        await db.faq_add(q_part.strip(), a_part.strip())
        await update.message.reply_text(f"✅ سوال متداول اضافه شد!")
        context.user_data['ca_mode'] = ''
