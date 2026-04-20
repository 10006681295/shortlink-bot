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

mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo["bot_db"]

tokens = db["tokens"]
videos = db["videos"]
premium_users = db["premium_users"]
payments = db["payments"]

EXPIRY = 43200
batch_files = []

PLANS = {
    "7d": {"days": 7, "price": 19},
    "15d": {"days": 15, "price": 29},
    "30d": {"days": 30, "price": 39},
    "100d": {"days": 100, "price": 99}
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
            f"🚫 पहले channel join करो:\n\nhttps://t.me/{CHANNEL_LINK}"
        )
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
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "• GET PREMIUM •",
                            callback_data="premium_menu"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "• REFER AND EARN •",
                            callback_data="refer_menu"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "• HOW TO VERIFY •",
                            callback_data="how_verify"
                        )
                    ]
                ]
            )
        )
        return

    param = message.command[1]

    token_data = await tokens.find_one({
        "user_id": message.from_user.id,
        "token": param
    })

    if token_data:
        now = int(time.time())

        if now - token_data["created_at"] > EXPIRY:
            await tokens.delete_one({"_id": token_data["_id"]})
            await message.reply_text("⏰ Token expired")
            return

        await tokens.delete_one({"_id": token_data["_id"]})

        video_data = token_data["file_data"]

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
        return

    video_data = await videos.find_one({"name": param})

    if not video_data:
        await message.reply_text("❌ Video not found")
        return

    premium_data = await premium_users.find_one({
        "user_id": message.from_user.id
    })

    if premium_data:
        if premium_data["expiry"] > int(time.time()):

            if video_data.get("type") == "batch":
                for file_id in video_data["file_ids"]:
                    await message.reply_video(
                        video=file_id,
                        caption="💎 Premium Access"
                    )
            else:
                await message.reply_video(
                    video=video_data["file_id"],
                    caption="💎 Premium Access"
                )
            return
        else:
            await premium_users.delete_one({
                "user_id": message.from_user.id
            })

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
        f"👉 नीचे button पर click करो\n\n"
        f"⏳ Token Validity: 12 Hours\n"
        f"❌ Token सिर्फ 1 बार काम करेगा",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "• VERIFY NOW •",
                        url=short_link
                    )
                ],
                [
                    InlineKeyboardButton(
                        "• GET PREMIUM •",
                        callback_data="premium_menu"
                    )
                ]
            ]
        )
    )

@app.on_callback_query()
async def callback_handler(client, callback_query):

    data = callback_query.data

    if data == "premium_menu":
        await callback_query.message.reply_text(
            "💎 Choose Your Premium Plan",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "7 Days - ₹19",
                            callback_data="buy_7d"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "15 Days - ₹29",
                            callback_data="buy_15d"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "30 Days - ₹39",
                            callback_data="buy_30d"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "100 Days - ₹99",
                            callback_data="buy_100d"
                        )
                    ]
                ]
            )
        )

    elif data.startswith("buy_"):

        plan_key = data.replace("buy_", "")
        plan = PLANS[plan_key]

        payment_id = generate_token()
        amount = plan["price"]
        days = plan["days"]

        upi_link = (
            f"upi://pay?pa={UPI_ID}"
            f"&pn=PremiumAccess"
            f"&am={amount}"
            f"&cu=INR"
            f"&tn={payment_id}"
        )

        qr = qrcode.make(upi_link)

        bio = BytesIO()
        bio.name = "payment.png"
        qr.save(bio, "PNG")
        bio.seek(0)

        await payments.insert_one({
            "user_id": callback_query.from_user.id,
            "payment_id": payment_id,
            "plan": plan_key,
            "days": days,
            "amount": amount,
            "status": "pending",
            "created_at": int(time.time())
        })

        await callback_query.message.reply_photo(
            photo=bio,
            caption=(
                f"💎 Premium Plan Request\n\n"
                f"Plan: {days} Days\n"
                f"Amount: ₹{amount}\n"
                f"Payment ID: {payment_id}\n\n"
                f"QR scan करके payment करो\n\n"
                f"Payment के बाद यह भेजो:\n"
                f"/verify {payment_id} YOUR_UTR"
            )
        )

    elif data == "refer_menu":
        await callback_query.message.reply_text(
            f"💸 Refer And Earn\n\n"
            f"Share this bot:\nhttps://t.me/{BOT_USERNAME}"
        )

    elif data == "how_verify":
        await callback_query.message.reply_text(
            "1. Video link open करो\n"
            "2. Verify button दबाओ\n"
            "3. Short link complete करो\n"
            "4. Token मिलेगा\n"
            "5. Token open करके video देखो"
        )

    await callback_query.answer()

@app.on_message(filters.command("verify"))
async def verify_payment(client, message):

    if len(message.command) < 3:
        await message.reply_text(
            "Usage:\n/verify PAYMENT_ID UTR"
        )
        return

    payment_id = message.command[1]
    utr = message.command[2]

    payment = await payments.find_one({
        "payment_id": payment_id,
        "user_id": message.from_user.id
    })

    if not payment:
        await message.reply_text("❌ Payment not found")
        return

    await payments.update_one(
        {"payment_id": payment_id},
        {
            "$set": {
                "utr": utr,
                "status": "waiting_admin"
            }
        }
    )

    await client.send_message(
        OWNER_ID,
        f"💰 New Premium Request\n\n"
        f"User ID: {message.from_user.id}\n"
        f"Plan: {payment['days']} Days\n"
        f"Amount: ₹{payment['amount']}\n"
        f"Payment ID: {payment_id}\n"
        f"UTR: {utr}\n\n"
        f"/approve {message.from_user.id} {payment['days']}"
    )

    await message.reply_text(
        "✅ Payment request submitted\nAdmin approval pending"
    )

@app.on_message(filters.command("approve"))
async def approve_premium(client, message):

    if message.from_user.id != OWNER_ID:
        return

    if len(message.command) < 3:
        await message.reply_text(
            "Usage:\n/approve USER_ID DAYS"
        )
        return

    user_id = int(message.command[1])
    days = int(message.command[2])

    expiry = int(time.time()) + (days * 24 * 60 * 60)

    await premium_users.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "expiry": expiry,
                "days": days
            }
        },
        upsert=True
    )

    await client.send_message(
        user_id,
        f"🎉 Your {days} Days Premium Plan has been activated!"
    )

    await message.reply_text("✅ Premium approved")

@app.on_message((filters.video | filters.document) & filters.private)
async def save_video(client, message):

    global batch_files

    if message.from_user.id != OWNER_ID:
        return

    file_id = message.video.file_id if message.video else message.document.file_id

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

    await videos.delete_many({"name": name})

    await videos.insert_one({
        "name": name,
        "file_id": app.file_id_temp,
        "type": "single"
    })

    await message.reply_text(
        f"✅ Saved Successfully\n\n"
        f"Link:\nhttps://t.me/{BOT_USERNAME}?start={name}"
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

    await videos.delete_many({"name": name})

    await videos.insert_one({
        "name": name,
        "file_ids": batch_files,
        "type": "batch"
    })

    await message.reply_text(
        f"✅ Batch Saved\n\n"
        f"Videos: {len(batch_files)}\n\n"
        f"Link:\nhttps://t.me/{BOT_USERNAME}?start={name}"
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

app.run()
