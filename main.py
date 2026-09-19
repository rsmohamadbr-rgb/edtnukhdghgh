import asyncio
import datetime
import os

from telethon import TelegramClient
from telethon.tl.functions.account import UpdateProfileRequest

# قراءة المتغيرات من البيئة (Railway) مع وضع القيم الافتراضية تلقائياً
API_ID = int(os.environ.get("API_ID", 25531882))
API_HASH = os.environ.get("API_HASH", "1357697ae77bb729fb1b788a1add000e")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8735176234:AAH2XvvQD1knprH44HRyE64533CSusK6pIo")
BASE_NAME = os.environ.get("BASE_NAME", "ZAD nvr run")

SESSION_NAME = "session_name"

# إنشاء العميل باستخدام توكن البوت
if BOT_TOKEN:
    client = TelegramClient(SESSION_NAME, api_id=6, api_hash="eb06d4abfb49dc3eeb1aeb98ae0f581e").start(bot_token=BOT_TOKEN)
else:
    client = TelegramClient(
        SESSION_NAME,
        API_ID,
        API_HASH
    )

def to_fancy_digits(text):
    normal_digits = "0123456789"
    fancy_digits = "𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵"
    digits_map = str.maketrans(
        normal_digits,
        fancy_digits
    )
    return str(text).translate(digits_map)

async def update_time_name():
    if not client.is_connected():
        await client.start()

    print("doooone")
    print("started")

    last_time = ""

    while True:
        try:
            raw_time = datetime.datetime.now().strftime("%H:%M")
            fancy_time = to_fancy_digits(raw_time)

            if fancy_time != last_time:
                new_name = f"{BASE_NAME} {fancy_time}"

                await client(
                    UpdateProfileRequest(
                        first_name=new_name
                    )
                )

                last_time = fancy_time
                print(f"✅ the name secces: {new_name}")

            await asyncio.sleep(30)

        except Exception as e:
            print(f"❌ false: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(update_time_name())
