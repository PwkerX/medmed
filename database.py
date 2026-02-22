import os
import motor.motor_asyncio
from datetime import datetime, timedelta
from bson import ObjectId


class DB:
    def __init__(self):
        uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
        self.client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        db = self.client['medical_bot']
        self.users = db['users']
        self.resources = db['resources']
        self.videos = db['videos']
        self.questions = db['questions']
        self.schedules = db['schedules']
        self.stats = db['stats']
        self.answers = db['answers']
        self.lessons = db['lessons']      # درس‌های داینامیک
        self.topics = db['topics']        # مباحث داینامیک

    # ───────────── DYNAMIC LESSONS ─────────────
    async def get_lessons(self):
        docs = await self.lessons.find({}).sort('name', 1).to_list(200)
        if not docs:
            # بار اول: درس‌های پیش‌فرض رو ذخیره کن
            defaults = ['آناتومی', 'فیزیولوژی', 'بیوشیمی', 'بافت‌شناسی',
                        'میکروبیولوژی', 'پاتولوژی', 'ایمنی‌شناسی', 'فارماکولوژی',
                        'سمیولوژی', 'رادیولوژی']
            for l in defaults:
                await self.lessons.insert_one({'name': l, 'created_at': datetime.now().isoformat()})
            docs = await self.lessons.find({}).sort('name', 1).to_list(200)
        return [d['name'] for d in docs]

    async def add_lesson(self, name):
        existing = await self.lessons.find_one({'name': name})
        if existing:
            return False
        await self.lessons.insert_one({'name': name, 'created_at': datetime.now().isoformat()})
        return True

    async def delete_lesson(self, name):
        await self.lessons.delete_one({'name': name})

    async def get_topics(self, lesson):
        docs = await self.topics.find({'lesson': lesson}).sort('name', 1).to_list(200)
        if not docs:
            defaults = {
                'آناتومی': ['اندام فوقانی', 'اندام تحتانی', 'تنه', 'سر و گردن', 'سیستم عصبی'],
                'فیزیولوژی': ['قلب', 'تنفس', 'کلیه', 'عصبی', 'گوارش'],
                'بیوشیمی': ['متابولیسم', 'آنزیم‌ها', 'اسیدهای نوکلئیک', 'پروتئین‌ها'],
                'بافت‌شناسی': ['بافت پوششی', 'بافت پیوندی', 'بافت عضلانی', 'بافت عصبی'],
                'میکروبیولوژی': ['باکتری‌ها', 'ویروس‌ها', 'قارچ‌ها', 'انگل‌ها'],
                'پاتولوژی': ['التهاب', 'نئوپلازی', 'قلب', 'ریه', 'کبد'],
                'ایمنی‌شناسی': ['ایمنی ذاتی', 'ایمنی اکتسابی', 'آنتی‌بادی'],
                'فارماکولوژی': ['اصول کلی', 'قلب', 'عصبی', 'آنتی‌بیوتیک'],
                'سمیولوژی': ['معاینه عمومی', 'قلب', 'ریه', 'شکم'],
                'رادیولوژی': ['اشعه ایکس', 'CT Scan', 'MRI', 'سونوگرافی'],
            }
            lesson_topics = defaults.get(lesson, ['عمومی', 'پیشرفته'])
            for t in lesson_topics:
                await self.topics.insert_one({'lesson': lesson, 'name': t, 'created_at': datetime.now().isoformat()})
            docs = await self.topics.find({'lesson': lesson}).sort('name', 1).to_list(200)
        return [d['name'] for d in docs]

    async def add_topic(self, lesson, name):
        existing = await self.topics.find_one({'lesson': lesson, 'name': name})
        if existing:
            return False
        await self.topics.insert_one({'lesson': lesson, 'name': name, 'created_at': datetime.now().isoformat()})
        return True

    async def delete_topic(self, lesson, name):
        await self.topics.delete_one({'lesson': lesson, 'name': name})

    # ───────────── USERS ─────────────
    async def get_user(self, uid):
        return await self.users.find_one({'user_id': uid})

    async def create_user(self, uid, name, student_id, group, username=None):
        await self.users.insert_one({
            'user_id': uid, 'name': name, 'student_id': student_id,
            'group': group, 'username': username,
            'registered_at': datetime.now().isoformat(),
            'approved': False,
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

    # ───────────── RESOURCES ─────────────
    async def add_resource(self, term, lesson, topic, rtype, file_id, meta):
        r = await self.resources.insert_one({
            'term': term, 'lesson': lesson, 'topic': topic, 'type': rtype,
            'file_id': file_id,
            'metadata': {
                'upload_date': datetime.now().isoformat(),
                'downloads': 0,
                'version': meta.get('version', '1.0'),
                'tags': meta.get('tags', []),
                'importance': meta.get('importance', 3),
                'description': meta.get('description', '')
            }
        })
        return r.inserted_id

    async def get_resources(self, term=None, lesson=None, topic=None, rtype=None):
        q = {}
        if term: q['term'] = term
        if lesson: q['lesson'] = lesson
        if topic and topic != 'همه': q['topic'] = topic
        if rtype and rtype != 'همه': q['type'] = rtype
        return await self.resources.find(q).sort('metadata.upload_date', -1).to_list(100)

    async def get_resource(self, rid):
        try:
            return await self.resources.find_one({'_id': ObjectId(rid)})
        except:
            return None

    async def delete_resource(self, rid):
        try:
            await self.resources.delete_one({'_id': ObjectId(rid)})
        except:
            pass

    async def inc_download(self, rid, uid):
        try:
            await self.resources.update_one({'_id': ObjectId(rid)}, {'$inc': {'metadata.downloads': 1}})
        except:
            pass
        await self.log(uid, 'download', {'resource_id': rid})

    async def new_resources_count(self, days=7):
        ago = (datetime.now() - timedelta(days=days)).isoformat()
        return await self.resources.count_documents({'metadata.upload_date': {'$gt': ago}})

    async def search_resources(self, text):
        return await self.resources.find({'$or': [
            {'lesson': {'$regex': text, '$options': 'i'}},
            {'topic': {'$regex': text, '$options': 'i'}},
            {'type': {'$regex': text, '$options': 'i'}},
            {'metadata.tags': {'$elemMatch': {'$regex': text, '$options': 'i'}}}
        ]}).limit(20).to_list(20)

    # ───────────── VIDEOS ─────────────
    async def add_video(self, lesson, topic, teacher, date, file_id):
        r = await self.videos.insert_one({
            'lesson': lesson, 'topic': topic, 'teacher': teacher,
            'date': date, 'file_id': file_id,
            'upload_date': datetime.now().isoformat(), 'views': 0
        })
        return r.inserted_id

    async def get_videos(self, lesson=None, teacher=None):
        q = {}
        if lesson: q['lesson'] = lesson
        if teacher and teacher != 'همه': q['teacher'] = teacher
        return await self.videos.find(q).sort('date', -1).to_list(100)

    async def get_video(self, vid):
        try:
            return await self.videos.find_one({'_id': ObjectId(vid)})
        except:
            return None

    async def delete_video(self, vid):
        try:
            await self.videos.delete_one({'_id': ObjectId(vid)})
        except:
            pass

    # ───────────── QUESTIONS ─────────────
    async def add_question(self, lesson, topic, difficulty, question, options, correct, explanation, creator):
        r = await self.questions.insert_one({
            'lesson': lesson, 'topic': topic, 'difficulty': difficulty,
            'question': question, 'options': options,
            'correct_answer': correct, 'explanation': explanation,
            'creator_id': creator, 'approved': False,
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
            q = None
            try:
                q = await self.questions.find_one({'_id': ObjectId(qid)})
            except:
                pass
            if q:
                await self.users.update_one(
                    {'user_id': uid},
                    {'$addToSet': {'weak_topics': q['topic']}}
                )
        await self.log(uid, 'answer', {'qid': qid, 'correct': is_correct})

    # ───────────── SCHEDULES ─────────────
    async def add_schedule(self, stype, lesson, teacher, date, time, location, notes=''):
        r = await self.schedules.insert_one({
            'type': stype, 'lesson': lesson, 'teacher': teacher,
            'date': date, 'time': time, 'location': location, 'notes': notes,
            'created_at': datetime.now().isoformat()
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
            'resources': await self.resources.count_documents({}),
            'videos': await self.videos.count_documents({}),
            'questions': await self.questions.count_documents({'approved': True}),
            'downloads': await self.stats.count_documents({'action': 'download'})
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
