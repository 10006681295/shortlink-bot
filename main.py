from pyrogram import Client, filters
import os, random, string, time
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram.errors import UserNotParticipant
import aiohttp

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
GPLINK_API = os.getenv("GPLINK_API")
CHANNEL = os.getenv("CHANNEL_USERNAME")

app = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo["bot"]
tokens = db["tokens"]

EXPIRY = 43200

def generate_token():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

async def shorten_link(url):
    api_url = f"https://gplinks.in/api?api={GPLINK_API}&url={url}"
    async with aiohttp.ClientSession() as session:
        async with session.get(api_url) as res:
            data = await res.json()
            return data["shortenedUrl"]

async def check_join(client, user_id):
    try:
        await client.get_chat_member(CHANNEL, user_id)
        return True
    except UserNotParticipant:
        return False

@app.on_message(filters.command("start"))
async def start(client, message):

    joined = await check_join(client, message.from_user.id)
    if not joined:
        await message.reply_text(f"🚫 पहले join करो:\nhttps://t.me/{CHANNEL}")
        return

    param = message.command[1] if len(message.command) > 1 else "default"

    token = generate_token()
    now = int(time.time())

    await tokens.insert_one({
        "user_id": message.from_user.id,
        "token": token,
        "created_at": now
    })

    deep_link = f"https://t.me/{message.bot.username}?start={token}"
    short_link = await shorten_link(deep_link)

    await message.reply_text(
        f"🔗 Link complete करो:\n{short_link}\n\n⏳ 12 घंटे valid\n\nToken भेजो"
    )

@app.on_message(filters.text)
async def verify(client, message):

    data = await tokens.find_one({
        "user_id": message.from_user.id,
        "token": message.text.strip()
    })

    if data:
        now = int(time.time())

        if now - data["created_at"] > EXPIRY:
            await tokens.delete_one({"_id": data["_id"]})
            await message.reply_text("⏰ Expired")
        else:
            await tokens.delete_one({"_id": data["_id"]})

            await message.reply_video(
                video="https://www.w3schools.com/html/mov_bbb.mp4",
                caption="🎉 Access Granted!"
            )
    else:
        await message.reply_text("❌ Invalid / Used token")

app.run()
