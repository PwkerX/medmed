import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import db
from utils import main_keyboard, admin_keyboard

logger = logging.getLogger(__name__)
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))
BROADCAST = 5
RESOURCE_TYPES = ['📄 جزوه', '📊 پاورپوینت', '📝 نکات', '🧠 خلاصه', '🧪 تست', '🎙 ویس']
TERMS = ['ترم ۱', 'ترم ۲', 'ترم ۳', 'ترم ۴', 'ترم ۵', 'ترم ۶', 'ترم ۷']


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

    # ─── MAIN MENU ───
    if action == 'main':
        await _admin_menu(query)

    # ─── STATS ───
    elif action == 'stats':
        s = await db.global_stats()
        text = (
            "📊 <b>آمار سیستم</b>\n━━━━━━━━━━━━━━━━\n\n"
            f"👥 کاربران تأیید: <b>{s['users']}</b>  |  ⏳ منتظر: <b>{s['pending']}</b>\n"
            f"🆕 کاربر جدید این هفته: <b>{s.get('new_users_week',0)}</b>\n"
            f"🎓 ادمین محتوا: <b>{s.get('content_admins',0)}</b>\n\n"
            f"🔬 علوم پایه:\n"
            f"  📖 درس‌ها: <b>{s.get('bs_lessons',0)}</b>  |  📌 جلسات: <b>{s.get('bs_sessions',0)}</b>  |  📁 فایل: <b>{s.get('bs_content',0)}</b>\n\n"
            f"📚 رفرنس‌ها:\n"
            f"  📖 درس‌ها: <b>{s.get('ref_subjects',0)}</b>  |  📘 کتاب: <b>{s.get('ref_books',0)}</b>\n\n"
            f"🧪 بانک سوال: <b>{s['questions']}</b>  |  📁 فایل: <b>{s.get('qbank_files',0)}</b>\n"
            f"🎫 تیکت‌های باز: <b>{s.get('open_tickets',0)}</b>"
        )
        await query.edit_message_text(text, parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 بروزرسانی", callback_data='admin:stats')],
                [InlineKeyboardButton("🔙 بازگشت", callback_data='admin:main')]
            ]))

    # ─── USER LIST ───
    elif action == 'users':
        await _show_users_list(query, page=int(parts[2]) if len(parts) > 2 else 0)

    # ─── USER DETAIL ───
    elif action == 'user_detail':
        target_uid = int(parts[2])
        user = await db.get_user(target_uid)
        if not user:
            await query.answer("کاربر پیدا نشد!", show_alert=True)
            return
        stats = await db.user_stats(target_uid)
        status = "✅ تأیید شده" if user.get('approved') else "⏳ در انتظار"
        text = (
            f"👤 <b>پروفایل کاربر</b>\n━━━━━━━━━━━━━━\n\n"
            f"📛 نام: <b>{user.get('name','')}</b>\n"
            f"🎓 شماره دانشجویی: <b>{user.get('student_id','')}</b>\n"
            f"👥 گروه: <b>{user.get('group','')}</b>\n"
            f"📱 یوزرنیم: @{user.get('username','ندارد')}\n"
            f"📅 ثبت‌نام: {user.get('registered_at','')[:10]}\n"
            f"🔘 وضعیت: {status}\n\n"
            f"📊 <b>آمار:</b>\n"
            f"📥 دانلود: {stats['downloads']} | 🧪 سوال: {stats['total_answers']} | ✅ صحیح: {stats['correct_answers']}"
        )
        keyboard = [
            [InlineKeyboardButton("✏️ ویرایش نام", callback_data=f'admin:edit_name:{target_uid}'),
             InlineKeyboardButton("✏️ ویرایش گروه", callback_data=f'admin:edit_group:{target_uid}')],
            [InlineKeyboardButton("✏️ ویرایش شماره", callback_data=f'admin:edit_sid:{target_uid}')],
        ]
        if user.get('approved'):
            keyboard.append([InlineKeyboardButton("🚫 تعلیق کاربر", callback_data=f'admin:suspend:{target_uid}')])
        else:
            keyboard.append([InlineKeyboardButton("✅ تأیید", callback_data=f'admin:approve:{target_uid}'),
                              InlineKeyboardButton("❌ رد", callback_data=f'admin:reject:{target_uid}')])
        keyboard.append([InlineKeyboardButton("🗑 حذف کامل کاربر", callback_data=f'admin:confirm_delete_user:{target_uid}')])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='admin:users')])
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

    # ─── EDIT USER FIELDS ───
    elif action in ('edit_name', 'edit_group', 'edit_sid'):
        target_uid = int(parts[2])
        field_map = {'edit_name': ('name', 'نام'), 'edit_group': ('group', 'گروه'), 'edit_sid': ('student_id', 'شماره دانشجویی')}
        field, label = field_map[action]
        context.user_data['edit_user'] = {'uid': target_uid, 'field': field, 'label': label}
        context.user_data['mode'] = 'edit_user'
        await query.edit_message_text(
            f"✏️ <b>ویرایش {label}</b>\n\nمقدار جدید را وارد کنید:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data=f'admin:user_detail:{target_uid}')]]))

    # ─── SUSPEND USER ───
    elif action == 'suspend':
        target_uid = int(parts[2])
        await db.update_user(target_uid, {'approved': False})
        try:
            await context.bot.send_message(target_uid, "⚠️ دسترسی شما موقتاً تعلیق شد.")
        except:
            pass
        await query.answer("🚫 کاربر تعلیق شد!", show_alert=True)
        await _show_users_list(query, 0)

    # ─── CONFIRM DELETE USER ───
    elif action == 'confirm_delete_user':
        target_uid = int(parts[2])
        user = await db.get_user(target_uid)
        name = user.get('name', '') if user else ''
        keyboard = [
            [InlineKeyboardButton("⚠️ بله، حذف کن", callback_data=f'admin:delete_user:{target_uid}')],
            [InlineKeyboardButton("❌ لغو", callback_data=f'admin:user_detail:{target_uid}')]
        ]
        await query.edit_message_text(
            f"⚠️ <b>حذف کاربر</b>\n\nآیا مطمئنی می‌خواهی <b>{name}</b> را کاملاً حذف کنی؟\nاین عمل قابل بازگشت نیست!",
            parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

    # ─── DELETE USER ───
    elif action == 'delete_user':
        target_uid = int(parts[2])
        user = await db.get_user(target_uid)
        name = user.get('name', '') if user else ''
        await db.delete_user(target_uid)
        try:
            await context.bot.send_message(target_uid, "❌ حساب شما حذف شد.")
        except:
            pass
        await query.answer(f"🗑 {name} حذف شد!", show_alert=True)
        await _show_users_list(query, 0)

    # ─── PENDING USERS ───
    elif action == 'pending':
        await _show_pending(query)

    # ─── APPROVE USER ───
    elif action == 'approve':
        target_uid = int(parts[2])
        user = await db.get_user(target_uid)
        await db.update_user(target_uid, {'approved': True})
        try:
            await context.bot.send_message(target_uid,
                "✅ <b>دسترسی شما تأیید شد!</b>\nمی‌توانید از ربات استفاده کنید.",
                parse_mode='HTML', reply_markup=main_keyboard())
        except:
            pass
        await query.answer(f"✅ تأیید شد!", show_alert=True)
        await _show_pending(query)

    # ─── REJECT USER ───
    elif action == 'reject':
        target_uid = int(parts[2])
        await db.delete_user(target_uid)
        try:
            await context.bot.send_message(target_uid, "❌ درخواست شما رد شد.")
        except:
            pass
        await query.answer("❌ رد شد.", show_alert=True)
        await _show_pending(query)

    # ─── LESSON MANAGEMENT ───
    elif action == 'manage_lessons':
        await _show_lesson_management(query)

    elif action == 'add_lesson_prompt':
        context.user_data['mode'] = 'add_lesson'
        await query.edit_message_text(
            "➕ <b>افزودن درس جدید</b>\n\nنام درس را بنویسید:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data='admin:manage_lessons')]]))

    elif action == 'del_lesson':
        lesson = ':'.join(parts[2:])
        await db.delete_lesson(lesson)
        await query.answer(f"🗑 {lesson} حذف شد!", show_alert=True)
        await _show_lesson_management(query)

    # ─── TOPIC MANAGEMENT ───
    elif action == 'manage_topics':
        lesson = ':'.join(parts[2:])
        context.user_data['managing_lesson'] = lesson
        await _show_topic_management(query, lesson)

    elif action == 'add_topic_prompt':
        lesson = ':'.join(parts[2:])
        context.user_data['mode'] = 'add_topic'
        context.user_data['managing_lesson'] = lesson
        await query.edit_message_text(
            f"➕ <b>افزودن مبحث به {lesson}</b>\n\nنام مبحث را بنویسید:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data=f'admin:manage_topics:{lesson}')]]))

    elif action == 'del_topic':
        lesson = parts[2]
        topic = ':'.join(parts[3:])
        await db.delete_topic(lesson, topic)
        await query.answer(f"🗑 {topic} حذف شد!", show_alert=True)
        await _show_topic_management(query, lesson)

    # ─── UPLOAD RESOURCE ───
    elif action == 'upload_resource':
        context.user_data['upload_mode'] = 'resource'
        context.user_data['upload_path'] = {}
        await _select_term(query)

    elif action == 'upload_video':
        context.user_data['upload_mode'] = 'video'
        context.user_data['upload_path'] = {}
        await _select_lesson_dynamic(query, 'admin:upload_video')

    elif action == 'set_mode':
        mode = parts[2]
        context.user_data['upload_mode'] = mode
        context.user_data['upload_path'] = {}
        file_id = context.user_data.pop('pending_file_id', '')
        if file_id:
            context.user_data['upload_file_id'] = file_id
        if mode == 'resource':
            await _select_term(query)
        else:
            await _select_lesson_dynamic(query, 'admin:main')

    elif action == 'sel_term':
        term = ':'.join(parts[2:])
        context.user_data.setdefault('upload_path', {})['term'] = term
        await _select_lesson_dynamic(query, f'admin:sel_term:{term}')

    elif action == 'sel_lesson':
        lesson = ':'.join(parts[2:])
        context.user_data.setdefault('upload_path', {})['lesson'] = lesson
        mode = context.user_data.get('upload_mode', 'resource')
        await _select_topic_dynamic(query, lesson, mode)

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

    # ─── DELETE CONTENT ───
    elif action == 'del_resource':
        rid = parts[2]
        await db.delete_resource(rid)
        await query.answer("🗑 منبع حذف شد!", show_alert=True)
        await _admin_menu(query)

    elif action == 'del_video':
        vid = parts[2]
        await db.delete_video(vid)
        await query.answer("🗑 ویدیو حذف شد!", show_alert=True)
        await _admin_menu(query)

    # ─── QUESTIONS ───
    elif action == 'content_admins':
        # لیست ادمین‌های محتوا
        admins = await db.get_content_admins()
        keyboard = []
        for a in admins:
            uid_a = a['user_id']
            keyboard.append([
                InlineKeyboardButton(f"🎓 {a.get('name','')} | {a.get('student_id','')}",
                    callback_data=f'admin:ca_detail:{uid_a}'),
                InlineKeyboardButton("❌ حذف دسترسی", callback_data=f'admin:ca_remove:{uid_a}')
            ])
        keyboard.append([InlineKeyboardButton("➕ دادن دسترسی به کاربر", callback_data='admin:ca_grant')])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='admin:stats')])
        await query.edit_message_text(
            f"🎓 <b>ادمین‌های محتوا</b> — {len(admins)} نفر\n\n"
            "این افراد می‌توانند محتوای علوم پایه را مدیریت کنند:",
            parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif action == 'ca_grant':
        # انتخاب کاربر برای دادن دسترسی
        users = await db.all_users(approved_only=True)
        keyboard = []
        for u in users[:20]:
            uid_u = u['user_id']
            role = u.get('role','student')
            if role == 'content_admin':
                continue
            keyboard.append([InlineKeyboardButton(
                f"👤 {u.get('name','')} | گروه {u.get('group','')}",
                callback_data=f'admin:ca_set:{uid_u}'
            )])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='admin:content_admins')])
        await query.edit_message_text(
            "➕ <b>دادن دسترسی ادمین محتوا</b>\n\nکاربر را انتخاب کنید:",
            parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif action == 'ca_set':
        target_uid = int(parts[2])
        await db.update_user(target_uid, {'role': 'content_admin'})
        u = await db.get_user(target_uid)
        name = u.get('name','') if u else ''
        # ارسال کیبورد جدید به کاربر
        from utils import content_admin_keyboard
        try:
            await context.bot.send_message(
                target_uid,
                "🎓 <b>دسترسی ادمین محتوا فعال شد!</b>\n\n"
                "حالا می‌توانید محتوای علوم پایه را مدیریت کنید.\n"
                "از دکمه «🎓 پنل محتوا» استفاده کنید.",
                parse_mode='HTML',
                reply_markup=content_admin_keyboard()
            )
        except:
            pass
        await query.edit_message_text(
            f"✅ دسترسی ادمین محتوا به «{name}» داده شد.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 بازگشت", callback_data='admin:content_admins')
            ]])
        )

    elif action == 'ca_remove':
        target_uid = int(parts[2])
        await db.update_user(target_uid, {'role': 'student'})
        u = await db.get_user(target_uid)
        name = u.get('name','') if u else ''
        from utils import main_keyboard
        try:
            await context.bot.send_message(
                target_uid,
                "❌ دسترسی ادمین محتوای شما لغو شد.",
                reply_markup=main_keyboard()
            )
        except:
            pass
        await query.edit_message_text(
            f"✅ دسترسی «{name}» لغو شد.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 بازگشت", callback_data='admin:content_admins')
            ]])
        )

    elif action == 'qbank_manage':
        keyboard = [
            [InlineKeyboardButton("📤 آپلود فایل بانک سوال", callback_data='admin:upload_qbank')],
            [InlineKeyboardButton("🗑 حذف فایل‌های بانک سوال", callback_data='admin:list_qbank')],
            [InlineKeyboardButton("🔙 بازگشت", callback_data='admin:stats')]
        ]
        await query.edit_message_text(
            "🧪 <b>مدیریت بانک سوال</b>",
            parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
        )

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

    elif action == 'add_question':
        context.user_data['mode'] = 'add_question'
        await query.edit_message_text(
            "➕ <b>افزودن سوال</b>\n\nفرمت (با | جدا کنید):\n"
            "<code>درس|مبحث|سختی|سوال|گزینه۱|گزینه۲|گزینه۳|گزینه۴|جواب(1-4)|توضیح</code>\n\n"
            "سختی: <code>آسان 🟢</code> یا <code>متوسط 🟡</code> یا <code>سخت 🔴</code>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data='admin:main')]]))

    # ─── SCHEDULE ───
    elif action == 'add_schedule':
        keyboard = [
            [InlineKeyboardButton("📖 کلاس", callback_data='admin:schedule_type:class')],
            [InlineKeyboardButton("📝 امتحان", callback_data='admin:schedule_type:exam')],
            [InlineKeyboardButton("🔄 جبرانی", callback_data='admin:schedule_type:makeup')],
            [InlineKeyboardButton("🔙 بازگشت", callback_data='admin:main')]
        ]
        await query.edit_message_text("📅 نوع برنامه:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif action == 'schedule_type':
        stype = parts[2]
        context.user_data['schedule_type'] = stype
        context.user_data['mode'] = 'add_schedule'
        await query.edit_message_text(
            "📅 <b>برنامه جدید</b>\n\n"
            "<code>درس, استاد, تاریخ(YYYY-MM-DD), ساعت(HH:MM), مکان, توضیحات(اختیاری)</code>\n\n"
            "مثال: <code>آناتومی, دکتر محمدی, 2024-03-20, 09:00, کلاس A2</code>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data='admin:main')]]))

    # ─── BROADCAST ───
    elif action == 'broadcast':
        context.user_data['mode'] = 'broadcast'
        await query.edit_message_text(
            "📢 <b>ارسال همگانی</b>\n\nپیام را بنویسید:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data='admin:main')]]))
        return BROADCAST

    # ─── LIST CONTENT FOR DELETE ───
    elif action == 'list_resources':
        resources = await db.get_resources()
        if not resources:
            await query.edit_message_text("❌ منبعی ثبت نشده.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data='admin:main')]]))
            return
        keyboard = []
        for r in resources[:10]:
            rid = str(r['_id'])
            label = f"🗑 {r.get('lesson','')} — {r.get('type','')} v{r['metadata'].get('version','1')}"
            keyboard.append([InlineKeyboardButton(label, callback_data=f'admin:del_resource:{rid}')])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='admin:main')])
        await query.edit_message_text("📚 <b>حذف منبع:</b>", parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif action == 'list_videos':
        videos = await db.get_videos()
        if not videos:
            await query.edit_message_text("❌ ویدیویی ثبت نشده.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data='admin:main')]]))
            return
        keyboard = []
        for v in videos[:10]:
            vid = str(v['_id'])
            label = f"🗑 {v.get('lesson','')} | {v.get('teacher','')} | {v.get('date','')}"
            keyboard.append([InlineKeyboardButton(label, callback_data=f'admin:del_video:{vid}')])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='admin:main')])
        await query.edit_message_text("🎥 <b>حذف ویدیو:</b>", parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard))


