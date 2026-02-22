import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import db
from utils import main_keyboard, admin_keyboard

logger = logging.getLogger(__name__)
REGISTER = 0
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = await db.get_user(uid)

    if not user:
        await update.message.reply_text(
            "🩺 *به ربات پزشکی خوش آمدید!*\n\n"
            "برای ثبت‌نام اطلاعات را وارد کنید:\n"
            "`نام, شماره دانشجویی, گروه`\n\n"
            "مثال: `علی احمدی, 14031234, A`",
            parse_mode='Markdown'
        )
        return REGISTER

    if not user.get('approved') and uid != ADMIN_ID:
        await update.message.reply_text("⏳ دسترسی شما هنوز تأیید نشده است.")
        return ConversationHandler.END

    kb = admin_keyboard() if uid == ADMIN_ID else main_keyboard()
    await update.message.reply_text(f"🩺 خوش آمدید {user['name']} عزیز!", reply_markup=kb)
    await show_dashboard_msg(update, context)
    return ConversationHandler.END


async def register_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    username = update.effective_user.username
    text = update.message.text.strip()

    try:
        parts = [x.strip() for x in text.split(',')]
        if len(parts) != 3:
            raise ValueError()
        name, student_id, group = parts

        existing = await db.users.find_one({'student_id': student_id})
        if existing and existing['user_id'] != uid:
            await update.message.reply_text("❌ این شماره دانشجویی قبلاً ثبت شده است.")
            return REGISTER

        await db.create_user(uid, name, student_id, group.upper(), username)

        if uid == ADMIN_ID:
            await db.update_user(uid, {'approved': True})
            await update.message.reply_text("✅ ثبت‌نام موفق! (ادمین)", reply_markup=admin_keyboard())
            await show_dashboard_msg(update, context)
        else:
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ تأیید", callback_data=f'admin:approve:{uid}'),
                InlineKeyboardButton("❌ رد", callback_data=f'admin:reject:{uid}')
            ]])
            try:
                await context.bot.send_message(
                    ADMIN_ID,
                    f"👤 *کاربر جدید:*\nنام: {name}\nشماره: {student_id}\nگروه: {group}\n@{username or 'ندارد'}",
                    parse_mode='Markdown', reply_markup=kb
                )
            except Exception as e:
                logger.error(f"Cannot notify admin: {e}")
            await update.message.reply_text("✅ ثبت‌نام انجام شد!\n⏳ منتظر تأیید ادمین بمانید.")

    except ValueError:
        await update.message.reply_text(
            "❌ فرمت اشتباه!\nمثال: `علی احمدی, 14031234, A`",
            parse_mode='Markdown'
        )
        return REGISTER

    return ConversationHandler.END


async def show_dashboard_msg(update, context):
    from dashboard import build_dashboard_text
    uid = update.effective_user.id
    try:
        text, kb = await build_dashboard_text(uid)
        await update.effective_message.reply_text(text, parse_mode='HTML', reply_markup=kb)
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
