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

SYSTEM_PROMPT = """You are Bit28Support — the official AI assistant of Bit28, an invitation-only investment club. Detect language automatically and respond in that language. Be professional, warm, trustworthy. Never expose internal operations. Always include risk disclaimers when discussing returns. For complex issues direct to info@bit28.io. Main site: Bit28.io. Broker: VantageMarkets.com. Registration: https://vigco.co/la-com/DQeca8HC. PAMM join: https://pamm16.vantagemarkets.com/app/join/1361/jjrks3k9. Performance fee: 50% profit share, high-watermark. Min deposit $100. Target returns 5-10% monthly after fees — NOT a guarantee. Losses possible."""

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
            json={"model": "gpt-4o-mini", "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + conversations[user_id], "max_tokens": 1000}
        )
        msg = response.json()["choices"][0]["message"]["content"]
        conversations[user_id].append({"role": "assistant", "content": msg})
        return msg
    except Exception as e:
        return "Technical issue. Please contact info@bit28.io"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conversations[update.effective_user.id] = []
    await update.message.reply_text("👋 Welcome to Bit28! 
    Ask me anything about Bit28, Investment/PAMM setup, or agent functionality and registration. 
    ⚠️ Trading involves risk. Not financial advice.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    response = chat_with_openai(update.effective_user.id, update.message.text)
    await update.message.reply_text(response)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
