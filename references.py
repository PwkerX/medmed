"""رفرنس‌ها — دانشجو"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db

logger = logging.getLogger(__name__)


async def references_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    data   = query.data
    parts  = data.split(':')
    action = parts[1] if len(parts) > 1 else 'main'

    came_from_admin = context.user_data.get('ref_from_admin', False)

    if action == 'main':
        context.user_data['ref_from_admin'] = False
        await _show_subjects(query, back_cb='resources:menu')

    elif action == 'main_admin':
        context.user_data['ref_from_admin'] = True
        await _show_subjects(query, back_cb='admin:main')

    elif action == 'subject':
        subject_id = parts[2]
        context.user_data['ref_subject_id'] = subject_id
        back = 'ref:main_admin' if came_from_admin else 'ref:main'
        await _show_books(query, context, subject_id, back_cb=back)

    elif action == 'book':
        book_id = parts[2]
        context.user_data['ref_book_id'] = book_id
        subject_id = context.user_data.get('ref_subject_id', '')
        await _show_lang_choice(query, context, book_id, back_cb=f'ref:subject:{subject_id}')

    elif action == 'dl':
        file_id_db = parts[2]
        await _download_ref(query, file_id_db, update.effective_user.id)


async def _show_subjects(query, back_cb='resources:menu'):
    subjects = await db.ref_get_subjects()
    if not subjects:
        await query.edit_message_text(
            "📚 <b>رفرنس‌ها</b>\n\n❌ هنوز درسی تعریف نشده.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 بازگشت", callback_data=back_cb)
            ]])
        )
        return
    keyboard = []
    for s in subjects:
        sid = str(s['_id'])
        keyboard.append([InlineKeyboardButton(f"📖 {s['name']}", callback_data=f'ref:subject:{sid}')])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data=back_cb)])
    await query.edit_message_text(
        "📚 <b>رفرنس‌های درسی</b>\n\n"
        "━━━━━━━━━━━━━━━━\n"
        "درس مورد نظر را انتخاب کنید:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _show_books(query, context, subject_id, back_cb='ref:main'):
    subject = await db.ref_get_subject(subject_id)
    if not subject:
        await query.answer("❌ درس پیدا نشد!", show_alert=True); return
    books = await db.ref_get_books(subject_id)
    if not books:
        await query.edit_message_text(
            f"📖 <b>{subject['name']}</b>\n\n❌ رفرنسی برای این درس تعریف نشده.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data=back_cb)]]))
        return
    keyboard = []
    for b in books:
        bid = str(b['_id'])
        keyboard.append([InlineKeyboardButton(f"📘 {b['name']}", callback_data=f'ref:book:{bid}')])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data=back_cb)])
    await query.edit_message_text(
        f"📖 <b>{subject['name']}</b>\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"رفرنس مورد نظر را انتخاب کنید:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _show_lang_choice(query, context, book_id, back_cb='ref:main'):
    book = await db.ref_get_book(book_id)
    if not book:
        await query.answer("❌ کتاب پیدا نشد!", show_alert=True); return
    files = await db.ref_get_files(book_id)
    langs = {f['lang']: f for f in files}
    if not langs:
        await query.edit_message_text(
            f"📘 <b>{book['name']}</b>\n\n❌ فایلی برای این رفرنس بارگذاری نشده.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data=back_cb)]]))
        return
    keyboard = []
    if 'fa' in langs:
        fid = str(langs['fa']['_id'])
        dl  = langs['fa'].get('downloads', 0)
        keyboard.append([InlineKeyboardButton(f"🇮🇷 ترجمه فارسی | ⬇️ {dl}", callback_data=f'ref:dl:{fid}')])
    if 'en' in langs:
        fid = str(langs['en']['_id'])
        dl  = langs['en'].get('downloads', 0)
        keyboard.append([InlineKeyboardButton(f"🌐 نسخه لاتین (اصلی) | ⬇️ {dl}", callback_data=f'ref:dl:{fid}')])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data=back_cb)])
    await query.edit_message_text(
        f"📘 <b>{book['name']}</b>\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"نسخه مورد نظر را انتخاب کنید:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _download_ref(query, file_id_db, uid):
    item = await db.ref_get_file(file_id_db)
    if not item:
        await query.answer("❌ فایل پیدا نشد!", show_alert=True); return
    await db.ref_inc_download(file_id_db, uid)
    lang_label = "🇮🇷 ترجمه فارسی" if item['lang'] == 'fa' else "🌐 نسخه لاتین"
    try:
        await query.message.reply_document(
            item['file_id'],
            caption=f"📘 {lang_label}\n📥 {item.get('downloads', 0)} دانلود",
            parse_mode='HTML'
        )
    except:
        await query.answer("❌ خطا در ارسال فایل!", show_alert=True)
