import os
import random
import string
import time
import aiohttp
import qrcode
from io import BytesIO
from pyrogram import Client, filters
from pyrogram.errors import UserNotParticipant
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient

# --- 1. CONFIGURATION (Pehle Variables) ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
GPLINK_API = os.getenv("GPLINK_API")
CHANNEL = os.getenv("CHANNEL_USERNAME")
BOT_USERNAME = "Memestorehubbot"
OWNER_ID = int(os.getenv("OWNER_ID", "1853401283"))
UPI_ID = os.getenv("UPI_ID")

CHANNEL_LINK = CHANNEL.replace("@", "")

# --- 2. INITIALIZE APP (Ye line handlers se upar honi chahiye) ---
app = Client(
    "bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# --- 3. DATABASE SETUP ---
mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo["bot_db"]

tokens = db["tokens"]
videos = db["videos"]
premium_users = db["premium_users"]
payments = db["payments"]

EXPIRY = 43200  # 12 Hours
batch_files = []

PLANS = {
    "7d": {"days": 7, "price": 19},
    "15d": {"days": 15, "price": 29},
    "30d": {"days": 30, "price": 39},
    "100d": {"days": 100, "price": 99}
}

# --- 4. HELPERS ---
def generate_token():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

async def shorten_link(url):
    try:
        api_url = f"https://gplinks.in/api?api={GPLINK_API}&url={url}"
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                data = await response.json()
                return data.get("shortenedUrl", url)
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

# --- 5. HANDLERS (Ab shuru honge saare @app.on_message) ---

@app.on_message(filters.command("start"))
async def start_command(client, message):
    joined = await check_join(client, message.from_user.id)
    if not joined:
        await message.reply_text(f"🚫 पहले channel join करो:\n\nhttps://t.me/{CHANNEL_LINK}")
        return

    if len(message.command) < 2:
        await message.reply_photo(
            photo="https://i.ibb.co/8D0X0Q7/sample.jpg",
            caption=f"⚡ Hey, {message.from_user.first_name} ~\n›› Verify token for access or get Premium.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("• GET PREMIUM •", callback_data="premium_menu")],
                [InlineKeyboardButton("• HOW TO VERIFY •", callback_data="how_verify")]
            ])
        )
        return

    param = message.command[1]

    # --- TOKEN VERIFICATION (User return from Ad) ---
    if param.startswith("verify_"):
        token_val = param.replace("verify_", "")
        token_data = await tokens.find_one({"user_id": message.from_user.id, "token": token_val, "is_verified": False})

        if not token_data:
            await message.reply_text("❌ Invalid or Expired link! Get a new one.")
            return

        now = int(time.time())
        await tokens.update_one({"_id": token_data["_id"]}, {"$set": {"is_verified": True, "verified_at": now}})
        
        video_data = token_data["file_data"]
        caption = "🎉 Access Granted! (Valid for 12 Hours)"
        if video_data.get("type") == "batch":
            for file_id in video_data["file_ids"]:
                await message.reply_video(video=file_id, caption=caption)
        else:
            await message.reply_video(video=video_data["file_id"], caption=caption)
        return

    # --- VIDEO & PREMIUM & AD LOGIC ---
    video_data = await videos.find_one({"name": param})
    if not video_data:
        await message.reply_text("❌ Video not found")
        return

    # Premium Check
    premium_data = await premium_users.find_one({"user_id": message.from_user.id})
    if premium_data and premium_data["expiry"] > int(time.time()):
        if video_data.get("type") == "batch":
            for f_id in video_data["file_ids"]: await message.reply_video(video=f_id, caption="💎 Premium Access")
        else:
            await message.reply_video(video=video_data["file_id"], caption="💎 Premium Access")
        return

    # 12-Hour Verification Check
    last_verify = await tokens.find_one({"user_id": message.from_user.id, "is_verified": True, "verified_at": {"$gt": int(time.time()) - EXPIRY}})
    if last_verify:
        if video_data.get("type") == "batch":
            for f_id in video_data["file_ids"]: await message.reply_video(video=f_id, caption="✅ Verified Access")
        else:
            await message.reply_video(video=video_data["file_id"], caption="✅ Verified Access")
        return

    # Generate Ad Link
    token = generate_token()
    await tokens.insert_one({"user_id": message.from_user.id, "token": token, "created_at": int(time.time()), "is_verified": False, "file_data": video_data})
    short_link = await shorten_link(f"https://t.me/{BOT_USERNAME}?start=verify_{token}")

    await message.reply_text(
        "🔥 **Access Locked** 🔥\n\nVerify karke video unlock karein.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 CLICK TO VERIFY (AD) 🚀", url=short_link)],
            [InlineKeyboardButton("💎 GET PREMIUM (NO ADS) 💎", callback_data="premium_menu")]
        ])
    )

