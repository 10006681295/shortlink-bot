from pyrogram import Client, filters
from pyrogram.errors import UserNotParticipant
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient
import os
import random
import string
import time
import aiohttp
import qrcode
from io import BytesIO

# --- CONFIGURATION ---
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

app = Client(
    "bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# --- DATABASE SETUP ---
mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo["bot_db"]

tokens = db["tokens"]
videos = db["videos"]
premium_users = db["premium_users"]
payments = db["payments"]

EXPIRY = 43200 # 12 Hours
batch_files = []

PLANS = {
    "7d": {"days": 7, "price": 19},
    "15d": {"days": 15, "price": 29},
    "30d": {"days": 30, "price": 39},
    "100d": {"days": 100, "price": 99}
}

# --- HELPERS ---
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

# --- MAIN COMMANDS ---
@app.on_message(filters.command("start"))
async def start_command(client, message):
    joined = await check_join(client, message.from_user.id)
    if not joined:
        await message.reply_text(f"🚫 पहले channel join करो:\n\nhttps://t.me/{CHANNEL_LINK}")
        return

    if len(message.command) < 2:
        await message.reply_photo(
            photo="https://i.ibb.co/8D0X0Q7/sample.jpg",
            caption=(
                f"⚡ Hey, {message.from_user.first_name} ~\n\n"
                f"›› YOU NEED TO VERIFY A TOKEN TO GET FREE ACCESS\n\n"
                f"›› PREMIUM USERS GET DIRECT ACCESS\n\n"
                f"💸 REFER AND EARN FREE PREMIUM"
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("• GET PREMIUM •", callback_data="premium_menu")],
                [InlineKeyboardButton("• REFER AND EARN •", callback_data="refer_menu")],
                [InlineKeyboardButton("• HOW TO VERIFY •", callback_data="how_verify")]
            ])
        )
        return

    param = message.command[1]

    # --- 1. TOKEN VERIFICATION PROCESS ---
    if param.startswith("verify_"):
        token_val = param.replace("verify_", "")
        token_data = await tokens.find_one({"user_id": message.from_user.id, "token": token_val})

        if not token_data:
            await message.reply_text("❌ Invalid or Expired link!")
            return

        now = int(time.time())
        if now - token_data["created_at"] > EXPIRY:
            await tokens.delete_one({"_id": token_data["_id"]})
            await message.reply_text("⏰ Token expired! Please try again.")
            return

        # Mark as verified in DB
        await tokens.update_one({"_id": token_data["_id"]}, {"$set": {"is_verified": True}})
        
        video_data = token_data["file_data"]
        caption = "🎉 Access Granted! (Valid for 12 Hours)"
        
        if video_data.get("type") == "batch":
            for file_id in video_data["file_ids"]:
                await message.reply_video(video=file_id, caption=caption)
        else:
            await message.reply_video(video=video_data["file_id"], caption=caption)
        return

    # --- 2. VIDEO EXISTENCE CHECK ---
    video_data = await videos.find_one({"name": param})
    if not video_data:
        await message.reply_text("❌ Video not found")
        return

    # --- 3. PREMIUM ACCESS CHECK ---
    premium_data = await premium_users.find_one({"user_id": message.from_user.id})
    if premium_data:
        if premium_data["expiry"] > int(time.time()):
            caption = "💎 Premium Access"
            if video_data.get("type") == "batch":
                for file_id in video_data["file_ids"]:
                    await message.reply_video(video=file_id, caption=caption)
            else:
                await message.reply_video(video=video_data["file_id"], caption=caption)
            return
        else:
            await premium_users.delete_one({"user_id": message.from_user.id})

    # --- 4. ALREADY VERIFIED CHECK (Prevent Loss) ---
    # Check if user verified ANY token in the last 12 hours
    is_already_verified = await tokens.find_one({
        "user_id": message.from_user.id,
        "is_verified": True,
        "created_at": {"$gt": int(time.time()) - EXPIRY}
    })

    if is_already_verified:
        if video_data.get("type") == "batch":
            for file_id in video_data["file_ids"]:
                await message.reply_video(video=file_id, caption="✅ Verified Access")
        else:
            await message.reply_video(video=video_data["file_id"], caption="✅ Verified Access")
        return

    # --- 5. GENERATE AD LINK ---
    token = generate_token()
    await tokens.insert_one({
        "user_id": message.from_user.id,
        "token": token,
        "created_at": int(time.time()),
        "file_data": video_data,
        "is_verified": False
    })

    deep_link = f"https://t.me/{BOT_USERNAME}?start=verify_{token}"
    short_link = await shorten_link(deep_link)

    await message.reply_text(
        f"🔥 **Download Unlock System** 🔥\n\n"
        f"👉 नीचे button पर click karke verify karein\n\n"
        f"⏳ **Token Validity:** 12 Hours\n"
        f"💎 Premium users ko ads nahi dikhte.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("• VERIFY NOW (AD) •", url=short_link)],
            [InlineKeyboardButton("• GET PREMIUM •", callback_data="premium_menu")]
        ])
    )

