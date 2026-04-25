import os
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
BASE44_API_KEY = os.environ.get("BASE44_API_KEY")
BASE44_APP_ID = "69e600cd255745ec10a0fa67"

SYSTEM_PROMPT = """You are Bit28Support -- the official AI assistant of Bit28, an invitation-only investment club. Detect the user language and respond in it. Be professional, warm, and trustworthy. Never guarantee returns. Always add risk disclaimers when discussing performance. Direct complex issues to info@bit28.io. Guide users step by step through Vantage setup. Registration link: https://vigco.co/la-com/DQeca8HC. PAMM join link: https://pamm16.vantagemarkets.com/app/join/1361/jjrks3k9. Minimum deposit $100. Performance fee: 50% profit share, high-watermark. No profit = no fee. Monthly target 5-10% net (not guaranteed). For agent registration collect: name, email, referred by, estimated users, estimated capital."""

conversations = {}

def chat_with_openai(user_id, user_message):
    if user_id not in conversations:
        conversations[user_id] = []
    conversations[user_id].append({"role": "user", "content": user_message})
    if len(conversations[user_id]) > 20:
        conversations[user_id] = conversations[user_id][-20:]
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={"model": "gpt-4o-mini", "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + conversations[user_id], "max_tokens": 1000, "temperature": 0.7}
        )
        result = response.json()
        msg = result["choices"][0]["message"]["content"]
        conversations[user_id].append({"role": "assistant", "content": msg})
        return msg
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return "Technical issue. Please contact info@bit28.io"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conversations[update.effective_user.id] = []
    await update.message.reply_text("Welcome to Bit28!\n\nHow can I help you today?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    response = chat_with_openai(update.effective_user.id, update.message.text)
    await update.message.reply_text(response)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot starting...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
