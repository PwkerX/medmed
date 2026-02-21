"""
🩺 ربات پزشکی کامل
"""

import os
import sys
import logging

# اضافه کردن مسیر فعلی
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    CallbackQueryHandler, ConversationHandler
)

from start import start_handler, register_handler, REGISTER
from dashboard import dashboard_callback
from resources import resources_callback, upload_file_handler, upload_metadata_handler, UPLOAD_METADATA
from archive import archive_callback
from questions import questions_callback, handle_question_answer, ANSWERING
from schedule import schedule_callback
from stats import stats_callback
from notifications import notifications_callback
from admin import admin_callback, admin_broadcast_handler, BROADCAST
from search import search_handler, SEARCH
from message_router import route_message

logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TOKEN:
    logger.error("❌ TELEGRAM_TOKEN تنظیم نشده!")
    sys.exit(1)


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # ── ConversationHandler ──
    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start_handler)],
        states={
            REGISTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_handler)],
            UPLOAD_METADATA: [MessageHandler(filters.TEXT & ~filters.COMMAND, upload_metadata_handler)],
            SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_handler)],
            ANSWERING: [CallbackQueryHandler(handle_question_answer, pattern='^answer:')],
            BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_handler)],
        },
        fallbacks=[CommandHandler('start', start_handler)],
        allow_reentry=True,
        per_message=False,
    )
    app.add_handler(conv)

    # ── Callback Handlers ──
    app.add_handler(CallbackQueryHandler(dashboard_callback,    pattern='^dashboard'))
    app.add_handler(CallbackQueryHandler(resources_callback,    pattern='^(resources|download_resource)'))
    app.add_handler(CallbackQueryHandler(archive_callback,      pattern='^(archive|download_video)'))
    app.add_handler(CallbackQueryHandler(questions_callback,    pattern='^(questions|answer)'))
    app.add_handler(CallbackQueryHandler(schedule_callback,     pattern='^schedule'))
    app.add_handler(CallbackQueryHandler(stats_callback,        pattern='^stats'))
    app.add_handler(CallbackQueryHandler(notifications_callback,pattern='^notif'))
    app.add_handler(CallbackQueryHandler(admin_callback,        pattern='^admin'))

    # ── File Handler ──
    app.add_handler(MessageHandler(filters.Document.ALL | filters.VIDEO, upload_file_handler))

    # ── Text Router ──
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, route_message))

    logger.info("🩺 ربات پزشکی شروع به کار کرد...")
    app.run_polling(drop_pending_updates=True, allowed_updates=["message", "callback_query"])


if __name__ == '__main__':
    main()
