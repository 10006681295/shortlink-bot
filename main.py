import os
import time
import random
import string
import qrcode
from io import BytesIO
from flask import Flask
from threading import Thread
from pyrogram import Client, filters
from pyrogram.errors import UserNotParticipant
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient

# --- RENDER KEEP-ALIVE ---
web = Flask('')
@web.route('/')
def home(): return "Bot is Running!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web.run(host='0.0.0.0', port=port)

def keep_alive():
    Thread(target=run_web).start()

# --- CONFIGURATION ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
CHANNEL = os.getenv("CHANNEL_USERNAME")
BOT_USERNAME = "Memestorehubbot"
OWNER_ID = int(os.getenv("OWNER_ID", "1853401283"))
UPI_ID = os.getenv("UPI_ID")

CHANNEL_LINK = CHANNEL.replace("@", "")

app = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo["bot_db"]

videos = db["videos"]
premium_users = db["premium_users"]
payments = db["payments"]

batch_files = []

PLANS = {
    "7d": {"days": 7, "price": 19},
    "15d": {"days": 15, "price": 29},
    "30d": {"days": 30, "price": 39},
    "100d": {"days": 100, "price": 99}
}

# --- HELPERS ---
async def check_join(client, user_id):
    try:
        await client.get_chat_member(CHANNEL, user_id)
        return True
    except UserNotParticipant: return False
    except: return False

# --- START COMMAND ---
@app.on_message(filters.command("start"))
async def start_command(client, message):
    joined = await check_join(client, message.from_user.id)
    if not joined:
        await message.reply_text(f"🚫 पहले channel join करो:\n\nhttps://t.me/{CHANNEL_LINK}")
        return

    if len(message.command) < 2:
        await message.reply_photo(
            photo="https://i.ibb.co/8D0X0Q7/sample.jpg",
            caption=f"⚡ Hey, {message.from_user.first_name} ~\n\nOnly Premium users can access files here.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💎 GET PREMIUM 💎", callback_data="premium_menu")]])
        )
        return

    param = message.command[1].lower()
    video_data = await videos.find_one({"name": param})
    if not video_data:
        await message.reply_text("❌ Video not found!")
        return

    premium = await premium_users.find_one({"user_id": message.from_user.id})
    if premium and premium["expiry"] > int(time.time()):
        cap = "💎 Premium Access"
        if video_data.get("type") == "batch":
            for f_id in video_data["file_ids"]:
                await message.reply_video(video=f_id, caption=cap)
        else:
            await message.reply_video(video=video_data["file_id"], caption=cap)
    else:
        await message.reply_text(
            "⚠️ **Access Denied!**\n\nBhai, ye file sirf Premium users ke liye hai.\n\n✅ Plan lene ke baad aap unlimited content dekh sakte hain.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💎 SUBSCRIBE NOW 💎", callback_data="premium_menu")]])
        )

# --- PREMIUM CALLBACKS ---
@app.on_callback_query()
async def callback_handler(client, callback_query):
    data = callback_query.data
    if data == "premium_menu":
        btns = [[InlineKeyboardButton(f"{v['days']} Days - ₹{v['price']}", callback_data=f"buy_{k}")] for k, v in PLANS.items()]
        await callback_query.message.reply_text("💎 **Choose Your Plan:**", reply_markup=InlineKeyboardMarkup(btns))
    elif data.startswith("buy_"):
        plan_key = data.replace("buy_", "")
        plan = PLANS[plan_key]
        p_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        upi = f"upi://pay?pa={UPI_ID}&pn=Premium&am={plan['price']}&cu=INR&tn={p_id}"
        qr = qrcode.make(upi); bio = BytesIO(); bio.name = "p.png"; qr.save(bio, "PNG"); bio.seek(0)
        await payments.insert_one({"user_id": callback_query.from_user.id, "payment_id": p_id, "days": plan["days"], "status": "pending"})
        await callback_query.message.reply_photo(photo=bio, caption=f"Plan: {plan['days']} Days\nPrice: ₹{plan['price']}\nID: `{p_id}`\n\nPay karke bhejo:\n`/verify {p_id} YOUR_UTR`")
    await callback_query.answer()

# --- PAYMENT VERIFY/APPROVE ---
@app.on_message(filters.command("verify"))
async def verify_payment(client, message):
    if len(message.command) < 3: return
    p_id, utr = message.command[1], message.command[2]
    pay = await payments.find_one({"payment_id": p_id, "user_id": message.from_user.id})
    if pay:
        await client.send_message(OWNER_ID, f"💰 **Payment!**\nUID: `{message.from_user.id}`\nUTR: `{utr}`\n`/approve {message.from_user.id} {pay['days']}`")
        await message.reply_text("✅ Sent to admin for approval!")

@app.on_message(filters.command("approve"))
async def approve_premium(client, message):
    if message.from_user.id != OWNER_ID: return
    u_id, days = int(message.command[1]), int(message.command[2])
    exp = int(time.time()) + (days * 86400)
    await premium_users.update_one({"user_id": u_id}, {"$set": {"expiry": exp}}, upsert=True)
    await client.send_message(u_id, "🎉 Premium Activated!")
    await message.reply_text("✅ Approved!")

# --- OWNER CONTENT MANAGEMENT (NEW FORMAT) ---
@app.on_message((filters.video | filters.document | filters.animation) & filters.private)
async def save_video(client, message):
    if message.from_user.id != OWNER_ID: return
    
    file_id = None
    if message.video: file_id = message.video.file_id
    elif message.document: file_id = message.document.file_id
    elif message.animation: file_id = message.animation.file_id
    
    if not file_id: return

    app.file_id_temp = file_id
    batch_files.append(file_id)
    
    # EXACT FORMAT FROM YOUR PHOTO
    await message.reply_text(
        f"✅ **Video added**\n\n"
        f"Batch size: {len(batch_files)}\n\n"
        f"Single save:\n`/add movie1`\n\n"
        f"Batch save:\n`/addbatch series1`"
    )

@app.on_message(filters.command("add"))
async def add_video(client, message):
    if message.from_user.id != OWNER_ID or len(message.command) < 2: return
    name = message.command[1].lower()
    await videos.update_one({"name": name}, {"$set": {"file_id": app.file_id_temp, "type": "single"}}, upsert=True)
    await message.reply_text(f"✅ **Saved!**\nLink: `https://t.me/{BOT_USERNAME}?start={name}`")

@app.on_message(filters.command("addbatch"))
async def add_batch(client, message):
    global batch_files
    if message.from_user.id != OWNER_ID or not batch_files: return
    name = message.command[1].lower()
    await videos.update_one({"name": name}, {"$set": {"file_ids": list(batch_files), "type": "batch"}}, upsert=True)
    batch_files.clear()
    await message.reply_text(f"✅ **Batch Saved!**\nLink: `https://t.me/{BOT_USERNAME}?start={name}`")

@app.on_message(filters.command("delete"))
async def delete_video(client, message):
    if message.from_user.id == OWNER_ID:
        await videos.delete_one({"name": message.command[1].lower()})
        await message.reply_text("✅ Deleted!")

if __name__ == "__main__":
    keep_alive()
    app.run()
