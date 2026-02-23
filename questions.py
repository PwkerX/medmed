"""بانک سوال — با دسته‌بندی پیشرفته"""
import os, logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import db

logger  = logging.getLogger(__name__)
ANSWERING  = 4
CREATING_Q = 6
ADMIN_ID   = int(os.getenv('ADMIN_ID', '0'))

DIFF_EMOJI = {'آسان 🟢': '🟢', 'متوسط 🟡': '🟡', 'سخت 🔴': '🔴'}


async def questions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data  = query.data
    parts = data.split(':')
    action = parts[1] if len(parts) > 1 else 'main'
    uid = update.effective_user.id

    if action == 'main':
        await _main_menu(query)

    # ── بانک فایل ادمین ──
    elif action == 'file_bank':
        await _fb_lessons(query, context)

    elif action == 'fb_lesson':
        idx = int(parts[2])
        lessons = context.user_data.get('_fb_lessons', [])
        if idx < len(lessons):
            context.user_data['fb_lesson'] = lessons[idx]
            await _fb_topics(query, context, lessons[idx])

    elif action == 'fb_topic':
        lesson = context.user_data.get('fb_lesson', '')
        topics = context.user_data.get('_fb_topics', [])
        topic  = None if parts[2] == 'all' else (topics[int(parts[2])] if int(parts[2]) < len(topics) else None)
        await _fb_files(query, context, lesson, topic)

    elif data.startswith('download_qbank:'):
        fid  = parts[1]
        item = await db.get_qbank_file(fid)
        if not item:
            await query.answer("فایل پیدا نشد!", show_alert=True); return
        await db.inc_qbank_download(fid, uid)
        caption = (f"📁 <b>بانک سوال</b>\n📚 {item.get('lesson','')} — {item.get('topic','')}\n"
                   f"📝 {item.get('description','')}\n⬇️ {item.get('downloads',0)} دانلود")
        try:
            await query.message.reply_document(item['file_id'], caption=caption, parse_mode='HTML')
        except:
            try:
                await query.message.reply_photo(item['file_id'], caption=caption, parse_mode='HTML')
            except:
                await query.answer("خطا در ارسال فایل!", show_alert=True)
        return

    # ── تمرین تستی ──
    elif action == 'practice':
        await _practice_menu(query)

    elif action == 'free':
        await _lesson_select(query, context, 'free')

    elif action == 'weak':
        context.user_data['quiz'] = {'mode': 'weak', 'answered': [], 'correct': 0}
        await _next_q(query, context, uid)

    elif action == 'hard':
        context.user_data['quiz'] = {'mode': 'hard', 'difficulty': 'سخت 🔴', 'answered': [], 'correct': 0}
        await _next_q(query, context, uid)

    elif action == 'exam':
        await _lesson_select(query, context, 'exam')

    elif action == 'sel_lesson':
        mode = parts[2]; idx = int(parts[3])
        lessons = context.user_data.get('_lessons', [])
        if idx < len(lessons):
            lesson = lessons[idx]
            context.user_data['sel_lesson'] = lesson
            context.user_data['quiz'] = {'mode': mode, 'lesson': lesson, 'answered': [], 'correct': 0, 'total': 20 if mode == 'exam' else 999}
            await _topic_select(query, context, lesson, mode)

    elif action == 'sel_topic':
        mode   = parts[2]
        topics = context.user_data.get('_topics', [])
        topic  = 'همه' if parts[3] == 'all' else (topics[int(parts[3])] if int(parts[3]) < len(topics) else 'همه')
        lesson = context.user_data.get('sel_lesson', '')
        context.user_data.setdefault('quiz', {}).update({
            'lesson': lesson, 'topic': topic, 'mode': mode,
            'answered': [], 'correct': 0, 'total': 20 if mode == 'exam' else 999
        })
        await _next_q(query, context, uid)

    elif action == 'next':
        await _next_q(query, context, uid)

    elif action == 'stats':
        await _quiz_stats(query, uid)

    # ── طراحی سوال ──
    elif action == 'create':
        await _create_start(query, context)

    elif action == 'cr_lesson':
        idx = int(parts[2])
        lessons = context.user_data.get('_lessons', [])
        if idx < len(lessons):
            lesson = lessons[idx]
            context.user_data['new_q']    = {'lesson': lesson}
            context.user_data['cr_lesson'] = lesson
            await _create_topic_select(query, context, lesson)

    elif action == 'cr_topic':
        topics = context.user_data.get('_topics', [])
        idx    = int(parts[2])
        topic  = topics[idx] if idx < len(topics) else ''
        lesson = context.user_data.get('cr_lesson', '')
        context.user_data.setdefault('new_q', {})['topic'] = topic
        context.user_data['mode']        = 'creating_question'
        context.user_data['create_step'] = 'question'
        await query.edit_message_text(
            f"✏️ <b>طراحی سوال</b>\n📚 {lesson} — {topic}\n\n"
            "━━━━━━━━━━━━━━━━\n"
            "📝 <b>گام ۱ از ۵ — متن سوال</b>\n\nسوال خود را بنویسید:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data='questions:main')]])
        )
        return CREATING_Q

    elif data.startswith('answer:'):
        await handle_question_answer(update, context)


