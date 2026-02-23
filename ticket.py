"""تیکت پشتیبانی"""
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db

logger = logging.getLogger(__name__)
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))

TICKET_WAITING = 60
TICKET_REPLY_WAITING = 61

SUBJECTS = [
    "🔬 مشکل در بخش علوم پایه",
    "📚 مشکل در بخش رفرنس‌ها",
    "🧪 مشکل در بانک سوال",
    "📅 مشکل در برنامه/امتحانات",
    "👤 مشکل حساب کاربری",
    "⚙️ مشکل فنی",
    "💡 پیشنهاد",
    "❓ سوال دیگر",
]


async def ticket_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    data = query.data
    parts = data.split(':')
    action = parts[1] if len(parts) > 1 else 'main'

    if action == 'main':
        await _ticket_main(query, uid)

    elif action == 'new':
        keyboard = [[InlineKeyboardButton(s, callback_data=f'ticket:subject:{i}')] for i, s in enumerate(SUBJECTS)]
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='ticket:main')])
        await query.edit_message_text(
            "🎫 <b>تیکت جدید</b>\n\nموضوع مشکل را انتخاب کنید:",
            parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif action == 'subject':
        idx = int(parts[2])
        subject = SUBJECTS[idx]
        context.user_data['ticket_subject'] = subject
        context.user_data['ticket_mode'] = 'waiting_message'
        await query.edit_message_text(
            f"🎫 <b>{subject}</b>\n\n"
            "توضیح کامل مشکل خود را بنویسید:\n"
            "<i>هرچه دقیق‌تر بنویسید، سریع‌تر پاسخ می‌گیرید.</i>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data='ticket:main')]])
        )
        return TICKET_WAITING

    elif action == 'list':
        await _ticket_list(query, uid)

    elif action == 'view':
        tid = int(parts[2])
        ticket = await db.ticket_get(tid)
        if not ticket or ticket['user_id'] != uid:
            await query.answer("❌ تیکت پیدا نشد!", show_alert=True)
            return
        status_icon = "🟢 پاسخ داده شده" if ticket['status'] == 'closed' else "🟡 در انتظار پاسخ"
        text = (
            f"🎫 <b>تیکت #{ticket['ticket_id']}</b>\n"
            f"📋 {ticket.get('subject','')}\n"
            f"🔘 وضعیت: {status_icon}\n"
            f"📅 {ticket['created_at'][:10]}\n\n"
            f"💬 <b>پیام شما:</b>\n{ticket['message']}\n"
        )
        if ticket.get('reply'):
            text += f"\n━━━━━━━━━━━━━━━━\n✅ <b>پاسخ پشتیبانی:</b>\n{ticket['reply']}"
        await query.edit_message_text(
            text, parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data='ticket:list')]])
        )

    # ── ادمین ──
    elif action == 'admin_list':
        if uid != ADMIN_ID: return
        await _admin_ticket_list(query)

    elif action == 'admin_view':
        if uid != ADMIN_ID: return
        tid = int(parts[2])
        ticket = await db.ticket_get(tid)
        if not ticket:
            await query.answer("❌ پیدا نشد!", show_alert=True)
            return
        text = (
            f"🎫 <b>تیکت #{ticket['ticket_id']}</b>\n"
            f"👤 {ticket.get('user_name','')} | آیدی: <code>{ticket['user_id']}</code>\n"
            f"📋 {ticket.get('subject','')}\n"
            f"📅 {ticket['created_at'][:10]}\n\n"
            f"💬 <b>پیام:</b>\n{ticket['message']}"
        )
        keyboard = []
        if ticket['status'] == 'open':
            keyboard.append([InlineKeyboardButton("✏️ پاسخ دادن", callback_data=f'ticket:admin_reply:{tid}')])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='ticket:admin_list')])
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

    elif action == 'admin_reply':
        if uid != ADMIN_ID: return
        tid = int(parts[2])
        context.user_data['replying_ticket'] = tid
        context.user_data['ticket_mode'] = 'admin_reply'
        await query.edit_message_text(
            f"✏️ <b>پاسخ به تیکت #{tid}</b>\n\nپاسخ خود را بنویسید:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data='ticket:admin_list')]])
        )
        return TICKET_REPLY_WAITING


