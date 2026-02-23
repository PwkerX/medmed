"""
پنل ادمین محتوا — نسخه نهایی
فیکس‌ها:
  ✅ لغو با /cancel در هر مرحله
  ✅ دکمه لغو اینلاین در هر مرحله
  ✅ ویرایش درس، جلسه، رفرنس، کتاب
  ✅ دسترسی کامل content_admin (نه فقط ادمین اصلی)
  ✅ یک تابع واحد بدون پچ
"""
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import db

logger   = logging.getLogger(__name__)
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))

TERMS = ['ترم ۱', 'ترم ۲', 'ترم ۳', 'ترم ۴', 'ترم ۵']
CONTENT_TYPES = [
    ('video', '🎥 ویدیو کلاس'),
    ('ppt',   '📊 پاورپوینت'),
    ('pdf',   '📄 جزوه PDF'),
    ('note',  '📝 نکات'),
    ('test',  '🧪 تست'),
    ('voice', '🎙 ویس استاد'),
]

CA_WAITING_FILE = 50
CA_WAITING_TEXT = 51

EDIT_MODES = (
    'add_lesson', 'add_session', 'waiting_description',
    'add_faq', 'add_ref_subject', 'add_ref_book',
    'edit_lesson', 'edit_session', 'edit_ref_subject', 'edit_ref_book',
    'waiting_ref_file', 'waiting_file',
)


def _clear(context):
    """پاک‌سازی کامل وضعیت"""
    for k in ['ca_mode', 'ca_pending_file', 'ca_content_type',
              'ca_edit_target', 'ca_edit_field']:
        context.user_data.pop(k, None)


def _back_btn(label, cb):
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data=cb)]])