# --- CALLBACK HANDLERS ---
@app.on_callback_query()
async def callback_handler(client, callback_query):
    data = callback_query.data

    if data == "premium_menu":
        await callback_query.message.reply_text(
            "💎 **Choose Your Premium Plan**",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("7 Days - ₹19", callback_data="buy_7d")],
                [InlineKeyboardButton("15 Days - ₹29", callback_data="buy_15d")],
                [InlineKeyboardButton("30 Days - ₹39", callback_data="buy_30d")],
                [InlineKeyboardButton("100 Days - ₹99", callback_data="buy_100d")]
            ])
        )
    elif data.startswith("buy_"):
        plan_key = data.replace("buy_", "")
        plan = PLANS[plan_key]
        payment_id = generate_token()
        upi_link = f"upi://pay?pa={UPI_ID}&pn=PremiumAccess&am={plan['price']}&cu=INR&tn={payment_id}"
        
        qr = qrcode.make(upi_link)
        bio = BytesIO()
        bio.name = "payment.png"
        qr.save(bio, "PNG")
        bio.seek(0)

        await payments.insert_one({
            "user_id": callback_query.from_user.id,
            "payment_id": payment_id,
            "plan": plan_key,
            "days": plan["days"],
            "amount": plan["price"],
            "status": "pending",
            "created_at": int(time.time())
        })

        await callback_query.message.reply_photo(
            photo=bio,
            caption=(
                f"💎 **Premium Plan Request**\n\n"
                f"Plan: {plan['days']} Days\n"
                f"Amount: ₹{plan['price']}\n\n"
                f"QR scan karke payment karein.\n"
                f"Uske baad ye command bhejein:\n"
                f"`/verify {payment_id} YOUR_UTR`"
            )
        )
    elif data == "refer_menu":
        await callback_query.message.reply_text(f"💸 **Refer And Earn**\n\nApne dosto ko bot share karein:\nhttps://t.me/{BOT_USERNAME}")
    elif data == "how_verify":
        await callback_query.message.reply_text("1. Link open karein\n2. Ads complete karein\n3. Start button dabayein\n4. Video mil jayega!")
    
    await callback_query.answer()

# --- ADMIN & PAYMENT COMMANDS ---
@app.on_message(filters.command("verify"))
async def verify_payment(client, message):
    if len(message.command) < 3:
        await message.reply_text("Usage: `/verify PAYMENT_ID UTR`")
        return
    payment_id, utr = message.command[1], message.command[2]
    payment = await payments.find_one({"payment_id": payment_id, "user_id": message.from_user.id})
    if not payment:
        await message.reply_text("❌ Payment record not found!")
        return
    await payments.update_one({"payment_id": payment_id}, {"$set": {"utr": utr, "status": "waiting_admin"}})
    await client.send_message(OWNER_ID, f"💰 **New Payment**\nID: {message.from_user.id}\nPlan: {payment['days']} Days\nUTR: {utr}\n\n`/approve {message.from_user.id} {payment['days']}`")
    await message.reply_text("✅ Payment submitted! Waiting for admin approval.")

@app.on_message(filters.command("approve"))
async def approve_premium(client, message):
    if message.from_user.id != OWNER_ID: return
    if len(message.command) < 3: return
    user_id, days = int(message.command[1]), int(message.command[2])
    expiry = int(time.time()) + (days * 24 * 60 * 60)
    await premium_users.update_one({"user_id": user_id}, {"$set": {"expiry": expiry}}, upsert=True)
    await client.send_message(user_id, f"🎉 Your {days} Days Premium activated!")
    await message.reply_text("✅ Approved!")

# --- CONTENT MANAGEMENT ---
@app.on_message((filters.video | filters.document) & filters.private)
async def save_video(client, message):
    if message.from_user.id != OWNER_ID: return
    file_id = message.video.file_id if message.video else message.document.file_id
    app.file_id_temp = file_id
    batch_files.append(file_id)
    await message.reply_text(f"✅ Video Added! (Batch: {len(batch_files)})\n\n`/add name` ya `/addbatch name` use karein.")

@app.on_message(filters.command("add"))
async def add_video(client, message):
    if message.from_user.id != OWNER_ID or len(message.command) < 2: return
    if not hasattr(app, "file_id_temp"): return
    name = message.command[1].lower()
    await videos.update_one({"name": name}, {"$set": {"file_id": app.file_id_temp, "type": "single"}}, upsert=True)
    await message.reply_text(f"✅ Saved! Link: `https://t.me/{BOT_USERNAME}?start={name}`")

@app.on_message(filters.command("addbatch"))
async def add_batch(client, message):
    global batch_files
    if message.from_user.id != OWNER_ID or len(message.command) < 2 or not batch_files: return
    name = message.command[1].lower()
    await videos.update_one({"name": name}, {"$set": {"file_ids": batch_files, "type": "batch"}}, upsert=True)
    await message.reply_text(f"✅ Batch Saved! Link: `https://t.me/{BOT_USERNAME}?start={name}`")
    batch_files = []

@app.on_message(filters.command("list"))
async def list_videos(client, message):
    if message.from_user.id != OWNER_ID: return
    text = "📂 **Saved Videos:**\n\n"
    async for video in videos.find():
        text += f"• `{video['name']}`\n"
    await message.reply_text(text)

@app.on_message(filters.command("delete"))
async def delete_video(client, message):
    if message.from_user.id != OWNER_ID or len(message.command) < 2: return
    await videos.delete_one({"name": message.command[1].lower()})
    await message.reply_text("✅ Deleted!")

@app.on_message(filters.command("cleanup"))
async def cleanup_command(client, message):
    if message.from_user.id == OWNER_ID:
        await tokens.delete_many({})
        await message.reply_text("✅ Tokens Cleaned!")

app.run()
