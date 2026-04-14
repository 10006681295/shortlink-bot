from pyrogram import Client, filters
import os

API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

app = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

TOKEN = "12345"

@app.on_message(filters.command("start"))
async def start(client, message):
    link = f"https://gplinks.in/{TOKEN}"
    await message.reply_text(f"🔗 Open link:\n{link}", disable_web_page_preview=True)

@app.on_message(filters.text & ~filters.command)
async def check(client, message):
    if message.text.strip() == TOKEN:
        await message.reply_video(
            video="https://www.w3schools.com/html/mov_bbb.mp4",
            caption="🎉 Here is your video"
        )
    else:
        await message.reply_text("❌ Wrong token")

app.run()
