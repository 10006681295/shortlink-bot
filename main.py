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

# --- KEEP-ALIVE LOGIC ---
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

videos, premium_users, payments = db["videos"], db["premium_users"], db["payments"]
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
        await message.reply_text(f"🚫 पहले channel join karo:\n\nhttps://t.me/{CHANNEL_LINK}")
        return

    if len(message.command) < 2:
        await message.reply_photo(
            photo="https://i.ibb.co/8D0X0Q7/sample.jpg",
            caption=f"⚡ Hey, {message.from_user.first_name} ~\n\nOnly Premium users can access files here.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💎 GET PREMIUM 💎", callback_data="premium_menu")]])
        )
        return

    param = message.command[1].lower()
    v_data = await videos.find_one({"name": param})
    if not v_data:
        await message.reply_text("❌ Video not found!")
        return

    p_data = await premium_users.find_one({"user_id": message.from_user.id})
    if p_data and p_data["expiry"] > int(time.time()):
        cap = "💎 Premium Access"
        if v_data.get("type") == "batch":
            for f_id in v_data["file_ids"]:
                await message.reply_video(video=f_id, caption=cap)
        else:
            await message.reply_video(video=v_data["file_id"], caption=cap)
    else:
        await message.reply_text(
            f"⚠️ **Access Denied!**\n\nBhai, ye file sirf Premium users ke liye hai.\n\n"
            f"✅ **After buying a plan you can watch all content unlimited time.**\n"
            f"✅ **Plan lene ke baad aap saara content unlimited baar dekh sakte hain.**",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💎 SUBSCRIBE NOW 💎", callback_data="premium_menu")]])
        )

# --- CALLBACKS ---
@app.on_callback_query()
async def cb_handler(client, query):
    if query.data == "premium_menu":
        btns = [[InlineKeyboardButton(f"{v['days']} Days - ₹{v['price']}", callback_data=f"buy_{k}")] for k, v in PLANS.items()]
        await query.message.reply_text("💎 **Choose Your Plan:**", reply_markup=InlineKeyboardMarkup(btns))
    elif query.data.startswith("buy_"):
        pk = query.data.replace("buy_", ""); p = PLANS[pk]
        pid = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        upi = f"upi://pay?pa={UPI_ID}&pn=Premium&am={p['price']}&cu=INR&tn={pid}"
        qr = qrcode.make(upi); bio = BytesIO(); bio.name = "p.png"; qr.save(bio, "PNG"); bio.seek(0)
        await payments.insert_one({"user_id": query.from_user.id, "payment_id": pid, "days": p["days"]})
        await query.message.reply_photo(photo=bio, caption=f"ID: `{pid}`\n\nVerify: `/verify {pid} YOUR_UTR`")
    await query.answer()

# --- ADMIN ---
@app.on_message(filters.command("verify"))
async def verify(client, message):
    if len(message.command) < 3: return
    pid, utr = message.command[1], message.command[2]
    pay = await payments.find_one({"payment_id": pid, "user_id": message.from_user.id})
    if pay:
        await client.send_message(OWNER_ID, f"💰 **Payment!**\nUID: `{message.from_user.id}`\nUTR: `{utr}`\n`/approve {message.from_user.id} {pay['days']}`")
        await message.reply_text("✅ Sent to admin for approval!")

@app.on_message(filters.command("approve"))
async def approve(client, message):
    if message.from_user.id != OWNER_ID: return
    uid, days = int(message.command[1]), int(message.command[2])
    exp = int(time.time()) + (days * 86400)
    await premium_users.update_one({"user_id": uid}, {"$set": {"expiry": exp}}, upsert=True)
    await client.send_message(uid, "🎉 Premium Activated!")
    await message.reply_text("✅ Approved!")

# --- OWNER: UPDATED CLICKABLE BLUE COMMANDS ---
@app.on_message((filters.video | filters.document | filters.animation) & filters.private)
async def save_video(client, message):
    if message.from_user.id != OWNER_ID: return
    fid = message.video.file_id if message.video else (message.document.file_id if message.document else message.animation.file_id)
    if not fid: return
    
    app.file_id_temp = fid
    batch_files.append(fid)
    
    # Backticks se commands blue aur clickable ban jati hain
    await message.reply_text(
        f"✅ **Video added**\n\n"
        f"Batch size: {len(batch_files)}\n\n"
        f"Single save:\n`/add movie1`\n\n"
        f"Batch save:\n`/addbatch series1`"
    )

@app.on_message(filters.command("add"))
async def add_v(client, message):
    if message.from_user.id != OWNER_ID or len(message.command) < 2: return
    n = message.command[1].lower()
    await videos.update_one({"name": n}, {"$set": {"file_id": app.file_id_temp, "type": "single"}}, upsert=True)
    link = f"https://t.me/{BOT_USERNAME}?start={n}"
    await message.reply_text(f"Videos: 1\n\nLink:\n{link}", disable_web_page_preview=True)

@app.on_message(filters.command("addbatch"))
async def add_b(client, message):
    global batch_files
    if message.from_user.id != OWNER_ID or not batch_files:
        await message.reply_text("❌ Batch khali hai!")
        return
    n = message.command[1].lower()
    size = len(batch_files)
    await videos.update_one({"name": n}, {"$set": {"file_ids": list(batch_files), "type": "batch"}}, upsert=True)
    batch_files.clear()
    link = f"https://t.me/{BOT_USERNAME}?start={n}"
    await message.reply_text(f"✅ **Batch Saved!** (Total: {size})\n\nLink: {link}", disable_web_page_preview=True)

if __name__ == "__main__":
    keep_alive()
    app.run()
