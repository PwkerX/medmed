import os
import motor.motor_asyncio
from datetime import datetime, timedelta
from bson import ObjectId


class DB:
    def __init__(self):
        uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
        self.client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        _db = self.client['medical_bot']
        self.users = _db['users']
        self.questions = _db['questions']
        self.qbank_files = _db['qbank_files']
        self.schedules = _db['schedules']
        self.stats = _db['stats']
        self.answers = _db['answers']
        # علوم پایه - ساختار جدید
        self.basic_sci_lessons = _db['bs_lessons']    # درس‌های هر ترم
        self.basic_sci_sessions = _db['bs_sessions']  # جلسات هر درس
        self.basic_sci_content = _db['bs_content']    # محتوای هر جلسه
        # سوالات متداول
        self.faq = _db['faq']

    # ───────────── USERS ─────────────
    async def get_user(self, uid):
        return await self.users.find_one({'user_id': uid})

    async def create_user(self, uid, name, student_id, group, username=None):
        await self.users.insert_one({
            'user_id': uid, 'name': name, 'student_id': student_id,
            'group': group, 'username': username,
            'registered_at': datetime.now().isoformat(),
            'approved': False,
            'role': 'student',   # student | content_admin | admin
            'notification_settings': {
                'new_resources': True, 'schedule': True,
                'exam': True, 'daily_question': True
            },
            'total_answers': 0, 'correct_answers': 0, 'weak_topics': []
        })

    async def update_user(self, uid, data):
        await self.users.update_one({'user_id': uid}, {'$set': data})

    async def delete_user(self, uid):
        await self.users.delete_one({'user_id': uid})

    async def all_users(self, approved_only=True):
        q = {'approved': True} if approved_only else {}
        return await self.users.find(q).to_list(5000)

    async def pending_users(self):
        return await self.users.find({'approved': False}).to_list(100)

    async def notif_users(self, ntype):
        return await self.users.find(
            {'approved': True, f'notification_settings.{ntype}': True}
        ).to_list(5000)

    async def get_content_admins(self):
        return await self.users.find({'role': 'content_admin', 'approved': True}).to_list(100)

    async def is_content_admin(self, uid):
        admin_id = int(os.getenv('ADMIN_ID', '0'))
        if uid == admin_id:
            return True
        u = await self.get_user(uid)
        return u and u.get('role') in ('content_admin', 'admin')

    # ───────────── علوم پایه - درس‌های ترم ─────────────
    async def bs_get_lessons(self, term):
        """درس‌های یک ترم خاص"""
        return await self.basic_sci_lessons.find(
            {'term': term}
        ).sort('order', 1).to_list(50)

    async def bs_add_lesson(self, term, name, teacher=''):
        existing = await self.basic_sci_lessons.find_one({'term': term, 'name': name})
        if existing:
            return None
        count = await self.basic_sci_lessons.count_documents({'term': term})
        r = await self.basic_sci_lessons.insert_one({
            'term': term, 'name': name, 'teacher': teacher,
            'order': count, 'created_at': datetime.now().isoformat()
        })
        return r.inserted_id

    async def bs_delete_lesson(self, lesson_id):
        try:
            oid = ObjectId(lesson_id)
            await self.basic_sci_lessons.delete_one({'_id': oid})
            # حذف جلسات و محتوا
            sessions = await self.basic_sci_sessions.find({'lesson_id': lesson_id}).to_list(200)
            for s in sessions:
                await self.basic_sci_content.delete_many({'session_id': str(s['_id'])})
            await self.basic_sci_sessions.delete_many({'lesson_id': lesson_id})
        except:
            pass

    async def bs_get_lesson(self, lesson_id):
        try:
            return await self.basic_sci_lessons.find_one({'_id': ObjectId(lesson_id)})
        except:
            return None

    # ───────────── علوم پایه - جلسات ─────────────
    async def bs_get_sessions(self, lesson_id):
        return await self.basic_sci_sessions.find(
            {'lesson_id': lesson_id}
        ).sort('number', 1).to_list(200)

    async def bs_add_session(self, lesson_id, number, topic, teacher):
        existing = await self.basic_sci_sessions.find_one(
            {'lesson_id': lesson_id, 'number': number}
        )
        if existing:
            await self.basic_sci_sessions.update_one(
                {'_id': existing['_id']},
                {'$set': {'topic': topic, 'teacher': teacher}}
            )
            return str(existing['_id'])
        r = await self.basic_sci_sessions.insert_one({
            'lesson_id': lesson_id, 'number': number,
            'topic': topic, 'teacher': teacher,
            'created_at': datetime.now().isoformat()
        })
        return str(r.inserted_id)

    async def bs_get_session(self, session_id):
        try:
            return await self.basic_sci_sessions.find_one({'_id': ObjectId(session_id)})
        except:
            return None

    async def bs_delete_session(self, session_id):
        try:
            await self.basic_sci_sessions.delete_one({'_id': ObjectId(session_id)})
            await self.basic_sci_content.delete_many({'session_id': session_id})
        except:
            pass

    # ───────────── علوم پایه - محتوا ─────────────
    async def bs_get_content(self, session_id):
        return await self.basic_sci_content.find(
            {'session_id': session_id}
        ).sort('uploaded_at', 1).to_list(50)

    async def bs_add_content(self, session_id, ctype, file_id, description=''):
        r = await self.basic_sci_content.insert_one({
            'session_id': session_id,
            'type': ctype,          # video | ppt | pdf | note | test | voice
            'file_id': file_id,
            'description': description,
            'uploaded_at': datetime.now().isoformat(),
            'downloads': 0
        })
        return r.inserted_id

    async def bs_delete_content(self, content_id):
        try:
            await self.basic_sci_content.delete_one({'_id': ObjectId(content_id)})
        except:
            pass

    async def bs_get_content_item(self, content_id):
        try:
            return await self.basic_sci_content.find_one({'_id': ObjectId(content_id)})
        except:
            return None

    async def bs_inc_download(self, content_id, uid):
        try:
            await self.basic_sci_content.update_one(
                {'_id': ObjectId(content_id)}, {'$inc': {'downloads': 1}}
            )
        except:
            pass
        await self.log(uid, 'bs_download', {'content_id': content_id})

    # ───────────── FAQ ─────────────
    async def faq_get_all(self):
        return await self.faq.find({}).sort('order', 1).to_list(50)

    async def faq_add(self, question, answer, category='عمومی'):
        count = await self.faq.count_documents({})
        await self.faq.insert_one({
            'question': question, 'answer': answer,
            'category': category, 'order': count,
            'created_at': datetime.now().isoformat()
        })

    async def faq_delete(self, fid):
        try:
            await self.faq.delete_one({'_id': ObjectId(fid)})
        except:
            pass

    async def faq_get_categories(self):
        docs = await self.faq.distinct('category')
        return docs if docs else ['عمومی']

    # ───────────── QBANK FILES ─────────────
    async def add_qbank_file(self, lesson, topic, file_id, description, file_type='document'):
        r = await self.qbank_files.insert_one({
            'lesson': lesson, 'topic': topic,
            'file_id': file_id, 'file_type': file_type,
            'description': description,
            'upload_date': datetime.now().isoformat(), 'downloads': 0
        })
        return r.inserted_id

    async def get_qbank_files(self, lesson=None, topic=None):
        q = {}
        if lesson: q['lesson'] = lesson
        if topic: q['topic'] = topic
        return await self.qbank_files.find(q).sort('upload_date', -1).to_list(100)

    async def get_qbank_file(self, fid):
        try:
            return await self.qbank_files.find_one({'_id': ObjectId(fid)})
        except:
            return None

    async def inc_qbank_download(self, fid, uid):
        try:
            await self.qbank_files.update_one({'_id': ObjectId(fid)}, {'$inc': {'downloads': 1}})
        except:
            pass
        await self.log(uid, 'qbank_download', {'file_id': fid})

    async def delete_qbank_file(self, fid):
        try:
            await self.qbank_files.delete_one({'_id': ObjectId(fid)})
        except:
            pass

    # ───────────── QUESTIONS ─────────────
    async def add_question(self, lesson, topic, difficulty, question, options, correct, explanation, creator, auto_approve=False):
        r = await self.questions.insert_one({
            'lesson': lesson, 'topic': topic, 'difficulty': difficulty,
            'question': question, 'options': options,
            'correct_answer': correct, 'explanation': explanation,
            'creator_id': creator, 'approved': auto_approve,
            'created_at': datetime.now().isoformat(),
            'attempt_count': 0, 'correct_count': 0
        })
        return r.inserted_id

    async def get_questions(self, lesson=None, topic=None, difficulty=None, limit=1, exclude=None):
        q = {'approved': True}
        if lesson: q['lesson'] = lesson
        if topic and topic != 'همه': q['topic'] = topic
        if difficulty: q['difficulty'] = difficulty
        if exclude:
            try:
                q['_id'] = {'$nin': [ObjectId(i) for i in exclude]}
            except:
                pass
        return await self.questions.find(q).limit(limit).to_list(limit)

    async def get_weak_questions(self, uid, limit=1):
        user = await self.get_user(uid)
        weak = user.get('weak_topics', []) if user else []
        if not weak:
            return await self.get_questions(limit=limit)
        return await self.questions.find(
            {'approved': True, 'topic': {'$in': weak}}
        ).limit(limit).to_list(limit)

    async def pending_questions(self):
        return await self.questions.find({'approved': False}).to_list(50)

    async def approve_question(self, qid):
        try:
            await self.questions.update_one({'_id': ObjectId(qid)}, {'$set': {'approved': True}})
        except:
            pass

    async def delete_question(self, qid):
        try:
            await self.questions.delete_one({'_id': ObjectId(qid)})
        except:
            pass

    async def save_answer(self, uid, qid, selected, is_correct):
        await self.answers.insert_one({
            'user_id': uid, 'question_id': qid,
            'selected': selected, 'is_correct': is_correct,
            'answered_at': datetime.now().isoformat()
        })
        await self.users.update_one(
            {'user_id': uid},
            {'$inc': {'total_answers': 1, 'correct_answers': 1 if is_correct else 0}}
        )
        try:
            await self.questions.update_one(
                {'_id': ObjectId(qid)},
                {'$inc': {'attempt_count': 1, 'correct_count': 1 if is_correct else 0}}
            )
        except:
            pass
        if not is_correct:
            try:
                q = await self.questions.find_one({'_id': ObjectId(qid)})
                if q:
                    await self.users.update_one(
                        {'user_id': uid},
                        {'$addToSet': {'weak_topics': q['topic']}}
                    )
            except:
                pass
        await self.log(uid, 'answer', {'qid': qid, 'correct': is_correct})

    # ───────────── SCHEDULES ─────────────
    async def add_schedule(self, stype, lesson, teacher, date, time, location, notes=''):
        r = await self.schedules.insert_one({
            'type': stype, 'lesson': lesson, 'teacher': teacher,
            'date': date, 'time': time, 'location': location, 'notes': notes,
            'created_at': datetime.now().isoformat(),
            'notified_days': []
        })
        return r.inserted_id

    async def get_schedules(self, stype=None, upcoming=True):
        q = {}
        if stype: q['type'] = stype
        if upcoming:
            q['date'] = {'$gte': datetime.now().strftime('%Y-%m-%d')}
        return await self.schedules.find(q).sort('date', 1).to_list(100)

    async def delete_schedule(self, sid):
        try:
            await self.schedules.delete_one({'_id': ObjectId(sid)})
        except:
            pass

    async def upcoming_exams(self, days=7):
        today = datetime.now().strftime('%Y-%m-%d')
        future = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
        return await self.schedules.find(
            {'type': 'exam', 'date': {'$gte': today, '$lte': future}}
        ).sort('date', 1).to_list(20)

    async def get_exams_for_reminder(self, remind_days):
        target_date = (datetime.now() + timedelta(days=remind_days)).strftime('%Y-%m-%d')
        key = f'd{remind_days}'
        return await self.schedules.find({
            'type': 'exam', 'date': target_date,
            'notified_days': {'$ne': key}
        }).to_list(50)

    async def mark_exam_notified(self, sid, remind_days):
        key = f'd{remind_days}'
        try:
            await self.schedules.update_one(
                {'_id': ObjectId(sid)},
                {'$addToSet': {'notified_days': key}}
            )
        except:
            pass

    # ───────────── STATS ─────────────
    async def log(self, uid, action, data=None):
        await self.stats.insert_one({
            'user_id': uid, 'action': action,
            'data': data or {}, 'timestamp': datetime.now().isoformat()
        })

    async def user_stats(self, uid):
        downloads = await self.stats.count_documents({'user_id': uid, 'action': 'download'})
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        week_act = await self.stats.count_documents(
            {'user_id': uid, 'timestamp': {'$gt': week_ago}}
        )
        user = await self.get_user(uid)
        total = user.get('total_answers', 0) if user else 0
        correct = user.get('correct_answers', 0) if user else 0
        pct = round(correct / total * 100, 1) if total > 0 else 0
        return {
            'downloads': downloads, 'total_answers': total,
            'correct_answers': correct, 'percentage': pct,
            'week_activity': week_act,
            'weak_topics': user.get('weak_topics', []) if user else []
        }

    async def global_stats(self):
        return {
            'users': await self.users.count_documents({'approved': True}),
            'pending': await self.users.count_documents({'approved': False}),
            'questions': await self.questions.count_documents({'approved': True}),
            'qbank_files': await self.qbank_files.count_documents({}),
            'bs_lessons': await self.basic_sci_lessons.count_documents({}),
            'bs_sessions': await self.basic_sci_sessions.count_documents({}),
            'bs_content': await self.basic_sci_content.count_documents({}),
        }

    async def weekly_activity(self, uid):
        result = []
        for i in range(6, -1, -1):
            day = datetime.now() - timedelta(days=i)
            s = day.replace(hour=0, minute=0, second=0).isoformat()
            e = day.replace(hour=23, minute=59, second=59).isoformat()
            count = await self.stats.count_documents(
                {'user_id': uid, 'timestamp': {'$gte': s, '$lte': e}}
            )
            result.append((day.strftime('%m/%d'), count))
        return result


db = DB()
