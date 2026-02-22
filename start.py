import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from database import db
from utils import main_keyboard, admin_keyboard

logger = logging.getLogger(__name__)

# مراحل ثبت‌نام
REGISTER = 0
STEP_NAME = 10
STEP_STUDENT_ID = 11
STEP_GROUP = 12

ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))

WELCOME_IMG = None  # اگه خواستی عکس خوش‌آمدگویی اضافه کنی


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    first_name = update.effective_user.first_name or ''
    user = await db.get_user(uid)

    if not user:
        # کاربر جدید — شروع ثبت‌نام مرحله‌ای
        context.user_data.clear()
        await update.message.reply_text(
            f"🩺 <b>به ربات آموزشی پزشکی خوش آمدید!</b>\n\n"
            f"سلام <b>{first_name}</b> عزیز 👋\n\n"
            f"این ربات به شما کمک می‌کند:\n"
            f"📚 منابع و جزوات درسی\n"
            f"🎥 آرشیو کلاس‌ها\n"
            f"🧪 بانک سوال و تمرین\n"
            f"📅 برنامه کلاس‌ها و امتحانات\n\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"برای شروع، ابتدا باید ثبت‌نام کنید.\n"
            f"این فرآیند فقط <b>۳ مرحله</b> دارد! 🚀",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ شروع ثبت‌نام", callback_data='register:start')
            ]])
        )
        return REGISTER

    if not user.get('approved') and uid != ADMIN_ID:
        await update.message.reply_text(
            "⏳ <b>در انتظار تأیید</b>\n\n"
            f"سلام {user.get('name','')} عزیز،\n"
            "ثبت‌نام شما انجام شده و در انتظار تأیید ادمین است.\n\n"
            "به زودی دسترسی شما فعال می‌شود. 🙏",
            parse_mode='HTML'
        )
        return ConversationHandler.END

    kb = admin_keyboard() if uid == ADMIN_ID else main_keyboard()
    await update.message.reply_text(
        f"🩺 <b>خوش برگشتید {user.get('name','')} عزیز!</b>",
        parse_mode='HTML', reply_markup=kb
    )
    await show_dashboard_msg(update, context)
    return ConversationHandler.END


async def register_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع ثبت‌نام با دکمه"""
    query = update.callback_query
    await query.answer()

    if query.data == 'register:start':
        context.user_data['reg_step'] = 'name'
        await query.edit_message_text(
            "📝 <b>مرحله ۱ از ۳ — نام و نام خانوادگی</b>\n\n"
            "👤 لطفاً نام و نام خانوادگی کامل خود را بنویسید:\n\n"
            "<i>مثال: علی احمدی</i>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ انصراف", callback_data='register:cancel')
            ]])
        )
        return STEP_NAME

    elif query.data == 'register:cancel':
        await query.edit_message_text(
            "❌ ثبت‌نام لغو شد.\n\nبرای شروع مجدد /start بزنید.",
            parse_mode='HTML'
        )
        return ConversationHandler.END

    elif query.data == 'register:group1':
        return await _save_group(update, context, '1')

    elif query.data == 'register:group2':
        return await _save_group(update, context, '2')


async def step_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت نام"""
    name = update.message.text.strip()

    if len(name) < 3:
        await update.message.reply_text(
            "⚠️ نام باید حداقل ۳ حرف باشد.\n\n👤 لطفاً نام و نام خانوادگی کامل خود را بنویسید:"
        )
        return STEP_NAME

    if len(name) > 50:
        await update.message.reply_text("⚠️ نام نباید بیشتر از ۵۰ حرف باشد:")
        return STEP_NAME

    context.user_data['reg_name'] = name
    context.user_data['reg_step'] = 'student_id'

    await update.message.reply_text(
        f"✅ <b>نام ثبت شد:</b> {name}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📝 <b>مرحله ۲ از ۳ — کد دانشجویی</b>\n\n"
        f"🎓 لطفاً کد دانشجویی خود را وارد کنید:\n\n"
        f"<i>مثال: 14031234</i>",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ انصراف", callback_data='register:cancel')
        ]])
    )
    return STEP_STUDENT_ID