# ══════════════════════════════════════════════════════════
#  Callback اصلی — یک تابع واحد
# ══════════════════════════════════════════════════════════
async def content_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    uid    = update.effective_user.id
    data   = query.data
    parts  = data.split(':')
    action = parts[1] if len(parts) > 1 else 'main'

    if not await db.is_content_admin(uid):
        await query.answer("❌ دسترسی ندارید!", show_alert=True)
        return

    # ── هر بار دکمه زده شد، ca_mode پاک شه (مگر حالت‌های منتظر ورودی) ──
    KEEP_MODE = ('add_lesson_prompt', 'add_session_prompt', 'sel_ctype',
                 'add_ref_subject_prompt', 'add_ref_book_prompt', 'add_faq_prompt',
                 'upload_ref', 'edit_lesson_prompt', 'edit_session_prompt',
                 'edit_ref_subject_prompt', 'edit_ref_book_prompt')
    if action not in KEEP_MODE:
        _clear(context)

    from_admin = action.endswith('_admin')
    back_main  = 'admin:main' if from_admin else 'ca:main'

    # ════ منوی اصلی ════
    if action == 'main':
        await _show_main(query)

    # ══════════ علوم پایه ══════════

    elif action in ('terms', 'terms_admin'):
        context.user_data['ca_from_admin'] = from_admin
        await _show_terms(query, back=back_main)

    elif action == 'term':
        idx  = int(parts[2])
        context.user_data['ca_term']     = TERMS[idx]
        context.user_data['ca_term_idx'] = idx
        fa   = context.user_data.get('ca_from_admin', False)
        await _show_lessons(query, context, TERMS[idx],
                            back='ca:terms_admin' if fa else 'ca:terms')

    # ─ افزودن درس ─
    elif action == 'add_lesson_prompt':
        idx  = int(parts[2])
        term = TERMS[idx]
        context.user_data.update({'ca_term_idx': idx, 'ca_term': term, 'ca_mode': 'add_lesson'})
        await query.edit_message_text(
            f"➕ <b>درس جدید — {term}</b>\n\n"
            "📝 فرمت: <code>نام درس, نام استاد</code>\n"
            "مثال: <code>فیزیولوژی, دکتر احمدی</code>\n\n"
            "<i>استاد اختیاری است</i>\n\n"
            "⌨️ برای لغو: /cancel",
            parse_mode='HTML',
            reply_markup=_back_btn("❌ لغو", f'ca:term:{idx}'))

    # ─ ویرایش درس ─
    elif action == 'edit_lesson_menu':
        lid    = parts[2]
        lesson = await db.bs_get_lesson(lid)
        if not lesson: return
        keyboard = [
            [InlineKeyboardButton("✏️ ویرایش نام درس",   callback_data=f'ca:edit_lesson_prompt:{lid}:name')],
            [InlineKeyboardButton("✏️ ویرایش نام استاد", callback_data=f'ca:edit_lesson_prompt:{lid}:teacher')],
            [InlineKeyboardButton("🔙 بازگشت",            callback_data=f'ca:lesson:{lid}')],
        ]
        await query.edit_message_text(
            f"✏️ <b>ویرایش درس «{lesson['name']}»</b>\n\nکدام فیلد؟",
            parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

    elif action == 'edit_lesson_prompt':
        lid   = parts[2]
        field = parts[3]
        lesson = await db.bs_get_lesson(lid)
        if not lesson: return
        label = 'نام درس' if field == 'name' else 'نام استاد'
        current = lesson.get(field, '')
        context.user_data.update({'ca_mode': 'edit_lesson', 'ca_edit_target': lid, 'ca_edit_field': field})
        await query.edit_message_text(
            f"✏️ <b>ویرایش {label}</b>\n\n"
            f"مقدار فعلی: <b>{current}</b>\n\n"
            "مقدار جدید را بنویسید:\n⌨️ برای لغو: /cancel",
            parse_mode='HTML',
            reply_markup=_back_btn("❌ لغو", f'ca:lesson:{lid}'))

    # ─ حذف درس ─
    elif action == 'del_lesson':
        lid    = parts[2]
        lesson = await db.bs_get_lesson(lid)
        if not lesson: return
        idx    = context.user_data.get('ca_term_idx', 0)
        await query.edit_message_text(
            f"⚠️ <b>حذف درس «{lesson['name']}»؟</b>\n\nتمام جلسات و محتوا هم حذف می‌شود!",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑 بله، حذف کن", callback_data=f'ca:confirm_del_lesson:{lid}')],
                [InlineKeyboardButton("❌ لغو",          callback_data=f'ca:term:{idx}')],
            ]))

    elif action == 'confirm_del_lesson':
        lid    = parts[2]
        lesson = await db.bs_get_lesson(lid)
        name   = lesson['name'] if lesson else ''
        await db.bs_delete_lesson(lid)
        idx    = context.user_data.get('ca_term_idx', 0)
        await query.edit_message_text(
            f"✅ درس «{name}» حذف شد.",
            reply_markup=_back_btn("🔙 بازگشت به ترم", f'ca:term:{idx}'))

    # ─ جلسات ─
    elif action == 'lesson':
        lid    = parts[2]
        context.user_data['ca_lesson_id'] = lid
        await _show_sessions(query, context, lid)

    # ─ افزودن جلسه ─
    elif action == 'add_session_prompt':
        lid      = parts[2]
        context.user_data.update({'ca_lesson_id': lid, 'ca_mode': 'add_session'})
        sessions = await db.bs_get_sessions(lid)
        next_n   = len(sessions) + 1
        lesson   = await db.bs_get_lesson(lid)
        lname    = lesson.get('name','') if lesson else ''
        await query.edit_message_text(
            f"➕ <b>جلسه جدید — {lname}</b>\n\n"
            f"📝 فرمت: <code>شماره, موضوع, استاد</code>\n"
            f"مثال: <code>{next_n}, فیزیولوژی کلیه, دکتر احمدی</code>\n\n"
            f"<i>شماره پیشنهادی: <b>{next_n}</b> — استاد اختیاری</i>\n\n"
            "⌨️ برای لغو: /cancel",
            parse_mode='HTML',
            reply_markup=_back_btn("❌ لغو", f'ca:lesson:{lid}'))

    # ─ ویرایش جلسه ─
    elif action == 'edit_session_menu':
        sid     = parts[2]
        session = await db.bs_get_session(sid)
        if not session: return
        keyboard = [
            [InlineKeyboardButton("✏️ ویرایش موضوع",      callback_data=f'ca:edit_session_prompt:{sid}:topic')],
            [InlineKeyboardButton("✏️ ویرایش نام استاد",  callback_data=f'ca:edit_session_prompt:{sid}:teacher')],
            [InlineKeyboardButton("✏️ ویرایش شماره جلسه", callback_data=f'ca:edit_session_prompt:{sid}:number')],
            [InlineKeyboardButton("🔙 بازگشت",            callback_data=f'ca:session:{sid}')],
        ]
        await query.edit_message_text(
            f"✏️ <b>ویرایش جلسه {session.get('number','')} — {session.get('topic','')}</b>\n\nکدام فیلد؟",
            parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

    elif action == 'edit_session_prompt':
        sid   = parts[2]
        field = parts[3]
        session = await db.bs_get_session(sid)
        if not session: return
        labels  = {'topic': 'موضوع', 'teacher': 'نام استاد', 'number': 'شماره جلسه'}
        current = str(session.get(field, ''))
        context.user_data.update({'ca_mode': 'edit_session', 'ca_edit_target': sid, 'ca_edit_field': field})
        await query.edit_message_text(
            f"✏️ <b>ویرایش {labels.get(field,'')}</b>\n\n"
            f"مقدار فعلی: <b>{current}</b>\n\n"
            "مقدار جدید را بنویسید:\n⌨️ برای لغو: /cancel",
            parse_mode='HTML',
            reply_markup=_back_btn("❌ لغو", f'ca:session:{sid}'))

    # ─ حذف جلسه ─
    elif action == 'del_session':
        sid     = parts[2]
        session = await db.bs_get_session(sid)
        if not session: return
        lid     = context.user_data.get('ca_lesson_id','')
        await query.edit_message_text(
            f"⚠️ <b>حذف جلسه {session.get('number','')} — {session.get('topic','')}؟</b>\n\n"
            "تمام محتوای این جلسه هم حذف می‌شود!",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑 بله، حذف کن", callback_data=f'ca:confirm_del_session:{sid}')],
                [InlineKeyboardButton("❌ لغو",          callback_data=f'ca:lesson:{lid}')],
            ]))

    elif action == 'confirm_del_session':
        sid = parts[2]
        await db.bs_delete_session(sid)
        lid = context.user_data.get('ca_lesson_id','')
        await query.edit_message_text(
            "✅ جلسه حذف شد.",
            reply_markup=_back_btn("🔙 بازگشت", f'ca:lesson:{lid}'))

    # ─ محتوای جلسه ─
    elif action == 'session':
        sid = parts[2]
        context.user_data['ca_session_id'] = sid
        await _show_session_content(query, context, sid)

    # ─ آپلود محتوا ─
    elif action == 'upload_content':
        sid = parts[2]
        context.user_data['ca_session_id'] = sid
        keyboard = [[InlineKeyboardButton(label, callback_data=f'ca:sel_ctype:{sid}:{ct}')]
                    for ct, label in CONTENT_TYPES]
        keyboard.append([InlineKeyboardButton("❌ لغو", callback_data=f'ca:session:{sid}')])
        await query.edit_message_text(
            "📤 <b>نوع محتوا را انتخاب کنید:</b>",
            parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

    elif action == 'sel_ctype':
        sid   = parts[2]
        ctype = parts[3]
        context.user_data.update({'ca_session_id': sid, 'ca_content_type': ctype, 'ca_mode': 'waiting_file'})
        tlabel = dict(CONTENT_TYPES).get(ctype, ctype)
        await query.edit_message_text(
            f"📤 <b>آپلود {tlabel}</b>\n\nفایل را ارسال کنید:\n⌨️ برای لغو: /cancel",
            parse_mode='HTML',
            reply_markup=_back_btn("❌ لغو", f'ca:session:{sid}'))
        return CA_WAITING_FILE

    # ─ حذف محتوا ─
    elif action == 'del_content':
        cid  = parts[2]
        item = await db.bs_get_content_item(cid)
        if not item: return
        sid    = context.user_data.get('ca_session_id','')
        tlabel = dict(CONTENT_TYPES).get(item.get('type',''),'فایل')
        await query.edit_message_text(
            f"⚠️ <b>حذف {tlabel}؟</b>\n{item.get('description','')[:40]}",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑 حذف", callback_data=f'ca:confirm_del_content:{cid}')],
                [InlineKeyboardButton("❌ لغو", callback_data=f'ca:session:{sid}')],
            ]))

    elif action == 'confirm_del_content':
        cid = parts[2]
        await db.bs_delete_content(cid)
        sid = context.user_data.get('ca_session_id','')
        await query.edit_message_text(
            "✅ محتوا حذف شد.",
            reply_markup=_back_btn("🔙 بازگشت", f'ca:session:{sid}'))

    # ══════════ رفرنس‌ها ══════════

    elif action in ('refs', 'refs_admin'):
        context.user_data['ca_ref_from_admin'] = from_admin
        await _show_ref_subjects(query, back=back_main)

    # ─ افزودن درس رفرنس ─
    elif action == 'add_ref_subject_prompt':
        context.user_data['ca_mode'] = 'add_ref_subject'
        fa   = context.user_data.get('ca_ref_from_admin', False)
        back = 'ca:refs_admin' if fa else 'ca:refs'
        await query.edit_message_text(
            "➕ <b>درس جدید برای رفرنس</b>\n\n"
            "نام درس را بنویسید:\n"
            "مثال: <code>فیزیولوژی</code>\n\n"
            "⌨️ برای لغو: /cancel",
            parse_mode='HTML',
            reply_markup=_back_btn("❌ لغو", back))

    # ─ ویرایش درس رفرنس ─
    elif action == 'edit_ref_subject_prompt':
        sid  = parts[2]
        subj = await db.ref_get_subject(sid)
        if not subj: return
        context.user_data.update({'ca_mode': 'edit_ref_subject', 'ca_edit_target': sid})
        await query.edit_message_text(
            f"✏️ <b>ویرایش نام درس</b>\n\n"
            f"نام فعلی: <b>{subj['name']}</b>\n\n"
            "نام جدید را بنویسید:\n⌨️ برای لغو: /cancel",
            parse_mode='HTML',
            reply_markup=_back_btn("❌ لغو", f'ca:ref_subject:{sid}'))

    # ─ حذف درس رفرنس ─
    elif action == 'del_ref_subject':
        sid  = parts[2]
        subj = await db.ref_get_subject(sid)
        if not subj: return
        fa   = context.user_data.get('ca_ref_from_admin', False)
        back = 'ca:refs_admin' if fa else 'ca:refs'
        await query.edit_message_text(
            f"⚠️ <b>حذف درس «{subj['name']}»؟</b>\n\nتمام کتاب‌ها و فایل‌ها هم حذف می‌شوند!",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑 بله، حذف کن", callback_data=f'ca:confirm_del_ref_subject:{sid}')],
                [InlineKeyboardButton("❌ لغو",          callback_data=back)],
            ]))

    elif action == 'confirm_del_ref_subject':
        sid = parts[2]
        await db.ref_delete_subject(sid)
        fa   = context.user_data.get('ca_ref_from_admin', False)
        back = 'ca:refs_admin' if fa else 'ca:refs'
        await query.edit_message_text(
            "✅ درس رفرنس حذف شد.",
            reply_markup=_back_btn("🔙 بازگشت", back))

    elif action == 'ref_subject':
        sid  = parts[2]
        context.user_data['ca_ref_subject_id'] = sid
        fa   = context.user_data.get('ca_ref_from_admin', False)
        back = 'ca:refs_admin' if fa else 'ca:refs'
        await _show_ref_books(query, context, sid, back=back)

    # ─ افزودن کتاب ─
    elif action == 'add_ref_book_prompt':
        sid  = parts[2]
        context.user_data.update({'ca_ref_subject_id': sid, 'ca_mode': 'add_ref_book'})
        await query.edit_message_text(
            "➕ <b>کتاب/رفرنس جدید</b>\n\n"
            "نام کتاب را بنویسید:\n"
            "مثال: <code>Guyton Physiology</code>\n\n"
            "⌨️ برای لغو: /cancel",
            parse_mode='HTML',
            reply_markup=_back_btn("❌ لغو", f'ca:ref_subject:{sid}'))

    # ─ ویرایش کتاب ─
    elif action == 'edit_ref_book_prompt':
        bid  = parts[2]
        book = await db.ref_get_book(bid)
        if not book: return
        context.user_data.update({'ca_mode': 'edit_ref_book', 'ca_edit_target': bid})
        await query.edit_message_text(
            f"✏️ <b>ویرایش نام کتاب</b>\n\n"
            f"نام فعلی: <b>{book['name']}</b>\n\n"
            "نام جدید را بنویسید:\n⌨️ برای لغو: /cancel",
            parse_mode='HTML',
            reply_markup=_back_btn("❌ لغو", f'ca:ref_book:{bid}'))

    # ─ حذف کتاب ─
    elif action == 'del_ref_book':
        bid  = parts[2]
        book = await db.ref_get_book(bid)
        if not book: return
        sid  = context.user_data.get('ca_ref_subject_id','')
        await query.edit_message_text(
            f"⚠️ <b>حذف رفرنس «{book['name']}»؟</b>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑 حذف", callback_data=f'ca:confirm_del_ref_book:{bid}')],
                [InlineKeyboardButton("❌ لغو", callback_data=f'ca:ref_subject:{sid}')],
            ]))

    elif action == 'confirm_del_ref_book':
        bid = parts[2]
        await db.ref_delete_book(bid)
        sid = context.user_data.get('ca_ref_subject_id','')
        await query.edit_message_text(
            "✅ رفرنس حذف شد.",
            reply_markup=_back_btn("🔙 بازگشت", f'ca:ref_subject:{sid}'))

    elif action == 'ref_book':
        bid  = parts[2]
        context.user_data['ca_ref_book_id'] = bid
        await _show_ref_book_files(query, context, bid)

    # ─ آپلود فایل رفرنس ─
    elif action == 'upload_ref':
        bid  = parts[2]
        lang = parts[3]
        context.user_data.update({'ca_ref_book_id': bid, 'ca_ref_lang': lang, 'ca_mode': 'waiting_ref_file'})
        ll   = "🇮🇷 فارسی" if lang == 'fa' else "🌐 لاتین"
        await query.edit_message_text(
            f"📤 <b>آپلود {ll}</b>\n\nفایل PDF را ارسال کنید:\n⌨️ برای لغو: /cancel",
            parse_mode='HTML',
            reply_markup=_back_btn("❌ لغو", f'ca:ref_book:{bid}'))
        return CA_WAITING_FILE

    elif action == 'del_ref_file':
        fid = parts[2]
        await db.ref_delete_file(fid)
        bid  = context.user_data.get('ca_ref_book_id','')
        await query.edit_message_text(
            "✅ فایل حذف شد.",
            reply_markup=_back_btn("🔙 بازگشت", f'ca:ref_book:{bid}'))

    # ══════════ FAQ ══════════

    elif action == 'faq':
        await _show_faq(query)

    elif action == 'add_faq_prompt':
        context.user_data['ca_mode'] = 'add_faq'
        await query.edit_message_text(
            "➕ <b>سوال متداول جدید</b>\n\n"
            "📝 فرمت: <code>سوال | جواب | دسته‌بندی</code>\n"
            "مثال: <code>نحوه دانلود؟ | روی دانلود کلیک کنید | ⚙️ مشکلات فنی</code>\n\n"
            "⌨️ برای لغو: /cancel",
            parse_mode='HTML',
            reply_markup=_back_btn("❌ لغو", 'ca:faq'))

    elif action == 'del_faq':
        await db.faq_delete(parts[2])
        await _show_faq(query)