# ─────────── منوها ───────────

async def _main_menu(query):
    keyboard = [
        [InlineKeyboardButton("📁 بانک سوال ادمین",  callback_data='questions:file_bank')],
        [InlineKeyboardButton("🧪 تمرین تستی",        callback_data='questions:practice')],
        [InlineKeyboardButton("✏️ طراحی سوال",        callback_data='questions:create')],
        [InlineKeyboardButton("📊 آمار تمرین من",     callback_data='questions:stats')],
    ]
    await query.edit_message_text(
        "🧪 <b>بانک سوال</b>\n\n"
        "━━━━━━━━━━━━━━━━\n"
        "📁 <b>بانک ادمین:</b> دانلود فایل PDF سوالات\n"
        "🧪 <b>تمرین تستی:</b> سوالات چهارگزینه‌ای\n"
        "✏️ <b>طراحی سوال:</b> سوال خودتان را بسازید\n"
        "📊 <b>آمار:</b> پیشرفت و نقاط ضعف",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _fb_lessons(query, context):
    lessons = await db.get_lessons()
    if not lessons:
        await query.edit_message_text(
            "📁 <b>بانک سوال ادمین</b>\n\n❌ هنوز هیچ فایلی آپلود نشده.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data='questions:main')]]))
        return
    context.user_data['_fb_lessons'] = lessons
    keyboard = []
    for i in range(0, len(lessons), 2):
        row = [InlineKeyboardButton(f"📚 {lessons[i]}", callback_data=f'questions:fb_lesson:{i}')]
        if i+1 < len(lessons):
            row.append(InlineKeyboardButton(f"📚 {lessons[i+1]}", callback_data=f'questions:fb_lesson:{i+1}'))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='questions:main')])
    await query.edit_message_text("📁 <b>بانک سوال ادمین</b>\n\nدرس را انتخاب کنید:",
                                   parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def _fb_topics(query, context, lesson):
    topics = await db.get_topics(lesson)
    context.user_data['_fb_topics'] = topics
    keyboard = [[InlineKeyboardButton(f"📌 {t}", callback_data=f'questions:fb_topic:{i}')] for i, t in enumerate(topics)]
    keyboard.append([InlineKeyboardButton("📂 همه مباحث", callback_data='questions:fb_topic:all')])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='questions:file_bank')])
    await query.edit_message_text(f"📁 <b>{lesson}</b>\n\nمبحث را انتخاب کنید:",
                                   parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def _fb_files(query, context, lesson, topic):
    files = await db.get_qbank_files(lesson=lesson, topic=topic)
    if not files:
        await query.edit_message_text(
            f"📁 <b>{lesson}{' — '+topic if topic else ''}</b>\n\n❌ فایلی برای این بخش آپلود نشده.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data='questions:file_bank')]]))
        return
    keyboard = []
    for f in files:
        fid   = str(f['_id'])
        label = f"📥 {f.get('topic','')} | {f.get('description','')[:25]} | ⬇️{f.get('downloads',0)}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f'download_qbank:{fid}')])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='questions:file_bank')])
    await query.edit_message_text(
        f"📁 <b>{lesson}{' — '+topic if topic else ''}</b>\n{len(files)} فایل موجود:",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def _practice_menu(query):
    keyboard = [
        [InlineKeyboardButton("📖 تمرین آزاد",                callback_data='questions:free')],
        [InlineKeyboardButton("⚡ نقاط ضعف من",               callback_data='questions:weak')],
        [InlineKeyboardButton("📝 شبیه‌سازی امتحان (۲۰ سوال)", callback_data='questions:exam')],
        [InlineKeyboardButton("🔴 سوالات سطح سخت",            callback_data='questions:hard')],
        [InlineKeyboardButton("🔙 بازگشت",                    callback_data='questions:main')],
    ]
    await query.edit_message_text(
        "🧪 <b>تمرین تستی</b>\n\n"
        "━━━━━━━━━━━━━━━━\n"
        "📖 <b>آزاد:</b> هر درس و مبحث دلخواه\n"
        "⚡ <b>نقاط ضعف:</b> سوالاتی که اشتباه زدید\n"
        "📝 <b>شبیه امتحان:</b> ۲۰ سوال پشت سر هم\n"
        "🔴 <b>سخت:</b> چالشی‌ترین سوالات",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def _lesson_select(query, context, mode):
    lessons = await db.get_lessons()
    if not lessons:
        await query.edit_message_text("❌ هنوز سوالی در بانک موجود نیست.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data='questions:practice')]]))
        return
    context.user_data['_lessons'] = lessons
    keyboard = []
    for i in range(0, len(lessons), 2):
        row = [InlineKeyboardButton(f"📚 {lessons[i]}", callback_data=f'questions:sel_lesson:{mode}:{i}')]
        if i+1 < len(lessons):
            row.append(InlineKeyboardButton(f"📚 {lessons[i+1]}", callback_data=f'questions:sel_lesson:{mode}:{i+1}'))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='questions:practice')])
    label = "شبیه‌سازی امتحان" if mode == 'exam' else "تمرین آزاد"
    await query.edit_message_text(f"📚 <b>{label}</b>\n\nدرس را انتخاب کنید:",
                                   parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def _topic_select(query, context, lesson, mode):
    topics = await db.get_topics(lesson)
    context.user_data['_topics'] = topics
    keyboard = [[InlineKeyboardButton(f"📌 {t}", callback_data=f'questions:sel_topic:{mode}:{i}')] for i, t in enumerate(topics)]
    keyboard.append([InlineKeyboardButton("📂 همه مباحث", callback_data=f'questions:sel_topic:{mode}:all')])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f'questions:{"exam" if mode=="exam" else "free"}')])
    await query.edit_message_text(f"📚 <b>{lesson}</b>\n\nمبحث را انتخاب کنید:",
                                   parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def _next_q(query, context, uid):
    quiz   = context.user_data.get('quiz', {})
    mode   = quiz.get('mode', 'free')
    lesson = quiz.get('lesson')
    topic  = quiz.get('topic')
    diff   = quiz.get('difficulty')
    done   = quiz.get('answered', [])
    total  = quiz.get('total', 999)

    if len(done) >= total:
        correct = quiz.get('correct', 0)
        pct     = round(correct / len(done) * 100) if done else 0
        await query.edit_message_text(
            f"🏁 <b>پایان آزمون</b>\n\n"
            f"✅ صحیح: {correct} از {len(done)}\n"
            f"📊 درصد: {pct}%\n"
            f"{'🏆 عالی!' if pct>=80 else '👍 خوب!' if pct>=60 else '📖 بیشتر مطالعه کنید'}",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 دوباره", callback_data='questions:practice'),
                                                InlineKeyboardButton("🏠 منو", callback_data='questions:main')]]))
        return

    if mode == 'weak':
        qs = await db.get_weak_questions(uid, limit=1)
    else:
        qs = await db.get_questions(lesson=lesson, topic=topic, difficulty=diff, limit=1, exclude=done)

    if not qs:
        await query.edit_message_text(
            "❌ سوال دیگری یافت نشد!\n\nتمام سوالات موجود را پاسخ دادید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data='questions:practice')]]))
        return

    q   = qs[0]
    qid = str(q['_id'])
    context.user_data.setdefault('quiz', {}).setdefault('answered', []).append(qid)

    diff_icon = DIFF_EMOJI.get(q.get('difficulty',''), '⚪')
    num       = len(done) + 1
    total_str = f"/{total}" if total < 999 else ""

    keyboard = []
    for i, opt in enumerate(q['options']):
        keyboard.append([InlineKeyboardButton(f"{['🅐','🅑','🅒','🅓'][i]} {opt}",
                                               callback_data=f'answer:{qid}:{i}')])
    await query.edit_message_text(
        f"📝 <b>سوال {num}{total_str}</b>  {diff_icon}\n"
        f"📚 {q.get('lesson','')} — {q.get('topic','')}\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"{q['question']}",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_question_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid   = update.effective_user.id
    parts = query.data.split(':')
    qid   = parts[1]
    sel   = int(parts[2])

    q = await db.get_questions(limit=1)
    from bson import ObjectId
    from database import db as database
    q_doc = await database.questions.find_one({'_id': ObjectId(qid)})
    if not q_doc:
        await query.edit_message_text("❌ سوال پیدا نشد!")
        return

    correct_idx = q_doc.get('correct_answer', 0)
    is_correct  = (sel == correct_idx)
    await db.save_answer(uid, qid, sel, is_correct)

    quiz = context.user_data.setdefault('quiz', {})
    if is_correct:
        quiz['correct'] = quiz.get('correct', 0) + 1

    opts      = q_doc.get('options', [])
    expl      = q_doc.get('explanation', '')
    result_icon = "✅" if is_correct else "❌"

    options_text = ""
    for i, opt in enumerate(opts):
        if i == correct_idx:
            marker = "✅"
        elif i == sel and not is_correct:
            marker = "❌"
        else:
            marker = "⚫"
        options_text += f"{marker} {opt}\n"

    text = (
        f"{result_icon} <b>{'صحیح!' if is_correct else 'اشتباه!'}</b>\n\n"
        f"{q_doc['question']}\n\n"
        f"{options_text}"
    )
    if expl:
        text += f"\n💡 <b>توضیح:</b> {expl}"

    keyboard = [[InlineKeyboardButton("➡️ سوال بعدی", callback_data='questions:next'),
                 InlineKeyboardButton("🏠 منو", callback_data='questions:main')]]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def _quiz_stats(query, uid):
    stats = await db.user_stats(uid)
    total   = stats['total_answers']
    correct = stats['correct_answers']
    pct     = stats['percentage']
    weak    = stats['weak_topics'][:5]

    bar = '█' * int(pct/10) + '░' * (10 - int(pct/10))

    text = (
        f"📊 <b>آمار تمرین من</b>\n━━━━━━━━━━━━━━━━\n\n"
        f"🧪 کل سوالات: <b>{total}</b>\n"
        f"✅ صحیح: <b>{correct}</b>  ❌ اشتباه: <b>{total-correct}</b>\n\n"
        f"📈 درصد صحیح:\n  {bar} <b>{pct}%</b>\n"
    )
    if weak:
        text += f"\n⚡ <b>نقاط ضعف:</b>\n" + "".join(f"  • {w}\n" for w in weak)
    else:
        text += "\n🎉 هیچ نقطه ضعف ثبت‌شده‌ای ندارید!"

    await query.edit_message_text(text, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data='questions:main')]]))


