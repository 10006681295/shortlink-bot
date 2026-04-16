from pyrogram import Client, filters
import os
import random
import string
import time
import aiohttp
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram.errors import UserNotParticipant

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
GPLINK_API = os.getenv("GPLINK_API")
CHANNEL = os.getenv("CHANNEL_USERNAME")
BOT_USERNAME = os.getenv("BOT_USERNAME")

app = Client(
    "bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo["bot_db"]
tokens = db["tokens"]

EXPIRY = 43200

VIDEOS = {
    "movie": "BAACAgUAAxkBAAMDad3STtMT0Gk9a3TXB2iWk2h4b_YAAjkhAALhPfBWUiobOf1pWeIeBA"
}

def generate_token():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

async def shorten_link(url):
    try:
        api_url = f"https://gplinks.in/api?api={GPLINK_API}&url={url}"

        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                data = await response.json()

                if "shortenedUrl" in data:
                    return data["shortenedUrl"]

                return url
    except:
        return url

async def check_join(client, user_id):
    try:
        await client.get_chat_member(CHANNEL, user_id)
        return True
    except UserNotParticipant:
        return False
    except:
        return False

@app.on_message(filters.command("start"))
async def start_command(client, message):

    joined = await check_join(client, message.from_user.id)

    if not joined:
        await message.reply_text(
            f"🚫 पहले हमारा channel join करो:\n\nhttps://t.me/{CHANNEL}\n\nफिर /start भेजो"
        )
        return

    param = "movie"

    if len(message.command) > 1:
        param = message.command[1]

    file_id = VIDEOS.get(param)

    if not file_id:
        await message.reply_text("❌ Video not found")
        return

    token = generate_token()
    now = int(time.time())

    await tokens.insert_one({
        "user_id": message.from_user.id,
        "token": token,
        "created_at": now,
        "file_id": file_id
    })

    deep_link = f"https://t.me/{BOT_USERNAME}?start={token}"
    short_link = await shorten_link(deep_link)

    await message.reply_text(
        f"🔥 Download Unlock System 🔥\n\n"
        f"👉 Step 1: नीचे वाला link open करो\n\n"
        f"{short_link}\n\n"
        f"👉 Step 2: Token copy करो\n"
        f"👉 Step 3: Token यहाँ भेजो\n\n"
        f"⏳ Token Validity: 12 Hours\n"
        f"❌ Token सिर्फ 1 बार काम करेगा"
    )

@app.on_message(filters.video)
async def get_file_id(client, message):
    file_id = message.video.file_id
    await message.reply_text(f"FILE_ID:\n{file_id}")

@app.on_message(filters.text & ~filters.command(["start", "cleanup"]))
async def verify_token(client, message):

    joined = await check_join(client, message.from_user.id)

    if not joined:
        await message.reply_text(
            f"🚫 पहले channel join करो:\nhttps://t.me/{CHANNEL}"
        )
        return

    entered_token = message.text.strip()

    data = await tokens.find_one({
        "user_id": message.from_user.id,
        "token": entered_token
    })

    if not data:
        await message.reply_text("❌ Invalid / Expired / Already Used Token")
        return

    now = int(time.time())

    if now - data["created_at"] > EXPIRY:
        await tokens.delete_one({"_id": data["_id"]})
        await message.reply_text("⏰ Token expired! Use /start again")
        return

    await tokens.delete_one({"_id": data["_id"]})

    await message.reply_video(
        video=data["file_id"],
        caption="🎉 Access Granted!"
    )

@app.on_message(filters.command("cleanup"))
async def cleanup_command(client, message):
    owner_id = message.from_user.id

    if owner_id != 8529172721:
        return

    await tokens.delete_many({})
    await message.reply_text("✅ All tokens deleted")

app.run()