# ─────────── HELPER FUNCTIONS ───────────

async def _admin_menu(query):
    keyboard = [
        [InlineKeyboardButton("📊 آمار سیستم", callback_data='admin:stats')],
        [InlineKeyboardButton("👥 مدیریت کاربران", callback_data='admin:users'),
         InlineKeyboardButton("⏳ تأیید کاربران", callback_data='admin:pending')],
        [InlineKeyboardButton("📚 آپلود منبع", callback_data='admin:upload_resource'),
         InlineKeyboardButton("🎥 آپلود ویدیو", callback_data='admin:upload_video')],
        [InlineKeyboardButton("🗑 حذف منبع", callback_data='admin:list_resources'),
         InlineKeyboardButton("🗑 حذف ویدیو", callback_data='admin:list_videos')],
        [InlineKeyboardButton("📝 مدیریت درس‌ها", callback_data='admin:manage_lessons')],
        [InlineKeyboardButton("➕ افزودن سوال", callback_data='admin:add_question'),
         InlineKeyboardButton("⏳ تأیید سوالات", callback_data='admin:pending_q')],
        [InlineKeyboardButton("📅 برنامه جدید", callback_data='admin:add_schedule')],
        [InlineKeyboardButton("📢 ارسال همگانی", callback_data='admin:broadcast')]
    ]
    await query.edit_message_text(
        "👨‍⚕️ <b>پنل مدیریت</b>",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _show_users_list(query, page=0):
    all_users = await db.all_users(approved_only=False)
    per_page = 8
    start = page * per_page
    chunk = all_users[start:start + per_page]
    total = len(all_users)
    approved = sum(1 for u in all_users if u.get('approved'))

    text = f"👥 <b>کاربران</b>\n✅ تأیید: {approved} | ⏳ در انتظار: {total-approved} | مجموع: {total}\n\n"
    keyboard = []
    for u in chunk:
        icon = "✅" if u.get('approved') else "⏳"
        label = f"{icon} {u.get('name','')[:15]} | {u.get('student_id','')} | گروه {u.get('group','')}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f'admin:user_detail:{u["user_id"]}')])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ قبلی", callback_data=f'admin:users:{page-1}'))
    if start + per_page < total:
        nav.append(InlineKeyboardButton("بعدی ▶️", callback_data=f'admin:users:{page+1}'))
    if nav:
        keyboard.append(nav)
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='admin:main')])

    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def _show_pending(query):
    pending = await db.pending_users()
    if not pending:
        await query.edit_message_text("✅ هیچ کاربر در انتظاری نیست.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data='admin:main')]]))
        return
    text = f"⏳ <b>در انتظار تأیید: {len(pending)}</b>\n\n"
    keyboard = []
    for u in pending[:8]:
        uid2 = u['user_id']
        text += f"👤 {u.get('name','')} | {u.get('student_id','')} | گروه {u.get('group','')} | @{u.get('username','ندارد')}\n"
        keyboard.append([
            InlineKeyboardButton(f"✅ {u.get('name','')[:12]}", callback_data=f'admin:approve:{uid2}'),
            InlineKeyboardButton("👁 جزئیات", callback_data=f'admin:user_detail:{uid2}'),
            InlineKeyboardButton("❌ رد", callback_data=f'admin:reject:{uid2}')
        ])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='admin:main')])
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def _show_lesson_management(query):
    lessons = await db.get_lessons()
    text = f"📝 <b>مدیریت درس‌ها</b>\n{len(lessons)} درس ثبت شده\n\n"
    keyboard = []
    for l in lessons:
        keyboard.append([
            InlineKeyboardButton(f"📚 {l}", callback_data=f'admin:manage_topics:{l}'[:64]),
            InlineKeyboardButton("🗑", callback_data=f'admin:del_lesson:{l}'[:64])
        ])
    keyboard.append([InlineKeyboardButton("➕ درس جدید", callback_data='admin:add_lesson_prompt')])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='admin:main')])
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def _show_topic_management(query, lesson):
    topics = await db.get_topics(lesson)
    text = f"📂 <b>مباحث {lesson}</b>\n{len(topics)} مبحث\n\n"
    keyboard = []
    for t in topics:
        keyboard.append([
            InlineKeyboardButton(f"📌 {t}", callback_data=f'admin:manage_topics:{lesson}'[:64]),
            InlineKeyboardButton("🗑", callback_data=f'admin:del_topic:{lesson}:{t}'[:64])
        ])
    keyboard.append([InlineKeyboardButton("➕ مبحث جدید", callback_data=f'admin:add_topic_prompt:{lesson}'[:64])])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='admin:manage_lessons')])
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def _select_term(query):
    keyboard = []
    for i in range(0, len(TERMS), 2):
        row = [InlineKeyboardButton(TERMS[i], callback_data=f'admin:sel_term:{TERMS[i]}'[:64])]
        if i + 1 < len(TERMS):
            row.append(InlineKeyboardButton(TERMS[i+1], callback_data=f'admin:sel_term:{TERMS[i+1]}'[:64]))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='admin:main')])
    await query.edit_message_text("📚 ترم را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))


async def _select_lesson_dynamic(query, back):
    lessons = await db.get_lessons()
    keyboard = []
    for i in range(0, len(lessons), 2):
        row = [InlineKeyboardButton(lessons[i], callback_data=f'admin:sel_lesson:{lessons[i]}'[:64])]
        if i + 1 < len(lessons):
            row.append(InlineKeyboardButton(lessons[i+1], callback_data=f'admin:sel_lesson:{lessons[i+1]}'[:64]))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='admin:main')])
    await query.edit_message_text("📚 درس را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))


async def _select_topic_dynamic(query, lesson, mode):
    topics = await db.get_topics(lesson)
    keyboard = [[InlineKeyboardButton(t, callback_data=f'admin:sel_topic:{t}'[:64])] for t in topics]
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='admin:main')])
    await query.edit_message_text(f"📂 <b>{lesson}</b>\nمبحث را انتخاب کنید:", parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard))


