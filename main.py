import asyncio
from datetime import datetime
import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import pytz
from telethon import TelegramClient, events, Button, functions
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PasswordHashInvalidError
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument

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

# ==================== إعدادات المطور وحماية المفاتيح ====================
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# معرف القروب المستهدف (تأكد أن البوت مشرف فيه)
TARGET_CHAT_ID = int(os.environ.get("TARGET_CHAT_ID", -1000000000000))

TIMEZONE = 'Africa/Algiers'
SESSIONS_FILE = "sessions.json"
LOGIN_STATES = {}

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

# تعريف بوت التليجرام الرئيسي
bot = TelegramClient('maker_bot_session', API_ID, API_HASH)

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
    if str_user_id in USER_SESSIONS:
        return [
            [Button.inline("✦ تغيير نمط الزخرفة", data="change_style")],
            [Button.inline("⚙️ حالة الخدمة", data="status"), Button.inline("✖ إيقاف التفعيل", data="stop_service")],
            [Button.url("💬 المطور", "https://t.me/Q_AWD")]
        ]
    else:
        return [
            [Button.inline("📱 التفعيل عبر رقم الهاتف", data="start_login")],
            [Button.inline("🔗 إدخال جلسة دائمية مباشرة", data="start_string_session")],
            [Button.inline("⚙️ حالة الخدمة", data="status")],
            [Button.url("💬 المطور", "https://t.me/Q_AWD")]
        ]

def get_style_buttons():
    return [
        [Button.inline("✦ عريض (𝟭𝟮:𝟯𝡳)", data="set_style_bold"), Button.inline("✦ روماني (XII)", data="set_style_roman")],
        [Button.inline("✦ مائل (𝟣𝟤:𝟥𝟩)", data="set_style_script"), Button.inline("✦ مفرغ (𝟙𝟚:𝟛𝟟)", data="set_style_double")],
        [Button.inline("✦ دوائر (❶❷:❸❼)", data="set_style_circled_dark"), Button.inline("✦ صغير (¹²:³⁷)", data="set_style_small")],
        [Button.inline("↩ العودة للقائمة الرئيسية", data="main_menu")]
    ]

# ----------------- الأحداث والتحكم بالبوت -----------------
@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    user_id = event.sender_id
    msg = (
        "<tg-emoji emoji-id='5967688845397855939'>🥂</tg-emoji> <b>مرحباً بك في بوت الساعة الذكية والزخرفة والحذف الدوري</b>\n\n"
        "اختر طريقة التفعيل المناسبة لك:"
    )
    await event.respond(msg, buttons=get_main_buttons(user_id), parse_mode='html')

@bot.on(events.CallbackQuery)
async def callback_handler(event):
    data = event.data.decode('utf-8')
    user_id = event.sender_id
    str_user_id = str(user_id)

    if data == "main_menu":
        msg = "<tg-emoji emoji-id='5778332271417236782'>🕑</tg-emoji> <b>القائمة الرئيسية:</b>"
        await event.edit(msg, buttons=get_main_buttons(user_id), parse_mode='html')

    elif data == "start_login":
        LOGIN_STATES[user_id] = {"step": "WAITING_PHONE"}
        await event.respond("📱 <b>يرجى إرسال رقم هاتفك مع المفتاح الدولي:</b>\n\nمثال: <code>+21379679xxxx</code>", parse_mode='html')

    elif data == "start_string_session":
        LOGIN_STATES[user_id] = {"step": "WAITING_STRING_SESSION"}
        await event.respond("🔗 <b>يرجى إرسال كود الجلسة الدائمة (StringSession) الخاص بك:</b>", parse_mode='html')

    elif data == "change_style":
        if str_user_id not in USER_SESSIONS:
            await event.answer("⚠️ يجب عليك تفعيل الخدمة أولاً!", alert=True)
            return
        msg = "<tg-emoji emoji-id='5346324283029234202'>🙂</tg-emoji> <b>اختر نمط الزخرفة المفضل لديك:</b>"
        await event.edit(msg, buttons=get_style_buttons(), parse_mode='html')

    elif data.startswith("set_style_"):
        style_name = data.replace("set_style_", "")
        if str_user_id in USER_SESSIONS:
            USER_SESSIONS[str_user_id]['style'] = style_name
            save_sessions(USER_SESSIONS)
            await event.answer("✅ تم تغيير نمط الزخرفة بنجاح!", alert=True)
            msg = "<tg-emoji emoji-id='5422482011761690406'>🤩</tg-emoji> <b>تم تحديث الزخرفة بنجاح!</b>"
            await event.edit(msg, buttons=get_main_buttons(user_id), parse_mode='html')

    elif data == "status":
        if str_user_id in USER_SESSIONS:
            style = USER_SESSIONS[str_user_id].get('style', 'bold')
            await event.answer(f"🟢 الخدمة مفعلة!\nالنمط الحالي: {style}", alert=True)
        else:
            await event.answer("🔴 الخدمة غير مفعلة في حسابك حالياً.", alert=True)

    elif data == "stop_service":
        if str_user_id in USER_SESSIONS:
            del USER_SESSIONS[str_user_id]
            save_sessions(USER_SESSIONS)
            await event.answer("✅ تم إيقاف الخدمة بنجاح.", alert=True)
            msg = "<tg-emoji emoji-id='6163649769114702709'>🤩</tg-emoji> <b>تم إيقاف الخدمة وإزالة الجلسة.</b>"
            await event.edit(msg, buttons=get_main_buttons(user_id), parse_mode='html')