async def step_student_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت کد دانشجویی"""
    sid = update.message.text.strip()

    if not sid.isdigit():
        await update.message.reply_text(
            "⚠️ کد دانشجویی باید فقط عدد باشد.\n\n🎓 مجدداً وارد کنید:"
        )
        return STEP_STUDENT_ID

    if len(sid) < 5 or len(sid) > 12:
        await update.message.reply_text(
            "⚠️ کد دانشجویی باید بین ۵ تا ۱۲ رقم باشد.\n\n🎓 مجدداً وارد کنید:"
        )
        return STEP_STUDENT_ID

    # چک تکراری بودن
    existing = await db.users.find_one({'student_id': sid})
    if existing and existing['user_id'] != update.effective_user.id:
        await update.message.reply_text(
            "❌ این کد دانشجویی قبلاً ثبت شده است.\n\n"
            "اگر فکر می‌کنید اشتباهی رخ داده با ادمین تماس بگیرید.\n\n"
            "🎓 کد دانشجویی دیگری وارد کنید:"
        )
        return STEP_STUDENT_ID

    context.user_data['reg_sid'] = sid
    context.user_data['reg_step'] = 'group'

    await update.message.reply_text(
        f"✅ <b>کد دانشجویی ثبت شد:</b> {sid}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📝 <b>مرحله ۳ از ۳ — انتخاب گروه</b>\n\n"
        f"👥 گروه درسی خود را انتخاب کنید:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("👥 گروه ۱", callback_data='register:group1'),
                InlineKeyboardButton("👥 گروه ۲", callback_data='register:group2')
            ],
            [InlineKeyboardButton("❌ انصراف", callback_data='register:cancel')]
        ])
    )
    return STEP_GROUP


async def _save_group(update, context, group):
    """ذخیره گروه و نهایی کردن ثبت‌نام"""
    query = update.callback_query
    uid = update.effective_user.id
    username = update.effective_user.username

    name = context.user_data.get('reg_name', '')
    sid = context.user_data.get('reg_sid', '')

    if not name or not sid:
        await query.edit_message_text(
            "❌ خطایی رخ داد. لطفاً /start بزنید و مجدد ثبت‌نام کنید."
        )
        return ConversationHandler.END

    await db.create_user(uid, name, sid, group, username)

    if uid == ADMIN_ID:
        await db.update_user(uid, {'approved': True})
        await query.edit_message_text(
            f"🎉 <b>ثبت‌نام کامل شد!</b>\n\n"
            f"👤 نام: <b>{name}</b>\n"
            f"🎓 کد دانشجویی: <b>{sid}</b>\n"
            f"👥 گروه: <b>{group}</b>\n"
            f"🔑 نقش: <b>ادمین</b>\n\n"
            f"✅ دسترسی شما فعال است.",
            parse_mode='HTML'
        )
        await context.bot.send_message(uid, "به پنل ادمین خوش آمدید! 👨‍⚕️",
                                        reply_markup=admin_keyboard())
        await _send_dashboard(context, uid)
    else:
        # اطلاع به ادمین
        kb_admin = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ تأیید", callback_data=f'admin:approve:{uid}'),
            InlineKeyboardButton("❌ رد", callback_data=f'admin:reject:{uid}')
        ]])
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"🔔 <b>درخواست ثبت‌نام جدید</b>\n\n"
                f"👤 نام: <b>{name}</b>\n"
                f"🎓 کد دانشجویی: <b>{sid}</b>\n"
                f"👥 گروه: <b>{group}</b>\n"
                f"📱 یوزرنیم: @{username or 'ندارد'}\n"
                f"🆔 آیدی: <code>{uid}</code>",
                parse_mode='HTML', reply_markup=kb_admin
            )
        except Exception as e:
            logger.error(f"Cannot notify admin: {e}")

        await query.edit_message_text(
            f"🎉 <b>ثبت‌نام با موفقیت انجام شد!</b>\n\n"
            f"👤 نام: <b>{name}</b>\n"
            f"🎓 کد دانشجویی: <b>{sid}</b>\n"
            f"👥 گروه: <b>{group}</b>\n\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"⏳ <b>در انتظار تأیید ادمین...</b>\n\n"
            f"به زودی دسترسی شما فعال می‌شود و پیام تأیید دریافت خواهید کرد. 🙏",
            parse_mode='HTML'
        )

    # پاک کردن داده‌های موقت
    for k in ['reg_name', 'reg_sid', 'reg_step']:
        context.user_data.pop(k, None)

    return ConversationHandler.END


async def register_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر قدیمی — فقط برای fallback"""
    return REGISTER


async def _send_dashboard(context, uid):
    from database import db as _db
    from dashboard import build_dashboard_text
    try:
        user = await _db.get_user(uid)
        if user and user.get('approved'):
            text, kb = await build_dashboard_text(uid)
            await context.bot.send_message(uid, text, parse_mode='HTML', reply_markup=kb)
    except Exception as e:
        logger.error(f"Dashboard error: {e}")


async def show_dashboard_msg(update, context):
    from dashboard import build_dashboard_text
    uid = update.effective_user.id
    try:
        text, kb = await build_dashboard_text(uid)
        await update.effective_message.reply_text(text, parse_mode='HTML', reply_markup=kb)
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