# ══════════════════════════════════════════════════════════
#  توابع نمایش
# ══════════════════════════════════════════════════════════

async def _show_main(query):
    kb = [
        [InlineKeyboardButton("📘 مدیریت علوم پایه", callback_data='ca:terms')],
        [InlineKeyboardButton("📚 مدیریت رفرنس‌ها",  callback_data='ca:refs')],
        [InlineKeyboardButton("❓ مدیریت FAQ",         callback_data='ca:faq')],
    ]
    await query.edit_message_text(
        "🎓 <b>پنل ادمین محتوا</b>",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(kb))


async def _show_terms(query, back='ca:main'):
    kb = []
    for i in range(0, len(TERMS), 2):
        row = [InlineKeyboardButton(f"📘 {TERMS[i]}", callback_data=f'ca:term:{i}')]
        if i+1 < len(TERMS):
            row.append(InlineKeyboardButton(f"📘 {TERMS[i+1]}", callback_data=f'ca:term:{i+1}'))
        kb.append(row)
    kb.append([InlineKeyboardButton("🔙 بازگشت", callback_data=back)])
    await query.edit_message_text(
        "📘 <b>انتخاب ترم — علوم پایه</b>",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(kb))


async def _show_lessons(query, context, term, back='ca:terms'):
    lessons = await db.bs_get_lessons(term)
    idx     = context.user_data.get('ca_term_idx', 0)
    kb = []
    for l in lessons:
        lid = str(l['_id'])
        t   = f" | {l['teacher']}" if l.get('teacher') else ''
        kb.append([
            InlineKeyboardButton(f"📖 {l['name']}{t}", callback_data=f'ca:lesson:{lid}'),
            InlineKeyboardButton("✏️",  callback_data=f'ca:edit_lesson_menu:{lid}'),
            InlineKeyboardButton("🗑",   callback_data=f'ca:del_lesson:{lid}'),
        ])
    kb.append([InlineKeyboardButton(f"➕ درس جدید",  callback_data=f'ca:add_lesson_prompt:{idx}')])
    kb.append([InlineKeyboardButton("🔙 بازگشت",     callback_data=back)])
    await query.edit_message_text(
        f"📘 <b>{term}</b> — {len(lessons)} درس\n"
        "<i>✏️=ویرایش  🗑=حذف</i>",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(kb))