async def _create_start(query, context):
    lessons = await db.get_lessons()
    if not lessons:
        await query.edit_message_text(
            "❌ هنوز درسی تعریف نشده. برای طراحی سوال، ابتدا از ادمین بخواهید درس‌ها را تعریف کند.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data='questions:main')]]))
        return
    context.user_data['_lessons'] = lessons
    keyboard = []
    for i in range(0, len(lessons), 2):
        row = [InlineKeyboardButton(f"📚 {lessons[i]}", callback_data=f'questions:cr_lesson:{i}')]
        if i+1 < len(lessons):
            row.append(InlineKeyboardButton(f"📚 {lessons[i+1]}", callback_data=f'questions:cr_lesson:{i+1}'))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='questions:main')])
    await query.edit_message_text(
        "✏️ <b>طراحی سوال جدید</b>\n\nابتدا درس را انتخاب کنید:",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def _create_topic_select(query, context, lesson):
    topics = await db.get_topics(lesson)
    context.user_data['_topics'] = topics
    keyboard = [[InlineKeyboardButton(f"📌 {t}", callback_data=f'questions:cr_topic:{i}')] for i, t in enumerate(topics)]
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='questions:create')])
    await query.edit_message_text(f"✏️ <b>{lesson}</b>\n\nمبحث را انتخاب کنید:",
                                   parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_create_question_steps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    step = context.user_data.get('create_step', '')
    q    = context.user_data.setdefault('new_q', {})

    if text == '❌ لغو' or text == '/start':
        context.user_data['mode'] = ''
        context.user_data['create_step'] = ''
        await update.message.reply_text("❌ طراحی سوال لغو شد.")
        return ConversationHandler.END

    steps_total = 5

    if step == 'question':
        if len(text) < 10:
            await update.message.reply_text("⚠️ متن سوال باید حداقل ۱۰ کاراکتر باشد.")
            return CREATING_Q
        q['question'] = text
        context.user_data['create_step'] = 'opt1'
        await update.message.reply_text(
            f"✅ سوال ثبت شد.\n\n📝 <b>گام ۲ از {steps_total} — گزینه الف</b>\n\nگزینه اول را بنویسید:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data='questions:main')]]))

    elif step in ('opt1', 'opt2', 'opt3', 'opt4'):
        opts = q.setdefault('options', [])
        opts.append(text)
        next_steps = {'opt1': ('opt2', 'ب', 3), 'opt2': ('opt3', 'ج', 3), 'opt3': ('opt4', 'د', 3)}
        if step == 'opt4':
            context.user_data['create_step'] = 'correct'
            opt_list = "\n".join(f"  {['🅐','🅑','🅒','🅓'][i]} {o}" for i,o in enumerate(opts))
            keyboard = [[InlineKeyboardButton(f"{['🅐','🅑','🅒','🅓'][i]} گزینه {i+1}", callback_data=f'questions:cr_topic:noop')] for i in range(4)]
            await update.message.reply_text(
                f"✅ گزینه‌ها ثبت شدند:\n{opt_list}\n\n"
                f"📝 <b>گام ۴ از {steps_total} — گزینه صحیح</b>\n\nشماره گزینه صحیح را بنویسید (1-4):",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data='questions:main')]]));
        else:
            ns, label, gam = next_steps[step]
            context.user_data['create_step'] = ns
            await update.message.reply_text(
                f"📝 <b>گام ۳ از {steps_total} — گزینه {label}</b>\n\nگزینه بعدی را بنویسید:",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data='questions:main')]]))

    elif step == 'correct':
        if text not in ('1','2','3','4'):
            await update.message.reply_text("⚠️ عدد ۱ تا ۴ وارد کنید.")
            return CREATING_Q
        q['correct'] = int(text) - 1
        context.user_data['create_step'] = 'difficulty'
        keyboard = [
            [InlineKeyboardButton("🟢 آسان",   callback_data='qd:easy')],
            [InlineKeyboardButton("🟡 متوسط",  callback_data='qd:medium')],
            [InlineKeyboardButton("🔴 سخت",    callback_data='qd:hard')],
        ]
        await update.message.reply_text(
            f"📝 <b>گام ۴ از {steps_total} — سطح سختی</b>\n\nسطح سختی سوال را انتخاب کنید:",
            parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

    elif step == 'explanation':
        q['explanation'] = '' if text == '-' else text
        await _save_question(update, context)

    return CREATING_Q


async def handle_difficulty_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    diff_map = {'easy': 'آسان 🟢', 'medium': 'متوسط 🟡', 'hard': 'سخت 🔴'}
    diff = diff_map.get(query.data.split(':')[1], 'متوسط 🟡')
    context.user_data.setdefault('new_q', {})['difficulty'] = diff
    context.user_data['create_step'] = 'explanation'
    await query.edit_message_text(
        "📝 <b>گام ۵ از ۵ — توضیح</b>\n\n"
        "توضیح پاسخ صحیح را بنویسید (یا - بزنید برای بدون توضیح):",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data='questions:main')]]))
    return CREATING_Q


async def _save_question(update, context):
    uid  = update.effective_user.id
    q    = context.user_data.get('new_q', {})
    lesson     = q.get('lesson', '')
    topic      = q.get('topic', '')
    question   = q.get('question', '')
    options    = q.get('options', [])
    correct    = q.get('correct', 0)
    difficulty = q.get('difficulty', 'متوسط 🟡')
    explanation = q.get('explanation', '')

    admin_id = int(os.getenv('ADMIN_ID', '0'))
    auto     = (uid == admin_id)

    await db.add_question(lesson, topic, difficulty, question, options, correct, explanation, uid, auto_approve=auto)

    for k in ['new_q', 'create_step', 'mode', 'cr_lesson']:
        context.user_data.pop(k, None)

    if auto:
        msg = "✅ <b>سوال با موفقیت اضافه شد!</b>"
    else:
        msg = "✅ <b>سوال ارسال شد و در انتظار تأیید ادمین است.</b>"

    await update.message.reply_text(msg, parse_mode='HTML')
    return ConversationHandler.END
