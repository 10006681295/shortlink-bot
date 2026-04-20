from pyrogram import Client, filters
from pyrogram.errors import UserNotParticipant
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient
import os
import random
import string
import time
import aiohttp
import asyncio
import threading
import hmac
import hashlib
import razorpay
from flask import Flask, request

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
GPLINK_API = os.getenv("GPLINK_API")
CHANNEL = os.getenv("CHANNEL_USERNAME")
BOT_USERNAME = os.getenv("BOT_USERNAME", "Memestorehubbot")
OWNER_ID = int(os.getenv("OWNER_ID", "1853401283"))

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")

app = Client(
    "bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

flask_app = Flask(__name__)

razorpay_client = razorpay.Client(
    auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)
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
            f"🚫 पहले channel join करो:\n\nhttps://t.me/{CHANNEL.replace('@','')}"
        )
        return

    if len(message.command) < 2:
        await message.reply_text(
            "⚡ Welcome\n\nChoose option below",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("💎 Get Premium", callback_data="premium_menu")],
                    [InlineKeyboardButton("📖 How To Verify", callback_data="how_verify")]
                ]
            )
        )
        return

@app.on_callback_query()
async def callback_handler(client, callback_query):

    data = callback_query.data

    if data == "premium_menu":
        await callback_query.message.reply_text(
            "💎 Choose Your Premium Plan",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("7 Days - ₹19", callback_data="buy_7d")],
                    [InlineKeyboardButton("15 Days - ₹29", callback_data="buy_15d")],
                    [InlineKeyboardButton("30 Days - ₹39", callback_data="buy_30d")],
                    [InlineKeyboardButton("100 Days - ₹99", callback_data="buy_100d")]
                ]
            )
        )

    elif data.startswith("buy_"):

        plan_key = data.replace("buy_", "")
        plan = PLANS[plan_key]

        amount = plan["price"]
        days = plan["days"]

        payment_link = razorpay_client.payment_link.create({
            "amount": amount * 100,
            "currency": "INR",
            "accept_partial": False,
            "description": f"{days} Days Premium Plan",
            "notify": {
                "sms": False,
                "email": False
            },
            "reminder_enable": True,
            "notes": {
                "user_id": str(callback_query.from_user.id),
                "days": str(days)
            },
            "callback_url": f"https://t.me/{BOT_USERNAME}",
            "callback_method": "get"
        })

        payment_url = payment_link["short_url"]

        await payments.insert_one({
            "user_id": callback_query.from_user.id,
            "payment_id": payment_link["id"],
            "days": days,
            "amount": amount,
            "status": "pending",
            "created_at": int(time.time())
        })

        await callback_query.message.reply_text(
            f"💎 Premium Plan\n\n"
            f"Plan: {days} Days\n"
            f"Amount: ₹{amount}\n\n"
            f"Payment hone ke baad premium automatically activate ho jayega.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("💳 Pay Now", url=payment_url)]
                ]
            )
        )

    elif data == "how_verify":
        await callback_query.message.reply_text(
            "Payment complete hone ke baad premium automatically activate ho jayega."
        )

    await callback_query.answer()

@flask_app.route("/webhook", methods=["POST"])
def razorpay_webhook():

    received_signature = request.headers.get("X-Razorpay-Signature")
    body = request.data.decode()

    expected_signature = hmac.new(
        bytes(RAZORPAY_WEBHOOK_SECRET, "utf-8"),
        bytes(body, "utf-8"),
        hashlib.sha256
    ).hexdigest()

    if expected_signature != received_signature:
        return "Invalid signature", 400

    payload = request.json
    event = payload.get("event")

    if event == "payment_link.paid":

        payment_entity = payload["payload"]["payment_link"]["entity"]
        payment_id = payment_entity["id"]
        notes = payment_entity.get("notes", {})

        user_id = int(notes.get("user_id"))
        days = int(notes.get("days"))

        expiry = int(time.time()) + (days * 24 * 60 * 60)

        async def activate_premium():
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

            await payments.update_one(
                {"payment_id": payment_id},
                {
                    "$set": {
                        "status": "paid"
                    }
                }
            )

            await app.send_message(
                user_id,
                f"🎉 Payment Successful\n\nYour {days} Days Premium Plan is now activated."
            )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(activate_premium())
        loop.close()

    return "OK", 200

def run_flask():
    flask_app.run(host="0.0.0.0", port=8080)

threading.Thread(target=run_flask).start()

app.run()
