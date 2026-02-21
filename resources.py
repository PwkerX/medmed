import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import db
from utils import TERMS, LESSONS, TOPICS, RESOURCE_TYPES

logger = logging.getLogger(__name__)
UPLOAD_METADATA = 1
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))
CHANNEL_ID = os.getenv('CHANNEL_ID', '')


async def resources_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    parts = data.split(':')

    # download_resource:ID
    if data.startswith('download_resource:'):
        rid = parts[1]
        resource = await db.get_resource(rid)
        if not resource:
            await query.answer("❌ فایل پیدا نشد!", show_alert=True)
            return
        await db.inc_download(rid, update.effective_user.id)
        m = resource['metadata']
        caption = (
            f"📄 <b>{resource.get('type','')}</b> — {resource.get('lesson','')} / {resource.get('topic','')}\n"
            f"📌 نسخه {m.get('version','1')} | ⭐{'⭐'*m.get('importance',3)}\n"
            f"🏷 {', '.join(m.get('tags',[]))}\n"
            f"📝 {m.get('description','')}"
        )
        try:
            await context.bot.send_document(update.effective_chat.id, resource['file_id'],
                                            caption=caption, parse_mode='HTML')
        except:
            try:
                await context.bot.send_video(update.effective_chat.id, resource['file_id'],
                                             caption=caption, parse_mode='HTML')
            except:
                await query.answer("❌ خطا در ارسال فایل!", show_alert=True)
        return

    action = parts[1] if len(parts) > 1 else 'main'

    if action in ('main', 'back_main'):
        keyboard = []
        for i in range(0, len(TERMS), 2):
            row = [InlineKeyboardButton(TERMS[i], callback_data=f'resources:term:{TERMS[i]}'[:64])]
            if i + 1 < len(TERMS):
                row.append(InlineKeyboardButton(TERMS[i+1], callback_data=f'resources:term:{TERMS[i+1]}'[:64]))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔍 جستجو", callback_data='resources:search')])
        await query.edit_message_text(
            "📚 <b>منابع درسی</b>\n\nترم را انتخاب کنید:",
            parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif action == 'term':
        term = ':'.join(parts[2:])
        keyboard = []
        for i in range(0, len(LESSONS), 2):
            row = [InlineKeyboardButton(LESSONS[i], callback_data=f'resources:lesson:{term}:{LESSONS[i]}'[:64])]
            if i + 1 < len(LESSONS):
                row.append(InlineKeyboardButton(LESSONS[i+1], callback_data=f'resources:lesson:{term}:{LESSONS[i+1]}'[:64]))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='resources:main')])
        await query.edit_message_text(
            f"📚 <b>{term}</b>\n\nدرس را انتخاب کنید:",
            parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif action == 'lesson':
        term, lesson = parts[2], parts[3]
        topics = TOPICS.get(lesson, ['عمومی', 'پیشرفته', 'جامع'])
        keyboard = [[InlineKeyboardButton(t, callback_data=f'resources:topic:{term}:{lesson}:{t}'[:64])] for t in topics]
        keyboard.append([InlineKeyboardButton("📂 همه مباحث", callback_data=f'resources:topic:{term}:{lesson}:همه'[:64])])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f'resources:term:{term}'[:64])])
        await query.edit_message_text(
            f"📚 <b>{lesson}</b> — {term}\n\nمبحث را انتخاب کنید:",
            parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif action == 'topic':
        term, lesson, topic = parts[2], parts[3], ':'.join(parts[4:])
        keyboard = [[InlineKeyboardButton(rt, callback_data=f'resources:files:{term}:{lesson}:{topic}:{rt}'[:64])] for rt in RESOURCE_TYPES]
        keyboard.append([InlineKeyboardButton("📂 همه انواع", callback_data=f'resources:files:{term}:{lesson}:{topic}:همه'[:64])])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f'resources:lesson:{term}:{lesson}'[:64])])
        await query.edit_message_text(
            f"📚 <b>{topic}</b>\n{lesson} | {term}\n\nنوع فایل را انتخاب کنید:",
            parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif action == 'files':
        term, lesson, topic, rtype = parts[2], parts[3], parts[4], ':'.join(parts[5:])
        files = await db.get_resources(term=term, lesson=lesson, topic=topic, rtype=rtype)
        if not files:
            await query.edit_message_text(
                f"📂 <b>{rtype}</b> — {topic}\n\n❌ فایلی پیدا نشد.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data=f'resources:topic:{term}:{lesson}:{topic}'[:64])]])
            )
            return
        keyboard = []
        for f in files:
            fid = str(f['_id'])
            m = f['metadata']
            stars = '⭐' * m.get('importance', 3)
            label = f"📥 {f.get('type','')} v{m.get('version','1')} {stars} ⬇️{m.get('downloads',0)}"
            keyboard.append([InlineKeyboardButton(label, callback_data=f'download_resource:{fid}')])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f'resources:topic:{term}:{lesson}:{topic}'[:64])])
        await query.edit_message_text(
            f"📂 <b>{rtype}</b> — {topic}\n{lesson} | {term}\n\n{len(files)} فایل موجود:",
            parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif action == 'search':
        context.user_data['search_mode'] = 'resources'
        await query.edit_message_text(
            "🔍 <b>جستجو در منابع</b>\n\nکلمه کلیدی:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data='resources:main')]])
        )
        context.user_data['awaiting_search'] = True


async def upload_file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    mode = context.user_data.get('upload_mode', '')
    if not mode:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📚 منبع درسی", callback_data='admin:set_mode:resource')],
            [InlineKeyboardButton("🎥 ویدیو کلاس", callback_data='admin:set_mode:video')]
        ])
        file = update.message.document or update.message.video
        if file:
            context.user_data['pending_file_id'] = getattr(file, 'file_id', '')
        await update.message.reply_text("📤 فایل دریافت شد. نوع را انتخاب کنید:", reply_markup=keyboard)
        return

    file = update.message.document or update.message.video
    if file:
        context.user_data['upload_file_id'] = getattr(file, 'file_id', '')

    if mode == 'resource':
        path = context.user_data.get('upload_path', {})
        p = f"{path.get('term','؟')} ← {path.get('lesson','؟')} ← {path.get('topic','؟')} ← {path.get('type','؟')}"
        await update.message.reply_text(
            f"📤 فایل دریافت شد.\n📌 مسیر: {p}\n\n"
            "متادیتا را وارد کنید:\n"
            "`نسخه, تگ‌ها, اهمیت(1-5), توضیحات`\n"
            "مثال: `2.0, قلب عروق, 5, جزوه کامل دکتر محمدی`",
            parse_mode='Markdown'
        )
        return UPLOAD_METADATA

    elif mode == 'video':
        await update.message.reply_text(
            "📹 ویدیو دریافت شد.\n\n"
            "اطلاعات را وارد کنید:\n"
            "`استاد, تاریخ(YYYY-MM-DD), توضیح`\n"
            "مثال: `دکتر محمدی, 2024-03-15, جلسه اول آناتومی`",
            parse_mode='Markdown'
        )
        return UPLOAD_METADATA


