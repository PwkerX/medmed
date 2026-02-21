import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import db
from utils import TERMS, LESSONS, TOPICS, RESOURCE_TYPES, main_keyboard

logger = logging.getLogger(__name__)
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))
BROADCAST = 5


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id

    if uid != ADMIN_ID:
        await query.answer("❌ دسترسی ندارید!", show_alert=True)
        return

    await query.answer()
    data = query.data
    parts = data.split(':')
    action = parts[1] if len(parts) > 1 else 'main'

    if action == 'main':
        await _admin_menu(query)

    elif action == 'stats':
        s = await db.global_stats()
        top = await db.resources.find().sort('metadata.downloads', -1).limit(3).to_list(3)
        text = (
            "📊 <b>آمار سیستم</b>\n━━━━━━━━━━━━━━\n\n"
            f"👥 کاربران: <b>{s['users']}</b>\n"
            f"📚 منابع: <b>{s['resources']}</b>\n"
            f"🎥 ویدیوها: <b>{s['videos']}</b>\n"
            f"🧪 سوالات: <b>{s['questions']}</b>\n"
            f"📥 دانلودها: <b>{s['downloads']}</b>\n\n"
            "🔥 <b>پرطرفدارترین:</b>\n"
        )
        for i, r in enumerate(top, 1):
            text += f"{i}. {r.get('lesson','')} — {r.get('topic','')} | ⬇️{r['metadata'].get('downloads',0)}\n"
        await query.edit_message_text(text, parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 بروزرسانی", callback_data='admin:stats')],
                [InlineKeyboardButton("🔙 بازگشت", callback_data='admin:main')]
            ]))

    elif action == 'users':
        users = await db.all_users(approved_only=False)
        approved = sum(1 for u in users if u.get('approved'))
        text = f"👥 <b>کاربران</b>\n✅ تأیید شده: {approved} | ⏳ در انتظار: {len(users)-approved}\n\n"
        for u in users[:20]:
            icon = "✅" if u.get('approved') else "⏳"
            text += f"{icon} {u.get('name','')} | {u.get('student_id','')} | گروه {u.get('group','')}\n"
        keyboard = [
            [InlineKeyboardButton("⏳ تأیید کاربران", callback_data='admin:pending')],
            [InlineKeyboardButton("🔙 بازگشت", callback_data='admin:main')]
        ]
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

    elif action == 'pending':
        pending = await db.pending_users()
        if not pending:
            await query.edit_message_text("✅ هیچ کاربر در انتظاری نیست.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data='admin:main')]]))
            return
        text = f"⏳ <b>در انتظار تأیید: {len(pending)}</b>\n\n"
        keyboard = []
        for u in pending[:8]:
            uid2 = u['user_id']
            text += f"👤 {u.get('name','')} | {u.get('student_id','')} | @{u.get('username','ندارد')}\n"
            keyboard.append([
                InlineKeyboardButton(f"✅ {u.get('name','')[:15]}", callback_data=f'admin:approve:{uid2}'),
                InlineKeyboardButton("❌ رد", callback_data=f'admin:reject:{uid2}')
            ])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='admin:main')])
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

    elif action == 'approve':
        target_uid = int(parts[2])
        user = await db.get_user(target_uid)
        await db.update_user(target_uid, {'approved': True})
        try:
            await context.bot.send_message(target_uid,
                "✅ <b>دسترسی شما تأیید شد!</b>\n\nاکنون می‌توانید از ربات استفاده کنید.",
                parse_mode='HTML', reply_markup=main_keyboard())
        except: pass
        await query.answer(f"✅ {user.get('name','') if user else ''} تأیید شد!", show_alert=True)
        # رفرش لیست
        pending = await db.pending_users()
        if pending:
            from admin import admin_callback as ac
            query.data = 'admin:pending'
            await admin_callback(update, context)
        else:
            await query.edit_message_text("✅ همه کاربران تأیید شدند.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data='admin:main')]]))

    elif action == 'reject':
        target_uid = int(parts[2])
        await db.users.delete_one({'user_id': target_uid})
        try:
            await context.bot.send_message(target_uid, "❌ درخواست شما رد شد.")
        except: pass
        await query.answer("❌ رد شد.", show_alert=True)
        query.data = 'admin:pending'
        await admin_callback(update, context)

    elif action == 'upload_resource':
        context.user_data['upload_mode'] = 'resource'
        context.user_data['upload_path'] = {}
        await _select_term(query, 'resource')

    elif action == 'upload_video':
        context.user_data['upload_mode'] = 'video'
        context.user_data['upload_path'] = {}
        await _select_lesson_for_video(query)

    elif action == 'set_mode':
        mode = parts[2]
        context.user_data['upload_mode'] = mode
        context.user_data['upload_path'] = {}
        file_id = context.user_data.pop('pending_file_id', '')
        if file_id:
            context.user_data['upload_file_id'] = file_id
        if mode == 'resource':
            await _select_term(query, mode)
        else:
            await _select_lesson_for_video(query)

    elif action == 'sel_term':
        term = ':'.join(parts[2:])
        context.user_data.setdefault('upload_path', {})['term'] = term
        await _select_lesson(query, term)

    elif action == 'sel_lesson':
        lesson = ':'.join(parts[2:])
        context.user_data.setdefault('upload_path', {})['lesson'] = lesson
        mode = context.user_data.get('upload_mode', 'resource')
        if mode == 'video':
            await _select_topic(query, lesson, mode)
        else:
            await _select_topic(query, lesson, mode)

    elif action == 'sel_topic':
        topic = ':'.join(parts[2:])
        context.user_data.setdefault('upload_path', {})['topic'] = topic
        mode = context.user_data.get('upload_mode', 'resource')
        if mode == 'resource':
            await _select_type(query)
        else:
            await _finalize_path(query, context)

    elif action == 'sel_type':
        rtype = ':'.join(parts[2:])
        context.user_data.setdefault('upload_path', {})['type'] = rtype
        await _finalize_path(query, context)

    elif action == 'pending_q':
        await _pending_questions(query)

    elif action == 'approve_q':
        qid = parts[2]
        await db.approve_question(qid)
        await query.answer("✅ سوال تأیید شد!", show_alert=True)
        await _pending_questions(query)

    elif action == 'reject_q':
        qid = parts[2]
        await db.delete_question(qid)
        await query.answer("❌ سوال حذف شد.", show_alert=True)
        await _pending_questions(query)

    elif action == 'add_schedule':
        context.user_data['mode'] = 'add_schedule'
        keyboard = [
            [InlineKeyboardButton("📖 کلاس", callback_data='admin:schedule_type:class')],
            [InlineKeyboardButton("📝 امتحان", callback_data='admin:schedule_type:exam')],
            [InlineKeyboardButton("🔄 جبرانی", callback_data='admin:schedule_type:makeup')],
            [InlineKeyboardButton("🔙 بازگشت", callback_data='admin:main')]
        ]
        await query.edit_message_text("📅 نوع برنامه را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif action == 'schedule_type':
        stype = parts[2]
        context.user_data['schedule_type'] = stype
        context.user_data['mode'] = 'add_schedule'
        await query.edit_message_text(
            f"📅 <b>افزودن برنامه جدید</b>\n\n"
            "فرمت:\n<code>درس, استاد, تاریخ(YYYY-MM-DD), ساعت(HH:MM), مکان, توضیحات(اختیاری)</code>\n\n"
            "مثال:\n<code>آناتومی, دکتر محمدی, 2024-03-20, 09:00, کلاس A2</code>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data='admin:main')]]))

    elif action == 'broadcast':
        context.user_data['mode'] = 'broadcast'
        await query.edit_message_text(
            "📢 <b>ارسال پیام همگانی</b>\n\nپیام را بنویسید:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data='admin:main')]]))
        return BROADCAST

    elif action == 'add_question':
        context.user_data['mode'] = 'add_question'
        await query.edit_message_text(
            "➕ <b>افزودن سوال جدید</b>\n\n"
            "فرمت (با | جدا کنید):\n"
            "<code>درس|مبحث|سختی|سوال|گزینه۱|گزینه۲|گزینه۳|گزینه۴|جواب(1-4)|توضیح</code>\n\n"
            "سختی: <code>آسان 🟢</code> یا <code>متوسط 🟡</code> یا <code>سخت 🔴</code>\n\n"
            "مثال:\n"
            "<code>آناتومی|اندام فوقانی|متوسط 🟡|عصب مدیان از کجا عبور می‌کند?|تونل کارپال|آرنج|مچ|ساعد|1|از تونل کارپال عبور می‌کند</code>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data='admin:main')]]))


async def _admin_menu(query):
    keyboard = [
        [InlineKeyboardButton("📊 آمار سیستم", callback_data='admin:stats')],
        [InlineKeyboardButton("👥 کاربران", callback_data='admin:users'),
         InlineKeyboardButton("⏳ تأیید کاربران", callback_data='admin:pending')],
        [InlineKeyboardButton("📚 آپلود منبع", callback_data='admin:upload_resource'),
         InlineKeyboardButton("🎥 آپلود ویدیو", callback_data='admin:upload_video')],
        [InlineKeyboardButton("➕ افزودن سوال", callback_data='admin:add_question'),
         InlineKeyboardButton("⏳ تأیید سوالات", callback_data='admin:pending_q')],
        [InlineKeyboardButton("📅 افزودن برنامه", callback_data='admin:add_schedule')],
        [InlineKeyboardButton("📢 ارسال همگانی", callback_data='admin:broadcast')]
    ]
    await query.edit_message_text(
        "👨‍⚕️ <b>پنل مدیریت</b>",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _select_term(query, mode):
    keyboard = []
    from utils import TERMS
    for i in range(0, len(TERMS), 2):
        row = [InlineKeyboardButton(TERMS[i], callback_data=f'admin:sel_term:{TERMS[i]}'[:64])]
        if i + 1 < len(TERMS):
            row.append(InlineKeyboardButton(TERMS[i+1], callback_data=f'admin:sel_term:{TERMS[i+1]}'[:64]))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='admin:main')])
    await query.edit_message_text("📚 ترم را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))


async def _select_lesson(query, term):
    keyboard = []
    for i in range(0, len(LESSONS), 2):
        row = [InlineKeyboardButton(LESSONS[i], callback_data=f'admin:sel_lesson:{LESSONS[i]}'[:64])]
        if i + 1 < len(LESSONS):
            row.append(InlineKeyboardButton(LESSONS[i+1], callback_data=f'admin:sel_lesson:{LESSONS[i+1]}'[:64]))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='admin:upload_resource')])
    await query.edit_message_text(f"📚 {term}\nدرس را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))


async def _select_lesson_for_video(query):
    keyboard = []
    for i in range(0, len(LESSONS), 2):
        row = [InlineKeyboardButton(LESSONS[i], callback_data=f'admin:sel_lesson:{LESSONS[i]}'[:64])]
        if i + 1 < len(LESSONS):
            row.append(InlineKeyboardButton(LESSONS[i+1], callback_data=f'admin:sel_lesson:{LESSONS[i+1]}'[:64]))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='admin:main')])
    await query.edit_message_text("🎥 درس ویدیو را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))


async def _select_topic(query, lesson, mode):
    topics = TOPICS.get(lesson, ['عمومی', 'پیشرفته'])
    keyboard = [[InlineKeyboardButton(t, callback_data=f'admin:sel_topic:{t}'[:64])] for t in topics]
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='admin:upload_resource')])
    await query.edit_message_text(f"📂 {lesson}\nمبحث را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))


async def _select_type(query):
    keyboard = [[InlineKeyboardButton(rt, callback_data=f'admin:sel_type:{rt}'[:64])] for rt in RESOURCE_TYPES]
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='admin:upload_resource')])
    await query.edit_message_text("📄 نوع فایل را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))


async def _finalize_path(query, context):
    path = context.user_data.get('upload_path', {})
    mode = context.user_data.get('upload_mode', 'resource')
    p_text = f"ترم: {path.get('term','')}\nدرس: {path.get('lesson','')}\nمبحث: {path.get('topic','')}"
    if mode == 'resource':
        p_text += f"\nنوع: {path.get('type','')}"
    has_file = bool(context.user_data.get('upload_file_id'))
    if has_file:
        # فایل از قبل داریم، مستقیم متادیتا بخوا
        prompt = "متادیتا:\n`نسخه, تگ‌ها, اهمیت(1-5), توضیحات`" if mode == 'resource' else "متادیتا:\n`استاد, تاریخ(YYYY-MM-DD), توضیح`"
        await query.edit_message_text(
            f"✅ <b>مسیر انتخاب شد:</b>\n{p_text}\n\n{prompt}",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data='admin:main')]]))
    else:
        await query.edit_message_text(
            f"✅ <b>مسیر انتخاب شد:</b>\n{p_text}\n\n📤 <b>حالا فایل را ارسال کنید.</b>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data='admin:main')]]))


async def _pending_questions(query):
    questions = await db.pending_questions()
    if not questions:
        await query.edit_message_text("✅ هیچ سوال در انتظاری نیست.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data='admin:main')]]))
        return
    text = f"⏳ <b>سوالات در انتظار: {len(questions)}</b>\n\n"
    keyboard = []
    for q in questions[:5]:
        qid = str(q['_id'])
        short = q['question'][:40] + '...' if len(q['question']) > 40 else q['question']
        text += f"📌 {q.get('lesson','')} | {q.get('topic','')}\n❓ {short}\n\n"
        keyboard.append([
            InlineKeyboardButton("✅ تأیید", callback_data=f'admin:approve_q:{qid}'),
            InlineKeyboardButton("❌ حذف", callback_data=f'admin:reject_q:{qid}')
        ])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='admin:main')])
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def admin_broadcast_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    if context.user_data.get('mode') != 'broadcast':
        return ConversationHandler.END

    msg = update.message.text
    users = await db.all_users(approved_only=True)
    sent = failed = 0
    for u in users:
        if u['user_id'] != ADMIN_ID:
            try:
                await context.bot.send_message(u['user_id'],
                    f"📢 <b>پیام ادمین:</b>\n\n{msg}", parse_mode='HTML')
                sent += 1
            except:
                failed += 1

    await update.message.reply_text(
        f"📢 ارسال تمام شد!\n✅ {sent} نفر\n❌ {failed} ناموفق"
    )
    context.user_data.pop('mode', None)
    return ConversationHandler.END