async def _ticket_main(query, uid):
    tickets = await db.ticket_get_user(uid)
    open_count = sum(1 for t in tickets if t['status'] == 'open')
    closed_count = sum(1 for t in tickets if t['status'] == 'closed')
    keyboard = [
        [InlineKeyboardButton("🎫 تیکت جدید", callback_data='ticket:new')],
        [InlineKeyboardButton(f"📋 تیکت‌های من ({len(tickets)})", callback_data='ticket:list')],
    ]
    if uid == ADMIN_ID:
        open_tickets = await db.ticket_get_all('open')
        keyboard.append([InlineKeyboardButton(f"🔔 تیکت‌های باز ({len(open_tickets)})", callback_data='ticket:admin_list')])
    await query.edit_message_text(
        f"🎫 <b>پشتیبانی</b>\n\n"
        f"🟡 باز: {open_count}  |  🟢 بسته: {closed_count}\n\n"
        "برای ارسال مشکل یا سوال، تیکت جدید بزنید:",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _ticket_list(query, uid):
    tickets = await db.ticket_get_user(uid)
    if not tickets:
        await query.edit_message_text(
            "📋 هیچ تیکتی ندارید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data='ticket:main')]])
        )
        return
    keyboard = []
    for t in tickets[:10]:
        icon = "🟢" if t['status'] == 'closed' else "🟡"
        keyboard.append([InlineKeyboardButton(
            f"{icon} #{t['ticket_id']} — {t.get('subject','')[:25]}",
            callback_data=f'ticket:view:{t["ticket_id"]}'
        )])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='ticket:main')])
    await query.edit_message_text(
        "📋 <b>تیکت‌های من</b>", parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _admin_ticket_list(query):
    tickets = await db.ticket_get_all('open')
    if not tickets:
        await query.edit_message_text(
            "✅ هیچ تیکت بازی وجود ندارد!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data='admin:main')]])
        )
        return
    keyboard = []
    for t in tickets[:15]:
        keyboard.append([InlineKeyboardButton(
            f"🟡 #{t['ticket_id']} — {t.get('user_name','')[:10]} — {t.get('subject','')[:20]}",
            callback_data=f'ticket:admin_view:{t["ticket_id"]}'
        )])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='admin:main')])
    await query.edit_message_text(
        f"🎫 <b>تیکت‌های باز</b> — {len(tickets)} تیکت",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def ticket_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = await db.get_user(uid)
    mode = context.user_data.get('ticket_mode', '')
    text = update.message.text.strip()

    if mode == 'waiting_message':
        subject = context.user_data.get('ticket_subject', 'سوال')
        name = user.get('name', '') if user else ''
        tid = await db.ticket_create(uid, name, subject, text)
        context.user_data['ticket_mode'] = ''
        # اطلاع به ادمین
        try:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            await context.bot.send_message(
                ADMIN_ID,
                f"🔔 <b>تیکت جدید #{tid}</b>\n"
                f"👤 {name}\n📋 {subject}\n\n💬 {text[:200]}",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(f"✏️ پاسخ به #{tid}", callback_data=f'ticket:admin_view:{tid}')
                ]])
            )
        except: pass
        await update.message.reply_text(
            f"✅ <b>تیکت #{tid} ثبت شد!</b>\n\n"
            "به زودی پاسخ داده خواهد شد. 🙏",
            parse_mode='HTML'
        )

    elif mode == 'admin_reply' and uid == ADMIN_ID:
        tid = context.user_data.get('replying_ticket')
        if tid:
            await db.ticket_reply(tid, text)
            ticket = await db.ticket_get(tid)
            context.user_data['ticket_mode'] = ''
            # ارسال پاسخ به کاربر
            if ticket:
                try:
                    await context.bot.send_message(
                        ticket['user_id'],
                        f"✅ <b>پاسخ تیکت #{tid}</b>\n\n"
                        f"📋 {ticket.get('subject','')}\n\n"
                        f"💬 {text}",
                        parse_mode='HTML'
                    )
                except: pass
            await update.message.reply_text(f"✅ پاسخ به تیکت #{tid} ارسال شد!")
