import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import db

logger = logging.getLogger(__name__)
ANSWERING = 4
CREATING_Q = 6
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))


async def questions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    parts = data.split(':')
    action = parts[1] if len(parts) > 1 else 'main'

    if action == 'main':
        await _quiz_main_menu(query)

    elif action == 'file_bank':
        await _show_file_bank_lessons(query, context)

    elif action == 'fb_lesson':
        idx = int(parts[2])
        lessons = context.user_data.get('_lessons', [])
        if idx < len(lessons):
            lesson = lessons[idx]
            context.user_data['fb_lesson'] = lesson
            await _show_file_bank_topics(query, context, lesson)

    elif action == 'fb_topic':
        lesson = context.user_data.get('fb_lesson', '')
        topics = context.user_data.get('_topics', [])
        topic = None if parts[2] == 'all' else (topics[int(parts[2])] if int(parts[2]) < len(topics) else None)
        await _show_file_bank_files(query, lesson, topic)

    elif data.startswith('download_qbank:'):
        qid = parts[1]
        item = await db.get_qbank_file(qid)
        if not item:
            await query.answer("فایل پیدا نشد!", show_alert=True)
            return
        await db.inc_qbank_download(qid, update.effective_user.id)
        caption = (f"بانک سوال\n{item.get('lesson','')} - {item.get('topic','')}\n"
                   f"{item.get('description','')}\n{item.get('downloads',0)} دانلود")
        try:
            await context.bot.send_document(update.effective_chat.id, item['file_id'],
                                             caption=caption, parse_mode='HTML')
        except:
            try:
                await context.bot.send_photo(update.effective_chat.id, item['file_id'],
                                              caption=caption, parse_mode='HTML')
            except:
                await query.answer("خطا در ارسال!", show_alert=True)
        return

    elif action == 'practice':
        await _practice_menu(query)

    elif action == 'free':
        await _show_lesson_select(query, context, 'free')

    elif action == 'weak':
        context.user_data['quiz'] = {'mode': 'weak', 'answered': [], 'correct': 0}
        await _next_question(query, context, update.effective_user.id)

    elif action == 'hard':
        context.user_data['quiz'] = {'mode': 'hard', 'difficulty': 'سخت 🔴', 'answered': [], 'correct': 0}
        await _next_question(query, context, update.effective_user.id)

    elif action == 'exam':
        await _show_lesson_select(query, context, 'exam')

    elif action == 'sel_lesson':
        mode = parts[2]
        idx = int(parts[3])
        lessons = context.user_data.get('_lessons', [])
        if idx < len(lessons):
            lesson = lessons[idx]
            context.user_data['quiz'] = {
                'mode': mode, 'lesson': lesson,
                'answered': [], 'correct': 0,
                'total': 20 if mode == 'exam' else 999
            }
            context.user_data['sel_lesson'] = lesson
            await _show_topic_select(query, context, lesson, mode)

    elif action == 'sel_topic':
        mode = parts[2]
        topics = context.user_data.get('_topics', [])
        topic = 'همه' if parts[3] == 'all' else (topics[int(parts[3])] if int(parts[3]) < len(topics) else 'همه')
        lesson = context.user_data.get('sel_lesson', '')
        context.user_data.setdefault('quiz', {}).update({
            'lesson': lesson, 'topic': topic, 'mode': mode,
            'answered': [], 'correct': 0,
            'total': 20 if mode == 'exam' else 999
        })
        await _next_question(query, context, update.effective_user.id)

    elif action == 'next':
        await _next_question(query, context, update.effective_user.id)

    elif action == 'stats':
        await _quiz_stats(query, update.effective_user.id)

    elif action == 'create':
        await _create_question_start(query, context)

    elif action == 'cr_lesson':
        idx = int(parts[2])
        lessons = context.user_data.get('_lessons', [])
        if idx < len(lessons):
            lesson = lessons[idx]
            context.user_data['new_q'] = {'lesson': lesson}
            context.user_data['cr_lesson'] = lesson
            await _create_q_select_topic(query, context, lesson)

    elif action == 'cr_topic':
        topics = context.user_data.get('_topics', [])
        idx = int(parts[2])
        topic = topics[idx] if idx < len(topics) else ''
        lesson = context.user_data.get('cr_lesson', '')
        context.user_data.setdefault('new_q', {})['topic'] = topic
        context.user_data['mode'] = 'creating_question'
        context.user_data['create_step'] = 'question'
        await query.edit_message_text(
            f"✏️ <b>طراحی سوال</b>\n📚 {lesson} — {topic}\n\n📝 <b>گام ۱:</b> متن سوال را بنویسید:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data='questions:main')]])
        )
        return CREATING_Q

    elif data.startswith('answer:'):
        await handle_question_answer(update, context)