@app.on_callback_query()
async def callback_handler(client, callback_query):
    data = callback_query.data
    if data == "premium_menu":
        await callback_query.message.reply_text("💎 **Premium Plans**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"{v['days']} Days - ₹{v['price']}", callback_data=f"buy_{k}")] for k, v in PLANS.items()]))
    elif data.startswith("buy_"):
        plan = PLANS[data.replace("buy_", "")]
        p_id = generate_token()
        upi = f"upi://pay?pa={UPI_ID}&pn=Premium&am={plan['price']}&cu=INR&tn={p_id}"
        qr = qrcode.make(upi); bio = BytesIO(); bio.name = "p.png"; qr.save(bio, "PNG"); bio.seek(0)
        await payments.insert_one({"user_id": callback_query.from_user.id, "payment_id": p_id, "days": plan["days"], "status": "pending"})
        await callback_query.message.reply_photo(photo=bio, caption=f"Plan: {plan['days']} Days\nPrice: ₹{plan['price']}\n\nPay & send: `/verify {p_id} UTR`")
    await callback_query.answer()

@app.on_message(filters.command("verify"))
async def verify_payment(client, message):
    if len(message.command) < 3: return
    p_id, utr = message.command[1], message.command[2]
    pay = await payments.find_one({"payment_id": p_id, "user_id": message.from_user.id})
    if pay:
        await client.send_message(OWNER_ID, f"💰 Payment!\nUID: {message.from_user.id}\nUTR: {utr}\n`/approve {message.from_user.id} {pay['days']}`")
        await message.reply_text("✅ Approved pending!")

@app.on_message(filters.command("approve"))
async def approve_premium(client, message):
    if message.from_user.id != OWNER_ID: return
    u_id, days = int(message.command[1]), int(message.command[2])
    exp = int(time.time()) + (days * 86400)
    await premium_users.update_one({"user_id": u_id}, {"$set": {"expiry": exp}}, upsert=True)
    await client.send_message(u_id, "🎉 Premium Activated!")

@app.on_message((filters.video | filters.document) & filters.private)
async def save_video(client, message):
    if message.from_user.id != OWNER_ID: return
    f_id = message.video.file_id if message.video else message.document.file_id
    app.file_id_temp = f_id
    batch_files.append(f_id)
    await message.reply_text(f"✅ Added ({len(batch_files)})")

@app.on_message(filters.command("add"))
async def add_video(client, message):
    if message.from_user.id != OWNER_ID or len(message.command) < 2: return
    await videos.update_one({"name": message.command[1].lower()}, {"$set": {"file_id": app.file_id_temp, "type": "single"}}, upsert=True)
    await message.reply_text("✅ Saved!")

@app.on_message(filters.command("addbatch"))
async def add_batch(client, message):
    if message.from_user.id != OWNER_ID or not batch_files: return
    await videos.update_one({"name": message.command[1].lower()}, {"$set": {"file_ids": list(batch_files), "type": "batch"}}, upsert=True)
    batch_files.clear()
    await message.reply_text("✅ Batch Saved!")

@app.on_message(filters.command("cleanup"))
async def cleanup_command(client, message):
    if message.from_user.id == OWNER_ID:
        await tokens.delete_many({})
        await message.reply_text("✅ Cleaned!")

if __name__ == "__main__":
    app.run()
