"""
بخش سوالات متداول — دانشجو
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db

logger = logging.getLogger(__name__)


async def faq_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    parts = data.split(':')
    action = parts[1] if len(parts) > 1 else 'main'

    if action == 'main':
        await _faq_categories(query)

    elif action == 'cat':
        category = ':'.join(parts[2:])
        await _faq_list(query, category)

    elif action == 'item':
        idx = int(parts[2])
        cat = ':'.join(parts[3:])
        await _faq_answer(query, context, idx, cat)


async def _faq_categories(query):
    cats = await db.faq_get_categories()
    keyboard = [[InlineKeyboardButton(f"📂 {c}", callback_data=f'faq:cat:{c}')] for c in cats]
    keyboard.append([InlineKeyboardButton("📋 همه سوالات", callback_data='faq:cat:همه')])

    await query.edit_message_text(
        "❓ <b>سوالات متداول</b>\n\n"
        "━━━━━━━━━━━━━━━━\n"
        "دسته‌بندی مورد نظر را انتخاب کنید:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _faq_list(query, category):
    faqs = await db.faq_get_all()
    if category != 'همه':
        faqs = [f for f in faqs if f.get('category') == category]

    if not faqs:
        await query.edit_message_text(
            "❌ سوالی ثبت نشده.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 بازگشت", callback_data='faq:main')
            ]])
        )
        return

    keyboard = []
    for i, f in enumerate(faqs):
        keyboard.append([InlineKeyboardButton(
            f"❓ {f['question'][:40]}",
            callback_data=f'faq:item:{i}:{category}'
        )])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='faq:main')])

    await query.edit_message_text(
        f"❓ <b>سوالات متداول — {category}</b>\n\n"
        "روی هر سوال کلیک کنید تا جواب ببینید:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _faq_answer(query, context, idx, cat):
    faqs = await db.faq_get_all()
    if cat != 'همه':
        faqs = [f for f in faqs if f.get('category') == cat]

    if idx >= len(faqs):
        await query.answer("❌ سوال پیدا نشد!", show_alert=True)
        return

    f = faqs[idx]
    await query.edit_message_text(
        f"❓ <b>{f['question']}</b>\n\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"💡 {f['answer']}",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت", callback_data=f'faq:cat:{cat}')]
        ])
    )
