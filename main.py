from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, MessageHandler, Filters

import os

app = Flask(__name__)
TOKEN = os.environ.get("BOT_TOKEN")
bot = Bot(token=TOKEN)

def handle_message(update, context):
    message = update.message
    chat_id = message.chat_id
    channel_username = message.chat.username  # Channel username (if any)
    text = message.text

    # Simple verification logic
    VERIFIED_CHANNELS = ["your_verified_channel"]  # Replace with actual
    if channel_username in VERIFIED_CHANNELS:
        response = "✅ Verified post!"
    else:
        response = "⚠️ Unverified post."

    bot.send_message(chat_id=chat_id, text=response)

@app.route('/', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher = Dispatcher(bot, None, workers=0)
    dispatcher.add_handler(MessageHandler(Filters.text, handle_message))
    dispatcher.process_update(update)
    return 'ok'

if __name__ == '__main__':
    app.run()
