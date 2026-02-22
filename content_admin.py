"""
پنل ادمین محتوا — نسخه کامل با رفرنس‌ها
"""
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
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

    if not await db.is_content_admin(uid):
        await query.answer("❌ دسترسی ندارید!", show_alert=True)
        return

    # ── منوی اصلی ──
    if action == 'main':
        await _ca_main(query)

    # ══ علوم پایه ══
    elif action == 'terms':
        await _ca_show_terms(query)

    elif action == 'term':
        idx = int(parts[2])
        context.user_data['ca_term'] = TERMS[idx]
        context.user_data['ca_term_idx'] = idx
        await _ca_show_lessons(query, context, TERMS[idx])

    elif action == 'add_lesson_prompt':
        idx = int(parts[2])
        context.user_data['ca_term_idx'] = idx
        context.user_data['ca_term'] = TERMS[idx]
        context.user_data['ca_mode'] = 'add_lesson'
        await query.edit_message_text(
            f"➕ <b>درس جدید — {TERMS[idx]}</b>\n\n"
            "نام درس و نام استاد را بنویسید:\n"
            "<i>مثال: زبان پیش ۱, دکتر احمدی</i>\n"
            "<i>(استاد اختیاری است)</i>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data=f'ca:term:{idx}')]])
        )

    elif action == 'del_lesson':
        lesson_id = parts[2]
        lesson = await db.bs_get_lesson(lesson_id)
        if lesson:
            await query.edit_message_text(
                f"⚠️ <b>حذف درس «{lesson['name']}»</b>\n\nتمام جلسات و محتوا هم حذف می‌شود!",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🗑 بله حذف کن", callback_data=f'ca:confirm_del_lesson:{lesson_id}')],
                    [InlineKeyboardButton("❌ لغو", callback_data=f'ca:term:{context.user_data.get("ca_term_idx",0)}')]
                ])
            )

    elif action == 'confirm_del_lesson':
        lesson_id = parts[2]
        lesson = await db.bs_get_lesson(lesson_id)
        name = lesson.get('name', '') if lesson else ''
        await db.bs_delete_lesson(lesson_id)
        idx = context.user_data.get('ca_term_idx', 0)
        await query.edit_message_text(
            f"✅ درس «{name}» حذف شد.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data=f'ca:term:{idx}')]])
        )

    elif action == 'lesson':
        lesson_id = parts[2]
        context.user_data['ca_lesson_id'] = lesson_id
        await _ca_show_sessions(query, context, lesson_id)

    elif action == 'add_session_prompt':
        lesson_id = parts[2]
        context.user_data['ca_lesson_id'] = lesson_id
        context.user_data['ca_mode'] = 'add_session'
        sessions = await db.bs_get_sessions(lesson_id)
        next_num = len(sessions) + 1
        context.user_data['ca_next_session'] = next_num
        lesson = await db.bs_get_lesson(lesson_id)
        await query.edit_message_text(
            f"➕ <b>جلسه جدید — {lesson.get('name','')}</b>\n\n"
            f"شماره بعدی: <b>{next_num}</b>\n\n"
            "اطلاعات را بنویسید:\n<i>فرمت: شماره, موضوع, نام استاد</i>\n"
            "<i>مثال: 3, فعل‌های بی‌قاعده, دکتر محمدی</i>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data=f'ca:lesson:{lesson_id}')]])
        )

    elif action == 'del_session':
        session_id = parts[2]
        session = await db.bs_get_session(session_id)
        if session:
            await query.edit_message_text(
                f"⚠️ حذف جلسه {session.get('number','')} — {session.get('topic','')[:30]}",
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
            "✅ جلسه حذف شد.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data=f'ca:lesson:{lesson_id}')]])
        )

    elif action == 'session':
        session_id = parts[2]
        context.user_data['ca_session_id'] = session_id
        await _ca_show_session_content(query, context, session_id)

    elif action == 'upload_content':
        session_id = parts[2]
        context.user_data['ca_session_id'] = session_id
        keyboard = [[InlineKeyboardButton(label, callback_data=f'ca:sel_ctype:{session_id}:{ctype}')] for ctype, label in CONTENT_TYPES]
        keyboard.append([InlineKeyboardButton("❌ لغو", callback_data=f'ca:session:{session_id}')])
        await query.edit_message_text(
            "📤 <b>آپلود محتوا</b>\n\nنوع محتوا را انتخاب کنید:",
            parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif action == 'sel_ctype':
        session_id = parts[2]
        ctype = parts[3]
        context.user_data['ca_session_id'] = session_id
        context.user_data['ca_content_type'] = ctype
        context.user_data['ca_mode'] = 'waiting_file'
        type_label = dict(CONTENT_TYPES).get(ctype, ctype)
        await query.edit_message_text(
            f"📤 <b>آپلود {type_label}</b>\n\nفایل را ارسال کنید:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data=f'ca:session:{session_id}')]])
        )
        return CA_WAITING_FILE

    elif action == 'del_content':
        content_id = parts[2]
        item = await db.bs_get_content_item(content_id)
        if item:
            type_label = dict(CONTENT_TYPES).get(item.get('type',''), '')
            await query.edit_message_text(
                f"⚠️ حذف محتوا: {type_label}\nتوضیح: {item.get('description','')[:30]}",
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
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data=f'ca:session:{session_id}')]])
        )

    # ══ رفرنس‌ها ══
    elif action == 'refs':
        await _ca_ref_subjects(query)

    elif action == 'add_ref_subject_prompt':
        context.user_data['ca_mode'] = 'add_ref_subject'
        await query.edit_message_text(
            "➕ <b>درس جدید برای رفرنس</b>\n\nنام درس را بنویسید:\n<i>مثال: فیزیولوژی</i>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data='ca:refs')]])
        )

    elif action == 'del_ref_subject':
        subject_id = parts[2]
        subj = await db.ref_get_subject(subject_id)
        if subj:
            await query.edit_message_text(
                f"⚠️ حذف درس «{subj['name']}» و تمام رفرنس‌هایش؟",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🗑 حذف", callback_data=f'ca:confirm_del_ref_subject:{subject_id}')],
                    [InlineKeyboardButton("❌ لغو", callback_data='ca:refs')]
                ])
            )

    elif action == 'confirm_del_ref_subject':
        subject_id = parts[2]
        await db.ref_delete_subject(subject_id)
        await query.edit_message_text(
            "✅ درس رفرنس حذف شد.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data='ca:refs')]])
        )

    elif action == 'ref_subject':
        subject_id = parts[2]
        context.user_data['ca_ref_subject_id'] = subject_id
        await _ca_ref_books(query, context, subject_id)

    elif action == 'add_ref_book_prompt':
        subject_id = parts[2]
        context.user_data['ca_ref_subject_id'] = subject_id
        context.user_data['ca_mode'] = 'add_ref_book'
        await query.edit_message_text(
            "➕ <b>رفرنس جدید</b>\n\nنام کتاب را بنویسید:\n<i>مثال: Guyton Physiology</i>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data=f'ca:ref_subject:{subject_id}')]])
        )

    elif action == 'del_ref_book':
        book_id = parts[2]
        book = await db.ref_get_book(book_id)
        if book:
            subject_id = context.user_data.get('ca_ref_subject_id', '')
            await query.edit_message_text(
                f"⚠️ حذف رفرنس «{book['name']}»؟",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🗑 حذف", callback_data=f'ca:confirm_del_ref_book:{book_id}')],
                    [InlineKeyboardButton("❌ لغو", callback_data=f'ca:ref_subject:{subject_id}')]
                ])
            )

    elif action == 'confirm_del_ref_book':
        book_id = parts[2]
        await db.ref_delete_book(book_id)
        subject_id = context.user_data.get('ca_ref_subject_id', '')
        await query.edit_message_text(
            "✅ رفرنس حذف شد.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data=f'ca:ref_subject:{subject_id}')]])
        )

    elif action == 'ref_book':
        book_id = parts[2]
        context.user_data['ca_ref_book_id'] = book_id
        await _ca_ref_book_files(query, context, book_id)

    elif action == 'upload_ref':
        book_id = parts[2]
        lang = parts[3]  # fa یا en
        context.user_data['ca_ref_book_id'] = book_id
        context.user_data['ca_ref_lang'] = lang
        context.user_data['ca_mode'] = 'waiting_ref_file'
        lang_label = "🇮🇷 ترجمه فارسی" if lang == 'fa' else "🌐 نسخه لاتین"
        await query.edit_message_text(
            f"📤 <b>آپلود {lang_label}</b>\n\nفایل PDF را ارسال کنید:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data=f'ca:ref_book:{book_id}')]])
        )
        return CA_WAITING_FILE

    elif action == 'del_ref_file':
        file_id_db = parts[2]
        await db.ref_delete_file(file_id_db)
        book_id = context.user_data.get('ca_ref_book_id', '')
        await query.edit_message_text(
            "✅ فایل حذف شد.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data=f'ca:ref_book:{book_id}')]])
        )

    # ══ FAQ ══
    elif action == 'faq':
        await _ca_faq_manage(query)

    elif action == 'add_faq_prompt':
        context.user_data['ca_mode'] = 'add_faq'
        await query.edit_message_text(
            "➕ <b>سوال متداول جدید</b>\n\n"
            "سوال و جواب را بنویسید:\n<i>فرمت: سوال | جواب | دسته‌بندی</i>\n"
            "<i>مثال: نحوه دانلود؟ | روی دکمه دانلود کلیک کنید | ⚙️ مشکلات فنی</i>\n"
            "<i>(دسته‌بندی اختیاری است)</i>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data='ca:faq')]])
        )

    elif action == 'del_faq':
        fid = parts[2]
        await db.faq_delete(fid)
        await query.edit_message_text(
            "✅ سوال حذف شد.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data='ca:faq')]])
        )