async def _quiz_main_menu(query):
    keyboard = [
        [InlineKeyboardButton("📁 بانک سوال ادمین (دانلود فایل)", callback_data='questions:file_bank')],
        [InlineKeyboardButton("🧪 تمرین تستی", callback_data='questions:practice')],
        [InlineKeyboardButton("✏️ طراحی سوال", callback_data='questions:create')],
        [InlineKeyboardButton("📊 آمار تمرین من", callback_data='questions:stats')]
    ]
    await query.edit_message_text(
        "🧪 <b>بانک سوال</b>\n\n📁 <b>بانک ادمین:</b> فایل PDF/عکس\n"
        "🧪 <b>تمرین تستی:</b> سوالات چهارگزینه‌ای\n"
        "✏️ <b>طراحی سوال:</b> سوال بسازید",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _show_file_bank_lessons(query, context):
    lessons = await db.get_lessons()
    context.user_data['_lessons'] = lessons
    keyboard = []
    for i in range(0, len(lessons), 2):
        row = [InlineKeyboardButton(lessons[i], callback_data=f'questions:fb_lesson:{i}')]
        if i + 1 < len(lessons):
            row.append(InlineKeyboardButton(lessons[i+1], callback_data=f'questions:fb_lesson:{i+1}'))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='questions:main')])
    await query.edit_message_text("📁 <b>بانک سوال ادمین</b>\n\nدرس را انتخاب کنید:",
                                   parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def _show_file_bank_topics(query, context, lesson):
    topics = await db.get_topics(lesson)
    context.user_data['_topics'] = topics
    keyboard = [[InlineKeyboardButton(t, callback_data=f'questions:fb_topic:{i}')] for i, t in enumerate(topics)]
    keyboard.append([InlineKeyboardButton("📂 همه مباحث", callback_data='questions:fb_topic:all')])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='questions:file_bank')])
    await query.edit_message_text(f"📁 <b>{lesson}</b>\n\nمبحث را انتخاب کنید:",
                                   parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def _show_file_bank_files(query, lesson, topic):
    files = await db.get_qbank_files(lesson=lesson, topic=topic)
    if not files:
        await query.edit_message_text(
            f"📁 {lesson}{' — ' + topic if topic else ''}\n\n❌ فایل بانک سوالی آپلود نشده.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data='questions:file_bank')]]))
        return
    keyboard = []
    for f in files:
        fid = str(f['_id'])
        label = f"📥 {f.get('topic','')} | {f.get('description','')[:20]} | ⬇️{f.get('downloads',0)}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f'download_qbank:{fid}')])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='questions:file_bank')])
    await query.edit_message_text(
        f"📁 <b>{lesson}{' — ' + topic if topic else ''}</b>\n{len(files)} فایل:",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def _practice_menu(query):
    keyboard = [
        [InlineKeyboardButton("📖 تمرین آزاد", callback_data='questions:free')],
        [InlineKeyboardButton("⚡ تمرین نقاط ضعف", callback_data='questions:weak')],
        [InlineKeyboardButton("📝 شبیه‌سازی امتحان (۲۰ سوال)", callback_data='questions:exam')],
        [InlineKeyboardButton("🔴 سوالات سخت", callback_data='questions:hard')],
        [InlineKeyboardButton("🔙 بازگشت", callback_data='questions:main')]
    ]
    await query.edit_message_text("🧪 <b>تمرین تستی</b>\n\nحالت تمرین را انتخاب کنید:",
                                   parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def _show_lesson_select(query, context, mode):
    lessons = await db.get_lessons()
    context.user_data['_lessons'] = lessons
    keyboard = []
    for i in range(0, len(lessons), 2):
        row = [InlineKeyboardButton(lessons[i], callback_data=f'questions:sel_lesson:{mode}:{i}')]
        if i + 1 < len(lessons):
            row.append(InlineKeyboardButton(lessons[i+1], callback_data=f'questions:sel_lesson:{mode}:{i+1}'))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='questions:practice')])
    await query.edit_message_text("🧪 درس را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))


async def _show_topic_select(query, context, lesson, mode):
    topics = await db.get_topics(lesson)
    context.user_data['_topics'] = topics
    keyboard = [[InlineKeyboardButton(t, callback_data=f'questions:sel_topic:{mode}:{i}')] for i, t in enumerate(topics)]
    keyboard.append([InlineKeyboardButton("📂 همه مباحث", callback_data=f'questions:sel_topic:{mode}:all')])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='questions:practice')])
    await query.edit_message_text(f"🧪 <b>{lesson}</b>\n\nمبحث را انتخاب کنید:",
                                   parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def _next_question(query, context, uid):
    quiz = context.user_data.get('quiz', {})
    mode = quiz.get('mode', 'free')
    answered = quiz.get('answered', [])
    total_limit = quiz.get('total', 999)

    if len(answered) >= total_limit:
        await _show_results(query, quiz)
        return

    if mode == 'weak':
        questions = await db.get_weak_questions(uid, limit=1)
    else:
        questions = await db.get_questions(
            lesson=quiz.get('lesson'),
            topic=quiz.get('topic') if quiz.get('topic') != 'همه' else None,
            difficulty=quiz.get('difficulty'),
            limit=1, exclude=answered
        )

    if not questions:
        if not answered:
            await query.edit_message_text(
                "❌ سوالی برای این بخش ثبت نشده.\n\nمی‌توانید با ✏️ طراحی سوال، سوال اضافه کنید.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✏️ طراحی سوال", callback_data='questions:create')],
                    [InlineKeyboardButton("🔙 بازگشت", callback_data='questions:practice')]
                ]))
        else:
            await _show_results(query, quiz)
        return

    q = questions[0]
    qid = str(q['_id'])
    context.user_data['current_q'] = {
        'id': qid, 'correct': q['correct_answer'],
        'explanation': q.get('explanation', ''), 'topic': q.get('topic', '')
    }
    opts = q.get('options', [])
    diff_map = {'آسان 🟢': '🟢', 'متوسط 🟡': '🟡', 'سخت 🔴': '🔴'}
    diff_icon = diff_map.get(q.get('difficulty', ''), '⚪')
    progress = f"{len(answered)+1}" + (f"/{total_limit}" if total_limit < 999 else "")
    source = "👨‍⚕️ ادمین" if q.get('creator_id') == ADMIN_ID else "👤 دانشجو"

    keyboard = []
    for i, opt in enumerate(opts):
        keyboard.append([InlineKeyboardButton(f"{'ABCD'[i]}) {opt}", callback_data=f'answer:{qid}:{i+1}')])
    keyboard.append([InlineKeyboardButton("⏭ رد کردن", callback_data=f'answer:{qid}:0')])

    text = (f"🧪 <b>{q.get('lesson','')} — {q.get('topic','')}</b>\n"
            f"{diff_icon} | سوال {progress} | {source}\n━━━━━━━━━━━━━━━━━\n\n❓ <b>{q['question']}</b>")
    try:
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"edit error: {e}")


