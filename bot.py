"""
🩺 ربات پزشکی کامل - نسخه ۵
"""

import os
import sys
import logging
import asyncio
from datetime import datetime, time as dtime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    CallbackQueryHandler, ConversationHandler
)

from start import (start_handler, register_handler, register_start_callback,
                   step_name_handler, step_student_id_handler,
                   REGISTER, STEP_NAME, STEP_STUDENT_ID, STEP_GROUP)
from dashboard import dashboard_callback
from resources import resources_callback, upload_file_handler, upload_metadata_handler, UPLOAD_METADATA
from archive import archive_callback
from questions import (
    questions_callback, handle_question_answer, ANSWERING,
    handle_create_question_steps, handle_difficulty_choice, CREATING_Q
)
from schedule import schedule_callback
from stats import stats_callback
from notifications import notifications_callback
from admin import admin_callback, admin_broadcast_handler, BROADCAST
from search import search_handler, SEARCH
from message_router import route_message
from basic_science import basic_science_callback
from references import references_callback
from content_admin import content_admin_callback, ca_file_handler, ca_text_handler, CA_WAITING_FILE, CA_WAITING_TEXT
from faq import faq_callback

logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv('TELEGRAM_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))

if not TOKEN:
    logger.error("❌ TELEGRAM_TOKEN تنظیم نشده!")
    sys.exit(1)


async def send_exam_reminders(app):
    """یادآوری هوشمند امتحانات — هر روز ساعت ۸ صبح"""
    from database import db
    REMIND_DAYS = [7, 3, 1]

    while True:
        now = datetime.now()
        # منتظر ساعت ۸ صبح بعدی بمان
        next_run = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if now >= next_run:
            next_run = next_run.replace(day=now.day + 1)
        wait_secs = (next_run - now).total_seconds()
        await asyncio.sleep(wait_secs)

        try:
            for days in REMIND_DAYS:
                exams = await db.get_exams_for_reminder(days)
                for exam in exams:
                    sid = str(exam['_id'])
                    lesson = exam.get('lesson', '')
                    date = exam.get('date', '')
                    time_str = exam.get('time', '')
                    location = exam.get('location', '')
                    teacher = exam.get('teacher', '')

                    if days == 1:
                        day_text = "⚠️ <b>فردا</b>"
                    elif days == 3:
                        day_text = "📅 <b>۳ روز دیگر</b>"
                    else:
                        day_text = "📅 <b>۷ روز دیگر</b>"

                    msg = (
                        f"🔔 <b>یادآوری امتحان</b>\n\n"
                        f"📚 درس: <b>{lesson}</b>\n"
                        f"⏰ زمان: {day_text} — {date} ساعت {time_str}\n"
                        f"📍 مکان: {location}\n"
                        f"👨‍🏫 استاد: {teacher}"
                    )

                    users = await db.notif_users('exam')
                    sent = 0
                    for u in users:
                        try:
                            await app.bot.send_message(u['user_id'], msg, parse_mode='HTML')
                            sent += 1
                        except:
                            pass

                    if sent > 0:
                        await db.mark_exam_notified(sid, days)
                        logger.info(f"✅ یادآوری {lesson} ({days} روز) — {sent} نفر")

        except Exception as e:
            logger.error(f"reminder error: {e}")

        await asyncio.sleep(3600)  # بررسی هر ساعت


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # ── ConversationHandler اصلی ──
    conv = ConversationHandler(
        entry_points=[
            CommandHandler('start', start_handler),
            CallbackQueryHandler(questions_callback, pattern='^questions:cr_topic:'),
        ],
        states={
            REGISTER: [CallbackQueryHandler(register_start_callback, pattern="^register:")],
            STEP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, step_name_handler),
                        CallbackQueryHandler(register_start_callback, pattern="^register:cancel")],
            STEP_STUDENT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, step_student_id_handler),
                              CallbackQueryHandler(register_start_callback, pattern="^register:cancel")],
            STEP_GROUP: [CallbackQueryHandler(register_start_callback, pattern="^register:(group1|group2|cancel)")],
            UPLOAD_METADATA: [MessageHandler(filters.TEXT & ~filters.COMMAND, upload_metadata_handler)],
            SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_handler)],
            ANSWERING: [CallbackQueryHandler(handle_question_answer, pattern='^answer:')],
            BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_handler)],
            CREATING_Q: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_create_question_steps),
                CallbackQueryHandler(handle_difficulty_choice, pattern='^qd:'),
                CallbackQueryHandler(questions_callback, pattern='^questions:'),
            ],
            CA_WAITING_FILE: [
                MessageHandler(filters.Document.ALL | filters.VIDEO | filters.AUDIO | filters.VOICE, ca_file_handler),
                CallbackQueryHandler(content_admin_callback, pattern='^ca:'),
            ],
            CA_WAITING_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ca_text_handler),
                CallbackQueryHandler(content_admin_callback, pattern='^ca:'),
            ],
        },
        fallbacks=[CommandHandler('start', start_handler)],
        allow_reentry=True,
        per_message=False,
    )
    app.add_handler(conv)

    # ── Callback Handlers ──
    app.add_handler(CallbackQueryHandler(dashboard_callback,     pattern='^dashboard'))
    app.add_handler(CallbackQueryHandler(resources_callback,     pattern='^(resources|download_resource)'))
    app.add_handler(CallbackQueryHandler(archive_callback,       pattern='^(archive|download_video)'))
    app.add_handler(CallbackQueryHandler(questions_callback,     pattern='^(questions|answer|download_qbank)'))
    app.add_handler(CallbackQueryHandler(schedule_callback,      pattern='^schedule'))
    app.add_handler(CallbackQueryHandler(stats_callback,         pattern='^stats'))
    app.add_handler(CallbackQueryHandler(notifications_callback, pattern='^notif'))
    app.add_handler(CallbackQueryHandler(admin_callback,         pattern='^admin'))

    # ── Basic Science & FAQ & Content Admin ──
    app.add_handler(CallbackQueryHandler(basic_science_callback, pattern='^(bs:|bs_dl:|resources:bs)'))
    app.add_handler(CallbackQueryHandler(references_callback,    pattern='^(ref:|resources:ref)'))
    app.add_handler(CallbackQueryHandler(faq_callback,           pattern='^faq:'))
    app.add_handler(CallbackQueryHandler(content_admin_callback, pattern='^ca:'))

    # ── File & Voice Handler ──
    async def unified_file_handler(update, context):
        uid = update.effective_user.id
        ca_mode = context.user_data.get('ca_mode', '')
        if ca_mode == 'waiting_file' and await db.is_content_admin(uid):
            return await ca_file_handler(update, context)
        if uid == int(os.getenv('ADMIN_ID', '0')):
            return await upload_file_handler(update, context)

    app.add_handler(MessageHandler(
        filters.Document.ALL | filters.VIDEO | filters.AUDIO | filters.VOICE,
        unified_file_handler
    ))

    # ── Text Router ──
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, route_message))

    # ── Job: یادآوری امتحان ──
    async def post_init(application):
        asyncio.create_task(send_exam_reminders(application))

    app.post_init = post_init

    logger.info("🩺 ربات پزشکی شروع به کار کرد...")
    app.run_polling(drop_pending_updates=True, allowed_updates=["message", "callback_query"])


if __name__ == '__main__':
    main()
