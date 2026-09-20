import asyncio
from datetime import datetime
import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import pytz
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# ==================== خادم الويب المصغر لـ Render / Railway ====================
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Clock & Cleanup Bot is Live!")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

threading.Thread(target=run_web_server, daemon=True).start()

# ==================== إعدادات التوكن والقروب ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TARGET_CHAT_ID = int(os.environ.get("TARGET_CHAT_ID", -1002674296185))

TIMEZONE = 'Africa/Algiers'
SESSIONS_FILE = "sessions.json"

# قائمة مؤقتة لتخزين آيديات الرسائل المخالفة لحذفها كل 5 دقائق
PENDING_DELETIONS = []

# ----------------- حفظ واسترجاع الجلسات -----------------
def load_sessions():
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_sessions(sessions):
    with open(SESSIONS_FILE, "w") as f:
        json.dump(sessions, f, indent=4)

USER_SESSIONS = load_sessions()

# تعريف بوت التليجرام الرئيسي عبر aiogram
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# ----------------- مكتبة الزخرفات والأرقام الرومانية -----------------
def to_roman(num):
    val = [10, 9, 5, 4, 1]
    syb = ["X", "IX", "V", "IV", "I"]
    roman_num = ''
    i = 0
    while num > 0:
        for _ in range(num // val[i]):
            roman_num += syb[i]
            num -= val[i]
        i += 1
    return roman_num if roman_num else '0'

def format_time_roman(time_str):
    hours = int(time_str.split(':')[0])
    return to_roman(hours)

def get_fancy_time(time_str, style='bold'):
    if style == 'roman':
        return format_time_roman(time_str)
        
    styles = {
        'bold': {'0':'𝟬','1':'𝟭','2':'𝟮','3':'𝟯','4':'𝟰','5':'𝟱','6':'𝟲','7':'𝟳','8':'𝟴','9':'𝟵',':':':'},
        'script': {'0':'𝟣','1':'𝟤','2':'𝟥','3':'𝟦','4':'𝟧','5':'𝟨','6':'𝟩','7':'𝟪','8':'𝟫','9':'𝟢',':':':'},
        'double': {'0':'𝟘','1':'𝟙','2':'𝟚','3':'𝟛','4':'𝟜','5':'𝟝','6':'𝟞','7':'𝟟','8':'𝟠','9':'𝟡',':':':'},
        'circled_dark': {'0':'⓿','1':'❶','2':'❷','3':'❸','4':'❹','5':'❺','6':'❻','7':'❼','8':'❽','9':'❾',':':':'},
        'small': {'0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵','6':'⁶','7':'⁷','8':'⁸','9':'⁹',':':'’'}
    }
    
    mapping = styles.get(style, styles['bold'])
    return ''.join(mapping.get(char, char) for char in time_str)

# ----------------- لوحات الأزرار -----------------
def get_main_buttons(user_id):
    str_user_id = str(user_id)
    keyboard = [
        [types.InlineKeyboardButton(text="⚙️ حالة الخدمة", callback_data="status")],
        [types.InlineKeyboardButton(text="💬 المطور", url="https://t.me/Q_AWD")]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)

# ----------------- الأحداث والتحكم بالبوت -----------------
@dp.message(F.text == '/start')
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    msg = (
        "🥂 <b>مرحباً بك في بوت إدارة القروب والخدمات</b>\n\n"
        "البوت يعمل الآن بصلاحيات التوكن بنجاح!"
    )
    await message.answer(msg, reply_markup=get_main_buttons(user_id))

@dp.callback_query(F.data == "status")
async def status_callback(callback: types.CallbackQuery):
    await callback.answer("🟢 بوت العمل يعمل بتميز وبدون مشاكل!", show_alert=True)

# ----------------- مراقبة وتخزين الرسائل المخالفة -----------------
@dp.message(F.chat.id == TARGET_CHAT_ID)
async def monitor_messages(message: types.Message):
    should_delete = False

    # 1. فحص هل الرسالة صورة، فيديو، GIF، أو ملصق
    if message.photo or message.video or message.animation or message.sticker or message.document:
        should_delete = True

    # 2. فحص هل الرسالة تحتوي على إيموجي مخصص (Custom Emoji) عبر الـ entities
    if not should_delete and message.entities:
        for entity in message.entities:
            if entity.type == "custom_emoji":
                should_delete = True
                break

    # 3. إذا كانت مخالفة، أضفها إلى قائمة الانتظار للحذف بعد 5 دقائق
    if should_delete:
        PENDING_DELETIONS.append({
            'chat_id': message.chat.id,
            'message_id': message.message_id
        })

# ----------------- مهمة الحذف الدوري كل 5 دقائق -----------------
async def periodic_cleanup_task():
    while True:
        await asyncio.sleep(300) # الانتظار 300 ثانية (5 دقائق)
        if PENDING_DELETIONS:
            print(f"🧹 جاري تنفيذ الحذف الدوري لـ {len(PENDING_DELETIONS)} رسالة...")
            items_to_delete = list(PENDING_DELETIONS)
            PENDING_DELETIONS.clear()

            for item in items_to_delete:
                try:
                    await bot.delete_message(chat_id=item['chat_id'], message_id=item['message_id'])
                    await asyncio.sleep(0.5) # فاصل زمني بسيط لتجنب حظر السيرفر
                except Exception as e:
                    print(f"فشل حذف الرسالة {item['message_id']}: {e}")

async def main():
    # حذف أي رسائل معلقة قديمة للبوت قبل البدء
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(periodic_cleanup_task())
    print("🚀 البوت يعمل الآن بنجاح وبدون API_ID نهائياً!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
if __name__ == '__main__':
    asyncio.main() if hasattr(asyncio, 'main') else asyncio.run(main())