async def _show_sessions(query, context, lid):
    lesson   = await db.bs_get_lesson(lid)
    sessions = await db.bs_get_sessions(lid)
    idx      = context.user_data.get('ca_term_idx', 0)
    kb = []
    for s in sessions:
        sid = str(s['_id'])
        kb.append([
            InlineKeyboardButton(f"📌 {s['number']} — {s.get('topic','')[:22]}", callback_data=f'ca:session:{sid}'),
            InlineKeyboardButton("✏️",  callback_data=f'ca:edit_session_menu:{sid}'),
            InlineKeyboardButton("🗑",   callback_data=f'ca:del_session:{sid}'),
        ])
    kb.append([InlineKeyboardButton("➕ جلسه جدید", callback_data=f'ca:add_session_prompt:{lid}')])
    kb.append([InlineKeyboardButton("🔙 بازگشت",    callback_data=f'ca:term:{idx}')])
    lname = lesson.get('name','') if lesson else ''
    await query.edit_message_text(
        f"📖 <b>{lname}</b> — {len(sessions)} جلسه\n"
        "<i>✏️=ویرایش  🗑=حذف</i>",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(kb))


async def _show_session_content(query, context, sid):
    session  = await db.bs_get_session(sid)
    contents = await db.bs_get_content(sid)
    lid      = context.user_data.get('ca_lesson_id','')
    ICONS    = dict(CONTENT_TYPES)
    kb = []
    for c in contents:
        cid   = str(c['_id'])
        ctype = c.get('type','pdf')
        desc  = c.get('description','')[:20]
        kb.append([
            InlineKeyboardButton(f"{ICONS.get(ctype,'📎')} {desc}", callback_data=f'ca:session:{sid}'),
            InlineKeyboardButton("🗑", callback_data=f'ca:del_content:{cid}'),
        ])
    kb.append([InlineKeyboardButton("📤 آپلود محتوا",        callback_data=f'ca:upload_content:{sid}')])
    kb.append([InlineKeyboardButton("✏️ ویرایش اطلاعات جلسه", callback_data=f'ca:edit_session_menu:{sid}')])
    kb.append([InlineKeyboardButton("🔙 بازگشت",              callback_data=f'ca:lesson:{lid}')])
    if session:
        header = (f"📌 <b>جلسه {session.get('number','')}</b>\n"
                  f"📚 {session.get('topic','')}\n"
                  f"👨‍🏫 {session.get('teacher','') or 'ثبت نشده'}\n"
                  f"━━━━━━━━━━━━━━━━\n{len(contents)} فایل:")
    else:
        header = "📌 جلسه"
    await query.edit_message_text(header, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(kb))