# ── توابع نمایش ──

async def _ca_main(query):
    keyboard = [
        [InlineKeyboardButton("📘 مدیریت درس‌های علوم پایه", callback_data='ca:terms')],
        [InlineKeyboardButton("📚 مدیریت رفرنس‌ها", callback_data='ca:refs')],
        [InlineKeyboardButton("❓ مدیریت سوالات متداول", callback_data='ca:faq')],
    ]
    await query.edit_message_text(
        "🎓 <b>پنل ادمین محتوا</b>\n\nچه بخشی را مدیریت می‌کنید؟",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _ca_show_terms(query):
    keyboard = []
    for i in range(0, len(TERMS), 2):
        row = [InlineKeyboardButton(f"📘 {TERMS[i]}", callback_data=f'ca:term:{i}')]
        if i + 1 < len(TERMS):
            row.append(InlineKeyboardButton(f"📘 {TERMS[i+1]}", callback_data=f'ca:term:{i+1}'))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='ca:main')])
    await query.edit_message_text("📘 <b>انتخاب ترم</b>\n\nکدام ترم؟", parse_mode='HTML',
                                   reply_markup=InlineKeyboardMarkup(keyboard))


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
        f"📘 <b>{term}</b> — {len(lessons)} درس",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
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
    name = lesson.get('name', '') if lesson else ''
    await query.edit_message_text(
        f"📖 <b>{name}</b> — {len(sessions)} جلسه",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _ca_show_session_content(query, context, session_id):
    session = await db.bs_get_session(session_id)
    contents = await db.bs_get_content(session_id)
    lesson_id = context.user_data.get('ca_lesson_id', '')
    ICONS = dict(CONTENT_TYPES)
    keyboard = []
    for c in contents:
        cid = str(c['_id'])
        ctype = c.get('type', 'pdf')
        label = f"{ICONS.get(ctype,'📎')} {c.get('description','')[:20]}"
        keyboard.append([
            InlineKeyboardButton(label, callback_data=f'ca:session:{session_id}'),
            InlineKeyboardButton("🗑", callback_data=f'ca:del_content:{cid}')
        ])
    keyboard.append([InlineKeyboardButton("📤 آپلود محتوا", callback_data=f'ca:upload_content:{session_id}')])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f'ca:lesson:{lesson_id}')])
    snum = session.get('number', '') if session else ''
    stopic = session.get('topic', '') if session else ''
    await query.edit_message_text(
        f"📌 <b>جلسه {snum} — {stopic}</b>\n{len(contents)} فایل موجود:",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _ca_ref_subjects(query):
    subjects = await db.ref_get_subjects()
    keyboard = []
    for s in subjects:
        sid = str(s['_id'])
        keyboard.append([
            InlineKeyboardButton(f"📖 {s['name']}", callback_data=f'ca:ref_subject:{sid}'),
            InlineKeyboardButton("🗑", callback_data=f'ca:del_ref_subject:{sid}')
        ])
    keyboard.append([InlineKeyboardButton("➕ درس جدید", callback_data='ca:add_ref_subject_prompt')])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='ca:main')])
    await query.edit_message_text(
        f"📚 <b>رفرنس‌ها</b> — {len(subjects)} درس\n\nدرس را انتخاب کنید:",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _ca_ref_books(query, context, subject_id):
    subj = await db.ref_get_subject(subject_id)
    books = await db.ref_get_books(subject_id)
    keyboard = []
    for b in books:
        bid = str(b['_id'])
        keyboard.append([
            InlineKeyboardButton(f"📘 {b['name']}", callback_data=f'ca:ref_book:{bid}'),
            InlineKeyboardButton("🗑", callback_data=f'ca:del_ref_book:{bid}')
        ])
    keyboard.append([InlineKeyboardButton("➕ کتاب جدید", callback_data=f'ca:add_ref_book_prompt:{subject_id}')])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='ca:refs')])
    name = subj.get('name', '') if subj else ''
    await query.edit_message_text(
        f"📖 <b>{name}</b> — {len(books)} رفرنس:",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _ca_ref_book_files(query, context, book_id):
    book = await db.ref_get_book(book_id)
    files = await db.ref_get_files(book_id)
    langs = {f['lang']: f for f in files}
    subject_id = context.user_data.get('ca_ref_subject_id', '')
    keyboard = []
    for lang, label in [('fa', '🇮🇷 فارسی'), ('en', '🌐 لاتین')]:
        if lang in langs:
            fid = str(langs[lang]['_id'])
            dl = langs[lang].get('downloads', 0)
            keyboard.append([
                InlineKeyboardButton(f"✅ {label} (⬇️{dl})", callback_data=f'ca:ref_book:{book_id}'),
                InlineKeyboardButton("🗑 حذف", callback_data=f'ca:del_ref_file:{fid}')
            ])
        else:
            keyboard.append([InlineKeyboardButton(f"📤 آپلود {label}", callback_data=f'ca:upload_ref:{book_id}:{lang}')])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f'ca:ref_subject:{subject_id}')])
    name = book.get('name', '') if book else ''
    await query.edit_message_text(
        f"📘 <b>{name}</b>\n\nمدیریت فایل‌های PDF:",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _ca_faq_manage(query):
    faqs = await db.faq_get_all()
    keyboard = []
    for f in faqs[:15]:
        fid = str(f['_id'])
        keyboard.append([
            InlineKeyboardButton(f"❓ {f.get('question','')[:30]}", callback_data='ca:faq'),
            InlineKeyboardButton("🗑", callback_data=f'ca:del_faq:{fid}')
        ])
    keyboard.append([InlineKeyboardButton("➕ سوال جدید", callback_data='ca:add_faq_prompt')])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='ca:main')])
    await query.edit_message_text(
        f"❓ <b>سوالات متداول</b> — {len(faqs)} سوال\n\n"
        "⚠️ اگر هیچ سوالی اضافه نشود، سوالات پیش‌فرض ربات نمایش داده می‌شود.",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ── هندلر فایل ──

async def ca_file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not await db.is_content_admin(uid):
        return
    ca_mode = context.user_data.get('ca_mode', '')
    if ca_mode not in ('waiting_file', 'waiting_ref_file'):
        return

    file_obj = (update.message.document or update.message.video or
                update.message.audio or update.message.voice)
    if not file_obj:
        await update.message.reply_text("❌ فایل معتبر ارسال کنید.")
        return CA_WAITING_FILE

    file_id = file_obj.file_id

    if ca_mode == 'waiting_ref_file':
        # رفرنس PDF — مستقیم ذخیره بدون توضیح
        book_id = context.user_data.get('ca_ref_book_id', '')
        lang = context.user_data.get('ca_ref_lang', 'fa')
        await db.ref_add_file(book_id, lang, file_id)
        lang_label = "🇮🇷 فارسی" if lang == 'fa' else "🌐 لاتین"
        await update.message.reply_text(f"✅ فایل {lang_label} آپلود شد!")
        context.user_data['ca_mode'] = ''
        return

    # محتوای علوم پایه — نیاز به توضیح داره
    context.user_data['ca_pending_file'] = file_id
    context.user_data['ca_mode'] = 'waiting_description'
    await update.message.reply_text(
        "✅ فایل دریافت شد!\n\nتوضیح کوتاه بنویسید (یا - بزنید):\n<i>مثال: جلسه اول</i>",
        parse_mode='HTML'
    )
    return CA_WAITING_TEXT


async def ca_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not await db.is_content_admin(uid):
        return
    ca_mode = context.user_data.get('ca_mode', '')
    text = update.message.text.strip()

    if ca_mode == 'add_lesson':
        parts = [p.strip() for p in text.split(',')]
        name = parts[0]
        teacher = parts[1] if len(parts) > 1 else ''
        term = context.user_data.get('ca_term', '')
        result = await db.bs_add_lesson(term, name, teacher)
        if result:
            await update.message.reply_text(f"✅ درس «{name}» به {term} اضافه شد!")
        else:
            await update.message.reply_text("⚠️ این درس قبلاً وجود دارد.")
        context.user_data['ca_mode'] = ''

    elif ca_mode == 'add_session':
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

    elif ca_mode == 'waiting_description':
        description = '' if text == '-' else text
        file_id = context.user_data.get('ca_pending_file', '')
        session_id = context.user_data.get('ca_session_id', '')
        ctype = context.user_data.get('ca_content_type', 'pdf')
        await db.bs_add_content(session_id, ctype, file_id, description)
        type_label = dict(CONTENT_TYPES).get(ctype, ctype)
        await update.message.reply_text(f"✅ {type_label} اضافه شد!")
        context.user_data['ca_mode'] = ''

    elif ca_mode == 'add_ref_subject':
        result = await db.ref_add_subject(text)
        if result:
            await update.message.reply_text(f"✅ درس رفرنس «{text}» اضافه شد!")
        else:
            await update.message.reply_text("⚠️ این درس قبلاً وجود دارد.")
        context.user_data['ca_mode'] = ''

    elif ca_mode == 'add_ref_book':
        subject_id = context.user_data.get('ca_ref_subject_id', '')
        await db.ref_add_book(subject_id, text)
        await update.message.reply_text(f"✅ رفرنس «{text}» اضافه شد!")
        context.user_data['ca_mode'] = ''

    elif ca_mode == 'add_faq':
        parts = [p.strip() for p in text.split('|')]
        if len(parts) < 2:
            await update.message.reply_text("❌ فرمت اشتباه. مثال: سوال؟ | جواب | دسته‌بندی")
            return CA_WAITING_TEXT
        question = parts[0]
        answer = parts[1]
        category = parts[2] if len(parts) > 2 else 'عمومی'
        await db.faq_add(question, answer, category)
        await update.message.reply_text(f"✅ سوال متداول اضافه شد در دسته «{category}»!")
        context.user_data['ca_mode'] = ''
