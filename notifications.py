from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db
from utils import NOTIF_LABELS


async def notifications_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split(':')
    action = parts[1] if len(parts) > 1 else 'main'

    if action in ('main', 'settings'):
        await _show_settings(query, update.effective_user.id)
    elif action == 'toggle':
        ntype = parts[2]
        user = await db.get_user(update.effective_user.id)
        current = user.get('notification_settings', {}).get(ntype, True)
        await db.update_user(update.effective_user.id, {f'notification_settings.{ntype}': not current})
        await query.answer(f"{'✅ فعال' if not current else '❌ غیرفعال'} شد")
        await _show_settings(query, update.effective_user.id)
    elif action == 'all_on':
        settings = {f'notification_settings.{k}': True for k in NOTIF_LABELS}
        await db.update_user(update.effective_user.id, settings)
        await _show_settings(query, update.effective_user.id)
    elif action == 'all_off':
        settings = {f'notification_settings.{k}': False for k in NOTIF_LABELS}
        await db.update_user(update.effective_user.id, settings)
        await _show_settings(query, update.effective_user.id)


async def _show_settings(query, uid):
    user = await db.get_user(uid)
    s = user.get('notification_settings', {}) if user else {}
    active = sum(1 for k in NOTIF_LABELS if s.get(k, True))
    keyboard = []
    for key, label in NOTIF_LABELS.items():
        icon = "✅" if s.get(key, True) else "❌"
        keyboard.append([InlineKeyboardButton(f"{icon} {label}", callback_data=f'notif:toggle:{key}')])
    keyboard.append([
        InlineKeyboardButton("✅ همه روشن", callback_data='notif:all_on'),
        InlineKeyboardButton("❌ همه خاموش", callback_data='notif:all_off')
    ])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='dashboard:refresh')])
    await query.edit_message_text(
        f"🔔 <b>تنظیمات اعلان‌ها</b>\nفعال: {active}/{len(NOTIF_LABELS)}",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
    )