async def _show_ref_subjects(query, back='ca:main'):
    subjects = await db.ref_get_subjects()
    kb = []
    for s in subjects:
        sid = str(s['_id'])
        kb.append([
            InlineKeyboardButton(f"📖 {s['name']}", callback_data=f'ca:ref_subject:{sid}'),
            InlineKeyboardButton("✏️",  callback_data=f'ca:edit_ref_subject_prompt:{sid}'),
            InlineKeyboardButton("🗑",   callback_data=f'ca:del_ref_subject:{sid}'),
        ])
    kb.append([InlineKeyboardButton("➕ درس جدید", callback_data='ca:add_ref_subject_prompt')])
    kb.append([InlineKeyboardButton("🔙 بازگشت",   callback_data=back)])
    await query.edit_message_text(
        f"📚 <b>رفرنس‌ها</b> — {len(subjects)} درس\n"
        "<i>✏️=ویرایش نام  🗑=حذف کامل</i>",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(kb))


async def _show_ref_books(query, context, sid, back='ca:refs'):
    subj  = await db.ref_get_subject(sid)
    books = await db.ref_get_books(sid)
    kb = []
    for b in books:
        bid = str(b['_id'])
        kb.append([
            InlineKeyboardButton(f"📘 {b['name']}", callback_data=f'ca:ref_book:{bid}'),
            InlineKeyboardButton("✏️",  callback_data=f'ca:edit_ref_book_prompt:{bid}'),
            InlineKeyboardButton("🗑",   callback_data=f'ca:del_ref_book:{bid}'),
        ])
    kb.append([InlineKeyboardButton("➕ کتاب جدید", callback_data=f'ca:add_ref_book_prompt:{sid}')])
    kb.append([InlineKeyboardButton("🔙 بازگشت",    callback_data=back)])
    name = subj.get('name','') if subj else ''
    await query.edit_message_text(
        f"📖 <b>{name}</b> — {len(books)} رفرنس\n"
        "<i>✏️=ویرایش نام  🗑=حذف کامل</i>",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(kb))