async def _show_results(query, quiz):
    answered = len(quiz.get('answered', []))
    correct = quiz.get('correct', 0)
    pct = round(correct / answered * 100, 1) if answered > 0 else 0
    if pct >= 80: emoji = "🏆 عالی!"
    elif pct >= 60: emoji = "💪 خوب!"
    elif pct >= 40: emoji = "📖 بیشتر تمرین کن"
    else: emoji = "📚 مطالعه بیشتر لازم است"
    keyboard = [
        [InlineKeyboardButton("🔄 شروع مجدد", callback_data='questions:practice')],
        [InlineKeyboardButton("📊 آمار کامل", callback_data='questions:stats')],
        [InlineKeyboardButton("🔙 بازگشت", callback_data='questions:main')]
    ]
    await query.edit_message_text(
        f"🎯 <b>پایان تمرین!</b>\n\n✅ صحیح: {correct} از {answered}\n📊 درصد: {pct}%\n\n{emoji}",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_question_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split(':')
    if len(parts) < 3:
        return ANSWERING
    qid, sel_str = parts[1], parts[2]
    uid = update.effective_user.id
    current = context.user_data.get('current_q', {})
    correct_ans = current.get('correct', 1)
    explanation = current.get('explanation', '')
    quiz = context.user_data.get('quiz', {})
    answered = quiz.get('answered', [])
    answered.append(qid)
    quiz['answered'] = answered
    if sel_str == '0':
        await db.save_answer(uid, qid, 0, False)
        result = "⏭ <b>رد شد</b>"
    else:
        sel = int(sel_str)
        is_correct = (sel == correct_ans)
        await db.save_answer(uid, qid, sel, is_correct)
        if is_correct:
            quiz['correct'] = quiz.get('correct', 0) + 1
            result = "✅ <b>صحیح!</b> 🎉"
        else:
            result = f"❌ <b>اشتباه!</b>\nجواب صحیح: گزینه <b>{correct_ans}</b>"
    context.user_data['quiz'] = quiz
    if explanation:
        result += f"\n\n💡 <b>توضیح:</b>\n{explanation}"
    keyboard = [
        [InlineKeyboardButton("➡️ سوال بعدی", callback_data='questions:next')],
        [InlineKeyboardButton("🏠 منوی اصلی", callback_data='questions:main')]
    ]
    try:
        await query.edit_message_text(result, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"answer error: {e}")
    return ANSWERING


async def _create_question_start(query, context):
    lessons = await db.get_lessons()
    context.user_data['_lessons'] = lessons
    keyboard = []
    for i in range(0, len(lessons), 2):
        row = [InlineKeyboardButton(lessons[i], callback_data=f'questions:cr_lesson:{i}')]
        if i + 1 < len(lessons):
            row.append(InlineKeyboardButton(lessons[i+1], callback_data=f'questions:cr_lesson:{i+1}'))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='questions:main')])
    await query.edit_message_text(
        "✏️ <b>طراحی سوال جدید</b>\n\nبعد از تأیید ادمین به بانک اضافه می‌شود.\n\nدرس را انتخاب کنید:",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def _create_q_select_topic(query, context, lesson):
    topics = await db.get_topics(lesson)
    context.user_data['_topics'] = topics
    keyboard = [[InlineKeyboardButton(t, callback_data=f'questions:cr_topic:{i}')] for i, t in enumerate(topics)]
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='questions:create')])
    await query.edit_message_text(f"✏️ <b>{lesson}</b>\n\nمبحث را انتخاب کنید:",
                                   parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_create_question_steps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    step = context.user_data.get('create_step', '')
    new_q = context.user_data.get('new_q', {})

    if step == 'question':
        new_q['question'] = text
        context.user_data['create_step'] = 'options'
        context.user_data['new_q'] = new_q
        await update.message.reply_text(
            "📝 <b>گام ۲:</b> ۴ گزینه را بنویسید، هر گزینه در یک خط:",
            parse_mode='HTML')
        return CREATING_Q
    elif step == 'options':
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        if len(lines) != 4:
            await update.message.reply_text("❌ دقیقاً ۴ گزینه در ۴ خط بنویسید:")
            return CREATING_Q
        new_q['options'] = lines
        context.user_data['create_step'] = 'correct'
        context.user_data['new_q'] = new_q
        opts_text = '\n'.join(f"{'ABCD'[i]}) {o}" for i, o in enumerate(lines))
        await update.message.reply_text(
            f"✅ گزینه‌ها:\n{opts_text}\n\n📝 <b>گام ۳:</b> شماره گزینه صحیح (1 تا 4):",
            parse_mode='HTML')
        return CREATING_Q
    elif step == 'correct':
        try:
            correct = int(text)
            if correct < 1 or correct > 4:
                raise ValueError()
        except:
            await update.message.reply_text("❌ عدد 1 تا 4 وارد کنید:")
            return CREATING_Q
        new_q['correct'] = correct
        context.user_data['create_step'] = 'difficulty'
        context.user_data['new_q'] = new_q
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🟢 آسان", callback_data='qd:آسان 🟢'),
            InlineKeyboardButton("🟡 متوسط", callback_data='qd:متوسط 🟡'),
            InlineKeyboardButton("🔴 سخت", callback_data='qd:سخت 🔴')
        ]])
        await update.message.reply_text("📝 <b>گام ۴:</b> سطح سختی:", parse_mode='HTML', reply_markup=keyboard)
        return CREATING_Q
    elif step == 'explanation':
        new_q['explanation'] = text if text != '-' else ''
        context.user_data['new_q'] = new_q
        await _finalize_question(update, context)
        return ConversationHandler.END
    return CREATING_Q


