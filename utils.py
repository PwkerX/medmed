from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

TERMS = ['ترم ۱', 'ترم ۲', 'ترم ۳', 'ترم ۴', 'ترم ۵', 'ترم ۶', 'ترم ۷']

RESOURCE_TYPES = ['📄 جزوه', '📊 پاورپوینت', '📝 نکات', '🧠 خلاصه', '🧪 تست', '🎙 ویس']
DIFFICULTIES = ['آسان 🟢', 'متوسط 🟡', 'سخت 🔴']

NOTIF_LABELS = {
    'new_resources': '📚 منابع جدید',
    'schedule': '📅 تغییر برنامه',
    'exam': '📝 یادآوری امتحان',
    'daily_question': '🧪 سوال روزانه'
}


def main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🩺 داشبورد"), KeyboardButton("📚 منابع")],
        [KeyboardButton("🎥 آرشیو"), KeyboardButton("🧪 بانک سوال")],
        [KeyboardButton("📅 برنامه"), KeyboardButton("📊 آمار من")],
        [KeyboardButton("🔔 اعلان‌ها"), KeyboardButton("🔍 جستجو")]
    ], resize_keyboard=True)


def admin_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🩺 داشبورد"), KeyboardButton("📚 منابع")],
        [KeyboardButton("🎥 آرشیو"), KeyboardButton("🧪 بانک سوال")],
        [KeyboardButton("📅 برنامه"), KeyboardButton("📊 آمار من")],
        [KeyboardButton("🔔 اعلان‌ها"), KeyboardButton("🔍 جستجو")],
        [KeyboardButton("👨‍⚕️ پنل ادمین")]
    ], resize_keyboard=True)


def back_btn(data):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data=data)]])


def cb(prefix, *parts):
    data = prefix + ':' + ':'.join(str(p) for p in parts)
    return data[:64]