async def _show_ref_book_files(query, context, bid):
    book    = await db.ref_get_book(bid)
    files   = await db.ref_get_files(bid)
    langs   = {f['lang']: f for f in files}
    sid     = context.user_data.get('ca_ref_subject_id','')
    kb      = []
    for lang, label in [('fa','🇮🇷 فارسی'), ('en','🌐 لاتین')]:
        if lang in langs:
            fid = str(langs[lang]['_id'])
            dl  = langs[lang].get('downloads', 0)
            kb.append([
                InlineKeyboardButton(f"✅ {label}  ⬇️{dl}", callback_data=f'ca:ref_book:{bid}'),
                InlineKeyboardButton("🔄 جایگزین",           callback_data=f'ca:upload_ref:{bid}:{lang}'),
                InlineKeyboardButton("🗑",                    callback_data=f'ca:del_ref_file:{fid}'),
            ])
        else:
            kb.append([InlineKeyboardButton(f"📤 آپلود {label}", callback_data=f'ca:upload_ref:{bid}:{lang}')])
    kb.append([InlineKeyboardButton("✏️ ویرایش نام کتاب", callback_data=f'ca:edit_ref_book_prompt:{bid}')])
    kb.append([InlineKeyboardButton("🔙 بازگشت",           callback_data=f'ca:ref_subject:{sid}')])
    name = book.get('name','') if book else ''
    await query.edit_message_text(
        f"📘 <b>{name}</b>\n\nمدیریت فایل‌های PDF:",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(kb))


