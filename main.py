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
BOT_USERNAME = os.getenv("BOT_USERNAME", "Memestorehubbot")
OWNER_ID = int(os.getenv("OWNER_ID", "1853401283"))

app = Client(
    "bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo["bot_db"]

tokens = db["tokens"]
videos = db["videos"]

EXPIRY = 43200
batch_files = []

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

    if len(message.command) < 2:
        await message.reply_text("❌ Invalid link")
        return

    param = message.command[1]

    video_data = await videos.find_one({"name": param})

    if not video_data:
        await message.reply_text("❌ Video not found")
        return

    token = generate_token()
    now = int(time.time())

    await tokens.insert_one({
        "user_id": message.from_user.id,
        "token": token,
        "created_at": now,
        "file_data": video_data
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

@app.on_message((filters.video | filters.document) & filters.private)
async def save_video(client, message):

    global batch_files

    if message.from_user.id != OWNER_ID:
        return

    if message.video:
        file_id = message.video.file_id
    elif message.document:
        file_id = message.document.file_id
    else:
        return

    app.file_id_temp = file_id
    batch_files.append(file_id)

    await message.reply_text(
        f"✅ Video added\n\n"
        f"Batch size: {len(batch_files)}\n\n"
        f"Single save:\n/add movie1\n\n"
        f"Batch save:\n/addbatch series1"
    )

@app.on_message(filters.command("add"))
async def add_video(client, message):

    if message.from_user.id != OWNER_ID:
        return

    if len(message.command) < 2:
        await message.reply_text("Usage:\n/add movie1")
        return

    if not hasattr(app, "file_id_temp"):
        await message.reply_text("❌ पहले video भेजो")
        return

    name = message.command[1].lower()

    existing = await videos.find_one({"name": name})

    if existing:
        await videos.delete_one({"name": name})

    await videos.insert_one({
        "name": name,
        "file_id": app.file_id_temp,
        "type": "single"
    })

    link = f"https://t.me/{BOT_USERNAME}?start={name}"

    await message.reply_text(
        f"✅ Single video saved\n\n"
        f"Name: {name}\n\n"
        f"Link:\n{link}"
    )

@app.on_message(filters.command("addbatch"))
async def add_batch(client, message):

    global batch_files

    if message.from_user.id != OWNER_ID:
        return

    if len(message.command) < 2:
        await message.reply_text("Usage:\n/addbatch series1")
        return

    if len(batch_files) == 0:
        await message.reply_text("❌ पहले videos भेजो")
        return

    name = message.command[1].lower()

    existing = await videos.find_one({"name": name})

    if existing:
        await videos.delete_one({"name": name})

    await videos.insert_one({
        "name": name,
        "file_ids": batch_files,
        "type": "batch"
    })

    link = f"https://t.me/{BOT_USERNAME}?start={name}"

    await message.reply_text(
        f"✅ Batch saved successfully\n\n"
        f"Videos: {len(batch_files)}\n\n"
        f"Link:\n{link}"
    )

    batch_files = []

@app.on_message(filters.command("list"))
async def list_videos(client, message):

    if message.from_user.id != OWNER_ID:
        return

    text = "📂 Saved Videos:\n\n"

    async for video in videos.find():
        text += f"{video['name']}\nhttps://t.me/{BOT_USERNAME}?start={video['name']}\n\n"

    await message.reply_text(text)

@app.on_message(filters.command("delete"))
async def delete_video(client, message):

    if message.from_user.id != OWNER_ID:
        return

    if len(message.command) < 2:
        await message.reply_text("Usage:\n/delete movie1")
        return

    name = message.command[1].lower()

    result = await videos.delete_one({"name": name})

    if result.deleted_count > 0:
        await message.reply_text("✅ Deleted successfully")
    else:
        await message.reply_text("❌ Video not found")

@app.on_message(filters.command("cleanup"))
async def cleanup_command(client, message):

    if message.from_user.id != OWNER_ID:
        return

    await tokens.delete_many({})
    await message.reply_text("✅ All tokens deleted")

@app.on_message(filters.text)
async def verify_token(client, message):

    blocked_commands = [
        "/start",
        "/add",
        "/addbatch",
        "/list",
        "/delete",
        "/cleanup"
    ]

    for cmd in blocked_commands:
        if message.text.startswith(cmd):
            return

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
        await message.reply_text("⏰ Token expired! Use link again")
        return

    await tokens.delete_one({"_id": data["_id"]})

    video_data = data["file_data"]

    if video_data.get("type") == "batch":
        for file_id in video_data["file_ids"]:
            await message.reply_video(
                video=file_id,
                caption="🎉 Access Granted!"
            )
    else:
        await message.reply_video(
            video=video_data["file_id"],
            caption="🎉 Access Granted!"
        )

app.run()