@bot.on(events.NewMessage)
async def message_handler(event):
    if event.is_private and event.text and event.text.startswith('/'):
        return

    user_id = event.sender_id
    str_user_id = str(user_id)
    state = LOGIN_STATES.get(user_id)

    if not state:
        return

    if state["step"] == "WAITING_STRING_SESSION":
        session_str = event.text.strip()
        try:
            test_client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
            await test_client.connect()
            if not await test_client.is_user_authorized():
                await event.respond("❌ <b>الجلسة غير صالحة أو منتهية الصلاحية.</b> أعد المحاولة عبر /start", parse_mode='html')
                await test_client.disconnect()
                LOGIN_STATES.pop(user_id, None)
                return
            
            await test_client.disconnect()
            USER_SESSIONS[str_user_id] = {
                "session": session_str,
                "style": "bold"
            }
            save_sessions(USER_SESSIONS)
            LOGIN_STATES.pop(user_id, None)
            
            await event.respond("🎉 <b>تم حفظ وتخزين الجلسة الدائمة بنجاح!</b>", buttons=get_main_buttons(user_id), parse_mode='html')
        except Exception as e:
            await event.respond(f"❌ <b>حدث خطأ أثناء التحقق من الجلسة:</b> {e}\nأعد المحاولة عبر /start", parse_mode='html')
            LOGIN_STATES.pop(user_id, None)

    elif state["step"] == "WAITING_PHONE":
        phone = event.text.strip()
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()
        
        try:
            code_request = await client.send_code_request(phone)
            LOGIN_STATES[user_id] = {
                "step": "WAITING_CODE",
                "phone": phone,
                "client": client,
                "phone_code_hash": code_request.phone_code_hash
            }
            await event.respond("📩 <b>تم إرسال رمز التأكيد إلى حسابك في تيليجرام.</b>\n\nيرجى إرسال الرمز هنا:", parse_mode='html')
        except Exception as e:
            await event.respond(f"❌ <b>حدث خطأ:</b> {e}\nأعد المحاولة عبر /start", parse_mode='html')
            LOGIN_STATES.pop(user_id, None)

    elif state["step"] == "WAITING_CODE":
        code = event.text.strip().replace(" ", "").replace("-", "")
        client = state["client"]
        phone = state["phone"]
        phone_code_hash = state["phone_code_hash"]

        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            session_str = client.session.save()
            USER_SESSIONS[str_user_id] = {
                "session": session_str,
                "style": "bold"
            }
            save_sessions(USER_SESSIONS)
            await client.disconnect()
            LOGIN_STATES.pop(user_id, None)
            
            await event.respond("🎉 <b>تم ربط وحفظ حسابك بنجاح!</b>", buttons=get_main_buttons(user_id), parse_mode='html')
            
        except SessionPasswordNeededError:
            LOGIN_STATES[user_id]["step"] = "WAITING_PASSWORD"
            await event.respond("🔐 <b>حسابك محمي بكلمة سر (التحقق بخطوتين - 2FA).</b>\n\nيرجى إرسال كلمة السر الخاصة بك الآن:", parse_mode='html')
            
        except PhoneCodeInvalidError:
            await event.respond("❌ <b>الرمز غير صحيح.</b> أعد التأكد وأرسله مجدداً.")
            
        except Exception as e:
            await event.respond(f"❌ <b>حدث خطأ:</b> {e}")
            LOGIN_STATES.pop(user_id, None)

    elif state["step"] == "WAITING_PASSWORD":
        password = event.text.strip()
        client = state["client"]

        try:
            await client.sign_in(password=password)
            session_str = client.session.save()
            USER_SESSIONS[str_user_id] = {
                "session": session_str,
                "style": "bold"
            }
            save_sessions(USER_SESSIONS)
            await client.disconnect()
            LOGIN_STATES.pop(user_id, None)
            
            await event.respond("🎉 <b>تم ربط وحفظ حسابك بنجاح بعد التحقق من كلمة السر!</b>", buttons=get_main_buttons(user_id), parse_mode='html')
            
        except PasswordHashInvalidError:
            await event.respond("❌ <b>كلمة السر خاطئة!</b> يرجى إرسال كلمة السر الصحيحة:")
        except Exception as e:
            await event.respond(f"❌ <b>حدث خطأ:</b> {e}")
            LOGIN_STATES.pop(user_id, None)