async def _show_faq(query):
    faqs = await db.faq_get_all()
    kb   = []
    for f in faqs[:15]:
        fid = str(f['_id'])
        kb.append([
            InlineKeyboardButton(f"❓ {f.get('question','')[:30]}", callback_data='ca:faq'),
            InlineKeyboardButton("🗑", callback_data=f'ca:del_faq:{fid}'),
        ])
    kb.append([InlineKeyboardButton("➕ سوال جدید", callback_data='ca:add_faq_prompt')])
    kb.append([InlineKeyboardButton("🔙 بازگشت",   callback_data='ca:main')])
    await query.edit_message_text(
        f"❓ <b>سوالات متداول</b> — {len(faqs)} سوال",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(kb))


# ══════════════════════════════════════════════════════════
#  هندلر فایل
# ══════════════════════════════════════════════════════════

async def ca_file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid     = update.effective_user.id
    if not await db.is_content_admin(uid): return
    ca_mode = context.user_data.get('ca_mode','')
    if ca_mode not in ('waiting_file', 'waiting_ref_file'): return

    file_obj = (update.message.document or update.message.video or
                update.message.audio    or update.message.voice)
    if not file_obj:
        await update.message.reply_text("❌ فایل معتبر ارسال کنید.\n⌨️ /cancel برای لغو")
        return CA_WAITING_FILE

    fid = file_obj.file_id

    if ca_mode == 'waiting_ref_file':
        bid  = context.user_data.get('ca_ref_book_id','')
        lang = context.user_data.get('ca_ref_lang','fa')
        await db.ref_add_file(bid, lang, fid)
        ll   = "🇮🇷 فارسی" if lang == 'fa' else "🌐 لاتین"
        _clear(context)
        await update.message.reply_text(
            f"✅ فایل {ll} آپلود شد!",
            reply_markup=_back_btn("🔙 برگشت", f'ca:ref_book:{bid}'))
        return

    context.user_data.update({'ca_pending_file': fid, 'ca_mode': 'waiting_description'})
    sid = context.user_data.get('ca_session_id','')
    await update.message.reply_text(
        "✅ فایل دریافت شد!\n\n"
        "📝 توضیح کوتاه بنویسید (یا <code>-</code> برای بدون توضیح):\n"
        "⌨️ /cancel برای لغو",
        parse_mode='HTML',
        reply_markup=_back_btn("❌ لغو", f'ca:session:{sid}'))
    return CA_WAITING_TEXT


# ══════════════════════════════════════════════════════════
#  هندلر متن — با /cancel کامل
# ══════════════════════════════════════════════════════════

