import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import db
from utils import LESSONS, TOPICS

logger = logging.getLogger(__name__)
ANSWERING = 4


async def questions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    parts = data.split(':')
    action = parts[1] if len(parts) > 1 else 'main'

    if action == 'main':
        await _quiz_menu(query)
    elif action == 'free':
        await _show_lesson_select(query, 'free')
    elif action == 'weak':
        context.user_data['quiz'] = {'mode': 'weak', 'answered': [], 'correct': 0}
        await _next_question(query, context, update.effective_user.id)
    elif action == 'hard':
        context.user_data['quiz'] = {'mode': 'hard', 'difficulty': 'سخت 🔴', 'answered': [], 'correct': 0}
        await _next_question(query, context, update.effective_user.id)
    elif action == 'exam':
        await _show_lesson_select(query, 'exam')
    elif action == 'select_lesson':
        mode = parts[2] if len(parts) > 2 else 'free'
        lesson = ':'.join(parts[3:]) if len(parts) > 3 else ''
        if lesson:
            context.user_data['quiz'] = {'mode': mode, 'lesson': lesson, 'answered': [], 'correct': 0,
                                          'total': 20 if mode == 'exam' else 999}
            await _show_topic_select(query, lesson, mode)
        else:
            await _show_lesson_select(query, mode)
    elif action == 'select_topic':
        mode = parts[2]
        lesson = parts[3]
        topic = ':'.join(parts[4:])
        context.user_data.setdefault('quiz', {})
        context.user_data['quiz'].update({'lesson': lesson, 'topic': topic, 'mode': mode,
                                           'answered': [], 'correct': 0, 'total': 20 if mode == 'exam' else 999})
        await _next_question(query, context, update.effective_user.id)
    elif action == 'next':
        await _next_question(query, context, update.effective_user.id)
    elif action == 'stats':
        await _quiz_stats(query, update.effective_user.id)
    elif data.startswith('answer:'):
        await handle_question_answer(update, context)


async def _quiz_menu(query):
    keyboard = [
        [InlineKeyboardButton("📖 تمرین آزاد", callback_data='questions:free')],
        [InlineKeyboardButton("⚡ تمرین نقاط ضعف", callback_data='questions:weak')],
        [InlineKeyboardButton("📝 شبیه‌سازی امتحان (۲۰ سوال)", callback_data='questions:exam')],
        [InlineKeyboardButton("🔴 سوالات سخت", callback_data='questions:hard')],
        [InlineKeyboardButton("📊 آمار تمرین من", callback_data='questions:stats')]
    ]
    await query.edit_message_text(
        "🧪 <b>بانک سوال</b>\n\nحالت تمرین را انتخاب کنید:",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _show_lesson_select(query, mode):
    keyboard = []
    for i in range(0, len(LESSONS), 2):
        row = [InlineKeyboardButton(LESSONS[i], callback_data=f'questions:select_lesson:{mode}:{LESSONS[i]}'[:64])]
        if i + 1 < len(LESSONS):
            row.append(InlineKeyboardButton(LESSONS[i+1], callback_data=f'questions:select_lesson:{mode}:{LESSONS[i+1]}'[:64]))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='questions:main')])
    await query.edit_message_text(
        "🧪 درس را انتخاب کنید:", parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _show_topic_select(query, lesson, mode):
    topics = TOPICS.get(lesson, ['عمومی'])
    keyboard = [[InlineKeyboardButton(t, callback_data=f'questions:select_topic:{mode}:{lesson}:{t}'[:64])] for t in topics]
    keyboard.append([InlineKeyboardButton("📂 همه مباحث", callback_data=f'questions:select_topic:{mode}:{lesson}:همه'[:64])])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f'questions:free')])
    await query.edit_message_text(
        f"🧪 <b>{lesson}</b>\n\nمبحث را انتخاب کنید:", parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
    )


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
            limit=1,
            exclude=answered
        )

    if not questions:
        await _show_results(query, quiz)
        return

    q = questions[0]
    qid = str(q['_id'])
    context.user_data['current_q'] = {
        'id': qid,
        'correct': q['correct_answer'],
        'explanation': q.get('explanation', ''),
        'topic': q.get('topic', '')
    }

    opts = q.get('options', [])
    diff_map = {'آسان 🟢': '🟢', 'متوسط 🟡': '🟡', 'سخت 🔴': '🔴'}
    diff_icon = diff_map.get(q.get('difficulty', ''), '⚪')

    progress = f"{len(answered)+1}"
    if total_limit < 999:
        progress += f"/{total_limit}"

    keyboard = []
    for i, opt in enumerate(opts):
        keyboard.append([InlineKeyboardButton(
            f"{'ABCD'[i]}) {opt}", callback_data=f'answer:{qid}:{i+1}'
        )])
    keyboard.append([InlineKeyboardButton("⏭ رد کردن", callback_data=f'answer:{qid}:0')])

    text = (
        f"🧪 <b>{q.get('lesson','')} — {q.get('topic','')}</b>\n"
        f"{diff_icon} {q.get('difficulty','')} | سوال {progress}\n"
        f"━━━━━━━━━━━━━━━━━\n\n"
        f"❓ <b>{q['question']}</b>"
    )
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
        [InlineKeyboardButton("🔄 شروع مجدد", callback_data='questions:main')],
        [InlineKeyboardButton("📊 آمار کامل", callback_data='questions:stats')]
    ]
    await query.edit_message_text(
        f"🎯 <b>پایان تمرین!</b>\n\n"
        f"✅ صحیح: {correct} از {answered}\n"
        f"📊 درصد: {pct}%\n\n{emoji}",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
    )


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
        [InlineKeyboardButton("🏠 منوی بانک سوال", callback_data='questions:main')]
    ]
    try:
        await query.edit_message_text(result, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"answer edit error: {e}")
    return ANSWERING


async def _quiz_stats(query, uid):
    stats = await db.user_stats(uid)
    total = stats['total_answers']
    correct = stats['correct_answers']
    wrong = total - correct
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
        f"✅ صحیح: <b>{correct}</b>\n❌ اشتباه: <b>{wrong}</b>\n"
        f"📈 درصد: <b>{pct}%</b>\n━━━━━━━━━━━━━\n"
        f"⚡ <b>نقاط ضعف:</b>\n{weak_text}",
        parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
    )