# ----------------- مهمة الخلفية لتحديث الساعة -----------------
async def update_all_users_clock():
    while True:
        if USER_SESSIONS:
            tz = pytz.timezone(TIMEZONE)
            current_time = datetime.now(tz).strftime("%H:%M")

            for user_id, data in list(USER_SESSIONS.items()):
                try:
                    style = data.get("style", "bold")
                    formatted_time = get_fancy_time(current_time, style=style)

                    user_client = TelegramClient(StringSession(data["session"]), API_ID, API_HASH)
                    await user_client.connect()
                    
                    me = await user_client.get_me()
                    await user_client(functions.account.UpdateProfileRequest(
                        first_name=me.first_name,
                        last_name=formatted_time
                    ))
                    await user_client.disconnect()
                    print(f"✅ تم تحديث حساب {user_id} بنجاح إلى: {formatted_time}")
                except Exception as e:
                    print(f"❌ خطأ في تحديث حساب {user_id}: {e}")

        await asyncio.sleep(60)

# ----------------- مراقبة وتخزين الرسائل المخالفة -----------------
@bot.on(events.NewMessage(chats=TARGET_CHAT_ID))
async def monitor_messages(event):
    message = event.message
    should_delete = False

    # 1. فحص هل الرسالة صورة، فيديو، GIF، أو ملصق
    if message.media:
        if isinstance(message.media, MessageMediaPhoto):
            should_delete = True
        elif isinstance(message.media, MessageMediaDocument):
            doc = message.media.document
            if message.sticker:
                should_delete = True
            else:
                for attr in doc.attributes:
                    if type(attr).__name__ in ['DocumentAttributeAnimated', 'DocumentAttributeVideo']:
                        should_delete = True
                        break

    # 2. فحص هل الرسالة تحتوي على إيموجي مخصص (Custom Emoji)
    if not should_delete and message.entities:
        for entity in message.entities:
            if hasattr(entity, 'document_id'):
                should_delete = True
                break

    # 3. إذا كانت مخالفة، أضفها إلى قائمة الانتظار للحذف بعد 5 دقائق
    if should_delete:
        PENDING_DELETIONS.append({
            'chat_id': event.chat_id,
            'message_id': message.id
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
                    await bot.delete_messages(item['chat_id'], item['message_id'])
                    await asyncio.sleep(0.5) # فاصل زمني بسيط لتجنب حظر السيرفر
                except Exception as e:
                    print(f"فشل حذف الرسالة {item['message_id']}: {e}")

async def main():
    await bot.start(bot_token=BOT_TOKEN)
    asyncio.create_task(update_all_users_clock())
    asyncio.create_task(periodic_cleanup_task())
    print("🚀 البوت يراقب القروب ويجمع الرسائل ليقوم بحذفها كل 5 دقائق تماماً!")
    await bot.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