async def upload_metadata_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    mode = context.user_data.get('upload_mode', 'resource')
    file_id = context.user_data.get('upload_file_id', '')

    try:
        parts = [p.strip() for p in text.split(',')]

        if mode == 'resource':
            if len(parts) < 3:
                raise ValueError("کم")
            version = parts[0]
            tags = parts[1].split() if parts[1] else []
            importance = max(1, min(5, int(parts[2])))
            description = parts[3] if len(parts) > 3 else ''

            path = context.user_data.get('upload_path', {})
            term = path.get('term', 'ترم ۱')
            lesson = path.get('lesson', 'عمومی')
            topic = path.get('topic', 'عمومی')
            rtype = path.get('type', '📄 جزوه')

            rid = await db.add_resource(term, lesson, topic, rtype, file_id, {
                'version': version, 'tags': tags,
                'importance': importance, 'description': description
            })

            if CHANNEL_ID:
                try:
                    await context.bot.send_document(
                        CHANNEL_ID, file_id,
                        caption=f"📚 {lesson} — {topic}\n{rtype} v{version}\n{'⭐'*importance}",
                        parse_mode='HTML'
                    )
                except: pass

            # اطلاع‌رسانی
            users = await db.notif_users('new_resources')
            count = 0
            for u in users:
                if u['user_id'] != ADMIN_ID:
                    try:
                        await context.bot.send_message(
                            u['user_id'],
                            f"📚 <b>منبع جدید:</b> {lesson} — {topic}\n{rtype}",
                            parse_mode='HTML'
                        )
                        count += 1
                    except: pass

            await update.message.reply_text(
                f"✅ منبع اضافه شد!\n📚 {lesson} — {topic}\n🔔 {count} نفر مطلع شدند."
            )

        elif mode == 'video':
            if len(parts) < 2:
                raise ValueError("کم")
            teacher = parts[0]
            date = parts[1]
            description = parts[2] if len(parts) > 2 else ''
            path = context.user_data.get('upload_path', {})
            lesson = path.get('lesson', 'عمومی')
            topic = path.get('topic', 'عمومی')
            await db.add_video(lesson, topic, teacher, date, file_id)
            await update.message.reply_text(f"✅ ویدیو اضافه شد!\n🎥 {lesson} | {teacher} | {date}")

    except ValueError as e:
        await update.message.reply_text(f"❌ خطا: {e}\nدوباره وارد کنید:")
        return UPLOAD_METADATA
    except Exception as e:
        logger.error(f"upload_metadata error: {e}")
        await update.message.reply_text("❌ خطای ناشناخته. دوباره تلاش کنید:")
        return UPLOAD_METADATA

    for k in ['upload_mode', 'upload_file_id', 'upload_path', 'pending_file_id']:
        context.user_data.pop(k, None)
    return ConversationHandler.END