async def _select_type(query):
    keyboard = [[InlineKeyboardButton(rt, callback_data=f'admin:sel_type:{rt}'[:64])] for rt in RESOURCE_TYPES]
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='admin:main')])
    await query.edit_message_text("📄 نوع فایل را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))


async def _finalize_path(query, context):
    path = context.user_data.get('upload_path', {})
    mode = context.user_data.get('upload_mode', 'resource')
    p_text = f"درس: {path.get('lesson','')}\nمبحث: {path.get('topic','')}"
    if mode == 'resource':
        p_text = f"ترم: {path.get('term','')}\n" + p_text + f"\nنوع: {path.get('type','')}"
    has_file = bool(context.user_data.get('upload_file_id'))
    if has_file:
        prompt = "متادیتا:\n`نسخه, تگ‌ها, اهمیت(1-5), توضیحات`" if mode == 'resource' else "متادیتا:\n`استاد, تاریخ(YYYY-MM-DD), توضیح`"
        await query.edit_message_text(
            f"✅ <b>مسیر:</b>\n{p_text}\n\n{prompt}", parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data='admin:main')]]))
    else:
        await query.edit_message_text(
            f"✅ <b>مسیر:</b>\n{p_text}\n\n📤 <b>حالا فایل را ارسال کنید.</b>", parse_mode='HTML',
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

    await update.message.reply_text(f"📢 ارسال تمام!\n✅ {sent} نفر | ❌ {failed} ناموفق")
    context.user_data.pop('mode', None)
    return ConversationHandler.END


async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندل کردن متن‌های ادمین برای ویرایش و افزودن"""
    uid = update.effective_user.id
    if uid != ADMIN_ID:
        return False

    mode = context.user_data.get('mode', '')
    text = update.message.text.strip()

    if mode == 'add_lesson':
        ok = await db.add_lesson(text)
        if ok:
            await update.message.reply_text(f"✅ درس «{text}» اضافه شد!")
        else:
            await update.message.reply_text(f"❌ درس «{text}» قبلاً وجود دارد.")
        context.user_data.pop('mode', None)
        return True

    elif mode == 'add_topic':
        lesson = context.user_data.get('managing_lesson', '')
        ok = await db.add_topic(lesson, text)
        if ok:
            await update.message.reply_text(f"✅ مبحث «{text}» به {lesson} اضافه شد!")
        else:
            await update.message.reply_text(f"❌ این مبحث قبلاً وجود دارد.")
        context.user_data.pop('mode', None)
        return True

    elif mode == 'edit_user':
        edit_info = context.user_data.get('edit_user', {})
        target_uid = edit_info.get('uid')
        field = edit_info.get('field')
        label = edit_info.get('label')
        if target_uid and field:
            await db.update_user(target_uid, {field: text})
            await update.message.reply_text(f"✅ {label} به «{text}» تغییر کرد.")
        context.user_data.pop('mode', None)
        context.user_data.pop('edit_user', None)
        return True

    return False
