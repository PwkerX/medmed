from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

TERMS = ['ترم ۱', 'ترم ۲', 'ترم ۳', 'ترم ۴', 'ترم ۵']

CONTENT_TYPES = [
    ('video', '🎥 ویدیو کلاس'),
    ('ppt', '📊 پاورپوینت'),
    ('pdf', '📄 جزوه PDF'),
    ('note', '📝 نکات'),
    ('test', '🧪 تست'),
    ('voice', '🎙 ویس استاد'),
]

NOTIF_LABELS = {
    'new_resources': '📚 منابع جدید',
    'schedule': '📅 تغییر برنامه',
    'exam': '📝 یادآوری امتحان',
    'daily_question': '🧪 سوال روزانه'
}


def main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🩺 داشبورد"), KeyboardButton("🔬 علوم پایه")],
        [KeyboardButton("🧪 بانک سوال"), KeyboardButton("❓ سوالات متداول")],
        [KeyboardButton("📅 برنامه"), KeyboardButton("📊 آمار من")],
        [KeyboardButton("🔔 اعلان‌ها"), KeyboardButton("🔍 جستجو")]
    ], resize_keyboard=True)


def content_admin_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🩺 داشبورد"), KeyboardButton("🔬 علوم پایه")],
        [KeyboardButton("🧪 بانک سوال"), KeyboardButton("❓ سوالات متداول")],
        [KeyboardButton("📅 برنامه"), KeyboardButton("📊 آمار من")],
        [KeyboardButton("🔔 اعلان‌ها"), KeyboardButton("🔍 جستجو")],
        [KeyboardButton("🎓 پنل محتوا")]
    ], resize_keyboard=True)


def admin_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🩺 داشبورد"), KeyboardButton("🔬 علوم پایه")],
        [KeyboardButton("🧪 بانک سوال"), KeyboardButton("❓ سوالات متداول")],
        [KeyboardButton("📅 برنامه"), KeyboardButton("📊 آمار من")],
        [KeyboardButton("🔔 اعلان‌ها"), KeyboardButton("🔍 جستجو")],
        [KeyboardButton("👨‍⚕️ پنل ادمین"), KeyboardButton("🎓 پنل محتوا")]
    ], resize_keyboard=True)


def back_btn(data):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data=data)]])