async def handle_difficulty_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not query.data.startswith('qd:'):
        return CREATING_Q
    difficulty = query.data[3:]
    new_q = context.user_data.get('new_q', {})
    new_q['difficulty'] = difficulty
    context.user_data['new_q'] = new_q
    context.user_data['create_step'] = 'explanation'
    await query.edit_message_text(
        "📝 <b>گام ۵ (آخر):</b> توضیح جواب را بنویسید\nاگر ندارید <code>-</code> بنویسید:",
        parse_mode='HTML')
    return CREATING_Q


async def _finalize_question(update, context):
    uid = update.effective_user.id
    new_q = context.user_data.get('new_q', {})
    auto_approve = (uid == ADMIN_ID)
    await db.add_question(
        lesson=new_q.get('lesson', ''), topic=new_q.get('topic', ''),
        difficulty=new_q.get('difficulty', 'متوسط 🟡'),
        question=new_q.get('question', ''), options=new_q.get('options', []),
        correct=new_q.get('correct', 1), explanation=new_q.get('explanation', ''),
        creator=uid, auto_approve=auto_approve
    )
    if auto_approve:
        await update.message.reply_text(
            f"✅ <b>سوال اضافه شد!</b>\n📚 {new_q.get('lesson','')} — {new_q.get('topic','')}",
            parse_mode='HTML')
    else:
        await update.message.reply_text(
            f"✅ <b>سوال ثبت شد!</b>\n⏳ بعد از تأیید ادمین اضافه می‌شود.\n"
            f"📚 {new_q.get('lesson','')} — {new_q.get('topic','')}",
            parse_mode='HTML')
        try:
            await context.bot.send_message(ADMIN_ID,
                f"⏳ <b>سوال جدید:</b>\n📚 {new_q.get('lesson','')} — {new_q.get('topic','')}\n"
                f"❓ {new_q.get('question','')[:80]}", parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⏳ بررسی سوالات", callback_data='admin:pending_q')
                ]]))
        except:
            pass
    for k in ['new_q', 'create_step', 'mode', 'cr_lesson']:
        context.user_data.pop(k, None)


async def _quiz_stats(query, uid):
    stats = await db.user_stats(uid)
    total = stats['total_answers']
    correct = stats['correct_answers']
    pct = stats['percentage']
    bar_len = 15
    filled = int(correct / total * bar_len) if total > 0 else 0
    bar = '🟩' * filled + '🟥' * (bar_len - filled) if total > 0 else '⬜' * bar_len
    weak = stats['weak_topics']
    weak_text = '\n'.join(f"  • {t}" for t in weak[:5]) if weak else "  هیچ نقطه ضعفی ندارید! 🎉"
    keyboard = [
        [InlineKeyboardButton("⚡ تمرین نقاط ضعف", callback_data='questions:weak')],
        [InlineKeyboardButton("🔙 بازگشت", callback_data='questions:main')]
    ]
    await query.edit_message_text(
        f"📊 <b>آمار بانک سوال</b>\n\n{bar}\n\n"
        f"✅ صحیح: <b>{correct}</b>\n❌ اشتباه: <b>{total-correct}</b>\n"
        f"📈 درصد: <b>{pct}%</b>\n━━━━━━━━━━━━━\n⚡ <b>نقاط ضعف:</b>\n{weak_text}",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
