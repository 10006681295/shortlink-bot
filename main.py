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
'''
with open('/mnt/data/main.py', 'w', encoding='utf-8') as f:
    f.write(code)

print('/mnt/data/main.py')
