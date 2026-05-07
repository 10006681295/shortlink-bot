@app.on_message(filters.command("start"))
async def start_command(client, message):
    joined = await check_join(client, message.from_user.id)
    if not joined:
        await message.reply_text(f"🚫 पहले channel join karo:\n\nhttps://t.me/{CHANNEL_LINK}")
        return

    if len(message.command) < 2:
        await message.reply_photo(
            photo="https://i.ibb.co/8D0X0Q7/sample.jpg",
            caption=f"⚡ Hey, {message.from_user.first_name} ~\n\n›› TOKEN VERIFY KARO YA PREMIUM LO",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("• GET PREMIUM •", callback_data="premium_menu")],
                [InlineKeyboardButton("• HOW TO VERIFY •", callback_data="how_verify")]
            ])
        )
        return

    param = message.command[1]

    # --- STEP 1: TOKEN VERIFICATION (Sabse Pehle Ye Check Hoga) ---
    if param.startswith("verify_"):
        token_val = param.replace("verify_", "")
        token_data = await tokens.find_one({"user_id": message.from_user.id, "token": token_val})

        if not token_data:
            await message.reply_text("❌ Invalid or Expired link! Wapis link par click karein.")
            return

        now = int(time.time())
        if now - token_data["created_at"] > EXPIRY:
            await tokens.delete_one({"_id": token_data["_id"]})
            await message.reply_text("⏰ Token expired! Naya link generate karein.")
            return

        # Yahan token verify ho gaya, mark it as verified
        await tokens.update_one({"_id": token_data["_id"]}, {"$set": {"is_verified": True}})
        
        video_data = token_data["file_data"]
        caption = "🎉 Access Granted! (Valid for 12 Hours)"
        
        if video_data.get("type") == "batch":
            for file_id in video_data["file_ids"]:
                await message.reply_video(video=file_id, caption=caption)
        else:
            await message.reply_video(video=video_data["file_id"], caption=caption)
        return

    # --- STEP 2: VIDEO EXISTENCE CHECK ---
    video_data = await videos.find_one({"name": param})
    if not video_data:
        await message.reply_text("❌ Video not found")
        return

    # --- STEP 3: PREMIUM CHECK (Premium hai toh direct do) ---
    premium_data = await premium_users.find_one({"user_id": message.from_user.id})
    if premium_data and premium_data["expiry"] > int(time.time()):
        if video_data.get("type") == "batch":
            for file_id in video_data["file_ids"]:
                await message.reply_video(video=file_id, caption="💎 Premium Access")
        else:
            await message.reply_video(video=video_data["file_id"], caption="💎 Premium Access")
        return

    # --- STEP 4: ALREADY VERIFIED CHECK (12 Ghante wala logic) ---
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

    # --- STEP 5: AGAR KUCH NAHI HAI TOH AD LINK DO ---
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

    # Short_link agar generate nahi hui toh error handling
    if short_link == deep_link:
        await message.reply_text("❌ API Issue: Ad link generate nahi ho pa rahi. Admin se contact karein.")
        return

    await message.reply_text(
        f"🔥 **Access Locked** 🔥\n\n"
        f"Video dekhne ke liye niche button par click karke verify karein. Uske baad 'Open' ya 'Start' button dabayein.\n\n"
        f"⏳ **Validity:** 12 Hours",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("• VERIFY NOW (AD) •", url=short_link)],
            [InlineKeyboardButton("• GET PREMIUM (NO ADS) •", callback_data="premium_menu")]
        ])
    )