async def ca_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid     = update.effective_user.id
    if not await db.is_content_admin(uid): return
    ca_mode = context.user_data.get('ca_mode','')
    text    = update.message.text.strip()

    # ── لغو در هر مرحله ──
    if text.lower() in ('/cancel', 'لغو', '❌ لغو', 'cancel'):
        _clear(context)
        await update.message.reply_text(
            "✅ عملیات لغو شد.\n\nبرای ادامه از دکمه‌های ربات استفاده کنید.")
        return ConversationHandler.END

    # ── افزودن درس علوم پایه ──
    if ca_mode == 'add_lesson':
        ps      = [p.strip() for p in text.split(',')]
        name    = ps[0]
        teacher = ps[1] if len(ps) > 1 else ''
        term    = context.user_data.get('ca_term','')
        idx     = context.user_data.get('ca_term_idx', 0)
        result  = await db.bs_add_lesson(term, name, teacher)
        _clear(context)
        msg = f"✅ درس «{name}» به {term} اضافه شد!" if result else "⚠️ این درس قبلاً وجود دارد."
        await update.message.reply_text(msg, reply_markup=_back_btn("🔙 برگشت به ترم", f'ca:term:{idx}'))

    # ── ویرایش درس علوم پایه ──
    elif ca_mode == 'edit_lesson':
        lid   = context.user_data.get('ca_edit_target','')
        field = context.user_data.get('ca_edit_field','')
        ok    = await db.bs_update_lesson(lid, {field: text})
        _clear(context)
        msg = "✅ ویرایش ذخیره شد." if ok else "❌ خطا در ویرایش."
        await update.message.reply_text(msg, reply_markup=_back_btn("🔙 برگشت", f'ca:lesson:{lid}'))

    # ── افزودن جلسه ──
    elif ca_mode == 'add_session':
        ps  = [p.strip() for p in text.split(',')]
        lid = context.user_data.get('ca_lesson_id','')
        if len(ps) < 2:
            await update.message.reply_text(
                "❌ <b>فرمت اشتباه!</b>\n\n"
                "📝 باید اینطوری بنویسی:\n"
                "<code>شماره, موضوع, استاد</code>\n"
                "مثال: <code>3, فیزیولوژی کلیه, دکتر احمدی</code>\n\n"
                "⌨️ /cancel برای لغو کامل",
                parse_mode='HTML',
                reply_markup=_back_btn("❌ لغو کامل", f'ca:lesson:{lid}'))
            return CA_WAITING_TEXT
        try:    number = int(ps[0])
        except:
            sessions = await db.bs_get_sessions(lid)
            number   = len(sessions) + 1
        topic   = ps[1]
        teacher = ps[2] if len(ps) > 2 else ''
        await db.bs_add_session(lid, number, topic, teacher)
        _clear(context)
        await update.message.reply_text(
            f"✅ جلسه {number} — «{topic}» اضافه شد!",
            reply_markup=_back_btn("🔙 برگشت به درس", f'ca:lesson:{lid}'))

    # ── ویرایش جلسه ──
    elif ca_mode == 'edit_session':
        sid   = context.user_data.get('ca_edit_target','')
        field = context.user_data.get('ca_edit_field','')
        val   = int(text) if field == 'number' and text.isdigit() else text
        ok    = await db.bs_update_session(sid, {field: val})
        _clear(context)
        msg = "✅ جلسه ویرایش شد." if ok else "❌ خطا در ویرایش."
        await update.message.reply_text(msg, reply_markup=_back_btn("🔙 برگشت", f'ca:session:{sid}'))

    # ── توضیح فایل ──
    elif ca_mode == 'waiting_description':
        desc = '' if text == '-' else text
        fid  = context.user_data.get('ca_pending_file','')
        sid  = context.user_data.get('ca_session_id','')
        ct   = context.user_data.get('ca_content_type','pdf')
        await db.bs_add_content(sid, ct, fid, desc)
        tl   = dict(CONTENT_TYPES).get(ct, ct)
        _clear(context)
        await update.message.reply_text(
            f"✅ {tl} اضافه شد!",
            reply_markup=_back_btn("🔙 برگشت به جلسه", f'ca:session:{sid}'))

    # ── افزودن درس رفرنس ──
    elif ca_mode == 'add_ref_subject':
        result = await db.ref_add_subject(text)
        fa     = context.user_data.get('ca_ref_from_admin', False)
        back   = 'ca:refs_admin' if fa else 'ca:refs'
        _clear(context)
        msg = f"✅ درس «{text}» اضافه شد!" if result else "⚠️ این درس قبلاً وجود دارد."
        await update.message.reply_text(msg, reply_markup=_back_btn("🔙 برگشت به رفرنس‌ها", back))

    # ── ویرایش درس رفرنس ──
    elif ca_mode == 'edit_ref_subject':
        sid = context.user_data.get('ca_edit_target','')
        ok  = await db.ref_update_subject(sid, {'name': text})
        _clear(context)
        msg = f"✅ نام درس به «{text}» تغییر یافت." if ok else "❌ خطا در ویرایش."
        await update.message.reply_text(msg, reply_markup=_back_btn("🔙 برگشت", f'ca:ref_subject:{sid}'))

    # ── افزودن کتاب ──
    elif ca_mode == 'add_ref_book':
        sid = context.user_data.get('ca_ref_subject_id','')
        await db.ref_add_book(sid, text)
        _clear(context)
        await update.message.reply_text(
            f"✅ رفرنس «{text}» اضافه شد!",
            reply_markup=_back_btn("🔙 برگشت", f'ca:ref_subject:{sid}'))

    # ── ویرایش کتاب ──
    elif ca_mode == 'edit_ref_book':
        bid = context.user_data.get('ca_edit_target','')
        ok  = await db.ref_update_book(bid, {'name': text})
        _clear(context)
        msg = f"✅ نام کتاب به «{text}» تغییر یافت." if ok else "❌ خطا در ویرایش."
        await update.message.reply_text(msg, reply_markup=_back_btn("🔙 برگشت", f'ca:ref_book:{bid}'))

    # ── افزودن FAQ ──
    elif ca_mode == 'add_faq':
        ps = [p.strip() for p in text.split('|')]
        if len(ps) < 2:
            await update.message.reply_text(
                "❌ <b>فرمت اشتباه!</b>\n\n"
                "📝 فرمت: <code>سوال | جواب | دسته</code>\n"
                "⌨️ /cancel برای لغو",
                parse_mode='HTML')
            return CA_WAITING_TEXT
        question = ps[0]; answer = ps[1]
        category = ps[2] if len(ps) > 2 else 'عمومی'
        await db.faq_add(question, answer, category)
        _clear(context)
        await update.message.reply_text(
            f"✅ سوال در «{category}» اضافه شد!",
            reply_markup=_back_btn("🔙 برگشت به FAQ", 'ca:faq'))

    else:
        # اگر هیچ mode ای نبود، لغو کن
        _clear(context)
        await update.message.reply_text("⚠️ عملیات نامشخص. لطفاً از منوی ربات استفاده کنید.")
        return ConversationHandler.END
