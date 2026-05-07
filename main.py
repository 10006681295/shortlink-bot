import os
import time
import random
import string
import qrcode
from io import BytesIO
from pyrogram import Client, filters
from pyrogram.errors import UserNotParticipant
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient

# --- 1. CONFIGURATION ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
CHANNEL = os.getenv("CHANNEL_USERNAME")
BOT_USERNAME = "Memestorehubbot"
OWNER_ID = int(os.getenv("OWNER_ID", "1853401283"))
UPI_ID = os.getenv("UPI_ID")

CHANNEL_LINK = CHANNEL.replace("@", "")

# --- 2. INITIALIZE APP ---
app = Client(
    "bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# --- 3. DATABASE SETUP ---
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

# --- 4. HELPERS ---
async def check_join(client, user_id):
    try:
        await client.get_chat_member(CHANNEL, user_id)
        return True
    except UserNotParticipant:
        return False
    except:
        return False

# --- 5. MAIN LOGIC ---

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
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💎 GET PREMIUM 💎", callback_data="premium_menu")]
            ])
        )
        return

    param = message.command[1]
    video_data = await videos.find_one({"name": param})
    if not video_data:
        await message.reply_text("❌ Video not found!")
        return

    premium_data = await premium_users.find_one({"user_id": message.from_user.id})
    
    if premium_data and premium_data["expiry"] > int(time.time()):
        caption = "💎 Premium Access"
        if video_data.get("type") == "batch":
            for f_id in video_data["file_ids"]:
                await message.reply_video(video=f_id, caption=caption)
        else:
            await message.reply_video(video=video_data["file_id"], caption=caption)
    else:
        if premium_data: await premium_users.delete_one({"user_id": message.from_user.id})
        
        await message.reply_text(
            f"⚠️ **Access Denied!**\n\nBhai, ye file sirf Premium users ke liye hai.\n\n"
            f"✅ **After buying a plan you can watch all content unlimited time.**\n"
            f"✅ **Plan lene ke baad aap saara content unlimited baar dekh sakte hain.**",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💎 SUBSCRIBE NOW 💎", callback_data="premium_menu")]
            ])
        )

@app.on_callback_query()
async def callback_handler(client, callback_query):
    data = callback_query.data

    if data == "premium_menu":
        buttons = [[InlineKeyboardButton(f"{v['days']} Days - ₹{v['price']}", callback_data=f"buy_{k}")] for k, v in PLANS.items()]
        await callback_query.message.reply_text(
            "💎 **Choose Your Plan:**\n\n"
            "✨ After buy a plan you can watch all content unlimited time.\n"
            "✨ Plan lene ke baad aap saara content unlimited baar dekh sakte hain.",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data.startswith("buy_"):
        plan_key = data.replace("buy_", "")
        plan = PLANS[plan_key]
        p_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        upi = f"upi://pay?pa={UPI_ID}&pn=Premium&am={plan['price']}&cu=INR&tn={p_id}"
        qr = qrcode.make(upi); bio = BytesIO(); bio.name = "p.png"; qr.save(bio, "PNG"); bio.seek(0)

        await payments.insert_one({"user_id": callback_query.from_user.id, "payment_id": p_id, "days": plan["days"], "amount": plan["price"], "status": "pending"})
        
        await callback_query.message.reply_photo(
            photo=bio,
            caption=(
                f"💎 Premium Plan Request\n\n"
                f"Plan: {plan['days']} Days\n"
                f"Amount: ₹{plan['price']}\n"
                f"Payment ID: `{p_id}`\n\n"
                f"QR scan करके payment करो\n\n"
                f"Payment के बाद यह भेजो:\n"
                f"`/verify {p_id} YOUR_UTR`"
            )
        )
    await callback_query.answer()

@app.on_message(filters.command("verify"))
async def verify_payment(client, message):
    if len(message.command) < 3:
        await message.reply_text("❌ Galat format! Use: `/verify ID UTR` (e.g. `/verify ABCD123 41234567890`)")
        return
    p_id, utr = message.command[1], message.command[2]
    pay = await payments.find_one({"payment_id": p_id, "user_id": message.from_user.id})
    if pay:
        await client.send_message(OWNER_ID, f"💰 **New Payment Alert!**\n\nUser: `{message.from_user.id}`\nID: `{p_id}`\nUTR: `{utr}`\nPlan: {pay['days']} Days\n\nApprove karne ke liye click karein:\n`/approve {message.from_user.id} {pay['days']}`")
        await message.reply_text("✅ Payment sent to admin! Jaise hi admin check karega, aapka premium active ho jayega.")
    else:
        await message.reply_text("❌ Payment ID match nahi hui. Sahi ID bhejein.")

@app.on_message(filters.command("approve"))
async def approve_premium(client, message):
    if message.from_user.id != OWNER_ID: return
    u_id, days = int(message.command[1]), int(message.command[2])
    exp = int(time.time()) + (days * 86400)
    await premium_users.update_one({"user_id": u_id}, {"$set": {"expiry": exp}}, upsert=True)
    await client.send_message(u_id, "🎉 Congratulations! Your Premium is now active. Enjoy unlimited access!")
    await message.reply_text("✅ User Approved!")

# --- 6. OWNER CONTENT MANAGEMENT ---

@app.on_message((filters.video | filters.document) & filters.private)
async def save_video(client, message):
    if message.from_user.id != OWNER_ID: return
    f_id = message.video.file_id if message.video else message.document.file_id
    app.file_id_temp = f_id
    batch_files.append(f_id)
    await message.reply_text(f"✅ File Added! (Total in Batch: {len(batch_files)})")

@app.on_message(filters.command("add"))
async def add_video(client, message):
    if message.from_user.id != OWNER_ID or len(message.command) < 2: return
    name = message.command[1].lower()
    await videos.update_one({"name": name}, {"$set": {"file_id": app.file_id_temp, "type": "single"}}, upsert=True)
    await message.reply_text(f"✅ Saved! Link: `https://t.me/{BOT_USERNAME}?start={name}`")

@app.on_message(filters.command("addbatch"))
async def add_batch(client, message):
    global batch_files
    if message.from_user.id != OWNER_ID or not batch_files: return
    name = message.command[1].lower()
    await videos.update_one({"name": name}, {"$set": {"file_ids": list(batch_files), "type": "batch"}}, upsert=True)
    batch_files.clear()
    await message.reply_text(f"✅ Batch Saved! Link: `https://t.me/{BOT_USERNAME}?start={name}`")

@app.on_message(filters.command("delete"))
async def delete_video(client, message):
    if message.from_user.id == OWNER_ID:
        await videos.delete_one({"name": message.command[1].lower()})
        await message.reply_text("✅ Deleted!")

if __name__ == "__main__":
    app.run()
