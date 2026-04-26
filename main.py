import os
import logging
import requests
import tempfile
import base64
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
BASE44_API_KEY = os.environ.get("BASE44_API_KEY")
BASE44_APP_ID = "69e600cd255745ec10a0fa67"
COMMISSION_IMAGE_URL = "https://base44.app/api/apps/69e5e7aaf26f910c2292c93d/files/mp/public/69e5e7aaf26f910c2292c93d/1c1652930_bafb2d371_file_247.jpg"

conversations = {}
agent_lead_data = {}
last_message_time = {}

SYSTEM_PROMPT = """You are Bit28Support, the official support and sales concierge of Bit28.

## LANGUAGE
Detect the user's language from their first message. Always respond in that same language.

## FORMATTING
- Plain text only. No **, no *, no #, no markdown.
- Keep messages short and natural - like a real person texting.
- Use line breaks between different thoughts.
- Never write a wall of text.

## YOUR ROLE
You are a knowledgeable, professional, and warm concierge. Think of yourself as a senior relationship manager at a private investment club - not a chatbot, not a salesperson.

Your job:
1. First: understand what the user needs and answer it properly
2. Then: represent Bit28 professionally and with confidence
3. Finally: when the moment is right, help them see the opportunity

Do NOT jump straight to selling. Do NOT push questions before you have given a proper answer. Earn trust first, then guide.

## CONVERSATION STYLE
- If someone asks a question, answer it fully and clearly first.
- Keep it simple. One clear idea at a time.
- If someone wants detail, give detail. If they want a quick answer, keep it quick.
- Read the room. A curious person wants information. An excited person is ready to move forward.
- Handle objections calmly and honestly. Never oversell.
- Only ask a follow-up question when it makes natural sense - not after every single message.

## WHAT IS BIT28
Bit28 is a private, invitation-only investment club. Behind it are institutional traders who previously managed billions in capital at major hedge funds. Their goal is to make institutional-grade trading accessible to everyone.

Clients deposit into their own personal Vantage Markets account. Bit28 gets trading access only - they can never withdraw the client's funds. The capital is managed through a PAMM structure.

Fee model: Bit28 takes 50% of profits only. On a high-watermark basis. If there is no profit, there is no fee. The client keeps the other 50%.

Target performance: 5-10% net per month for the investor after the fee. This is a target based on historical results - not a guarantee. Markets involve risk and drawdowns are normal.

Managed by Vertex Wealth Management Inc., registered in Seychelles.

## HOW TO EXPLAIN THE COMMISSION STRUCTURE
When someone asks how the commission works, explain it properly first:

Bit28 has a 5-level referral structure. When you bring someone in as a client, you earn a share of the profits generated from their capital - not from the deposit itself, from the actual trading profits.

The percentages per level:
Level 1 (your direct partners): 10% of their profits
Level 2 (their partners): 6%
Level 3: 4%
Level 4: 3%
Level 5: 2.5%
Level 6 and beyond: 0% - but those people build their own identical structure, which keeps growing independently.

Each person can have up to 20 direct partners. Commissions are paid weekly.

Example to make it concrete:
Say you bring in 5 partners, each deposits $3,000, and the monthly performance is 5%.
Each partner generates $150 in profit. You earn 10% of that = $15 per partner = $75/month from Level 1 alone.
Now each of those 5 partners brings in 2-3 people. Suddenly you have 12 people on Level 2, each generating commissions for you at 6%.
This compounds across 5 levels. With an active network of just 10-15 people, monthly passive income of $3,000-$8,000 is realistic.
To reach $10,000/month passively: approximately 15 direct partners with an average deposit of $7,000, combined with 5% monthly performance across 5 levels.

After explaining, you can naturally ask: "Do you have people in mind who might be interested? I can run the exact numbers for your situation."

## DEPOSIT METHODS - CONFIRMED
Vantage Markets accepts:
- Credit/Debit Card (Visa, Mastercard)
- Bank Wire Transfer
- USDT (TRC20 and ERC20) - fully supported
- USDC - fully supported
- Bitcoin (BTC) - supported in most regions
- Local methods depending on country (Skrill, Neteller, FasaPay etc.)
Minimum deposit: $100 USD. Account must run in USD.
If unsure about a specific country or method: "Let me connect you with our team to confirm - https://t.me/bit28_io"

## JOINING
When someone wants to join, first ask: "Do you have an invitation link from the person who referred you?"
If yes: guide them to use it for Vantage registration.
If no: "No problem - just message our team directly and they will get you set up: https://t.me/bit28_io"
Never give out a generic Vantage link as the first step.

## VANTAGE SETUP - STEP BY STEP
Go one step at a time. Confirm each step before moving on. If stuck: "Send me a screenshot and I can see exactly what to do."

Step 1: Register at Vantage using the referral link from your inviter
Step 2: Verify your account (KYC) - click Verify Now and fill in your details
Step 3: Open a live MT5 account in USD (must be MT5, must be USD)
Step 4: Deposit minimum $100 USD (USDT, USDC, card, bank transfer all work)
Step 5: Join the PAMM via this link: https://pamm16.vantagemarkets.com/app/join/1361/jjrks3k9

## AGENT REGISTRATION
First confirm they have at least $100 active in the Vantage PAMM.
Then collect one at a time:
1. Estimated number of users they can bring in within 3 months
2. Estimated average deposit per user (USD)
3. Who referred them to Bit28
4. Their Vantage User-ID or registered email
5. Full name
6. Email address

After collecting all: "You are all set. Our team will be in touch within 24-48 hours. Any questions: https://t.me/bit28_io"

## HONESTY
If you are not 100% sure about something - especially technical details, fees, or country-specific rules - say:
"I want to make sure I give you the right answer - please check with our team: https://t.me/bit28_io or info@bit28.io"
Never guess. Never make up details.

## CONTACTS
Telegram: https://t.me/bit28_io
Email: info@bit28.io
Website: Bit28.io
PAMM join link: https://pamm16.vantagemarkets.com/app/join/1361/jjrks3k9

## RISK DISCLAIMER
Always mention when discussing returns or performance:
Past performance does not guarantee future results. Trading involves risk of loss. This is not financial advice.
"""


def save_agent_lead(data: dict):
    try:
        url = f"https://api.base44.com/api/apps/{BASE44_APP_ID}/entities/AgentLead"
        headers = {"api_key": BASE44_API_KEY, "Content-Type": "application/json"}
        resp = requests.post(url, json=data, headers=headers)
        logger.info(f"AgentLead saved: {resp.status_code} - {resp.text[:200]}")
    except Exception as e:
        logger.error(f"Failed to save agent lead: {e}")


def transcribe_voice(file_path: str) -> str:
    try:
        with open(file_path, "rb") as f:
            response = requests.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                files={"file": ("voice.ogg", f, "audio/ogg")},
                data={"model": "whisper-1"}
            )
        return response.json().get("text", "")
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return ""


def chat_with_openai(user_id: str, user_message: str) -> str:
    if user_id not in conversations:
        conversations[user_id] = []

    conversations[user_id].append({"role": "user", "content": user_message})

    if len(conversations[user_id]) > 30:
        conversations[user_id] = conversations[user_id][-30:]

    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + conversations[user_id],
                "max_tokens": 350,
                "temperature": 0.7
            }
        )
        data = response.json()
        reply = data["choices"][0]["message"]["content"]
        conversations[user_id].append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return "Having a brief issue - please try again or contact us: https://t.me/bit28_io"


def try_extract_and_save_lead(user_id: str, username: str):
    convo = conversations.get(user_id, [])
    if len(convo) < 8:
        return
    if agent_lead_data.get(user_id, {}).get("saved"):
        return
    full_text = " ".join([m["content"] for m in convo if isinstance(m["content"], str)])
    has_email = "@" in full_text and any(kw in full_text.lower() for kw in ["email", "e-mail"])
    has_submitted = any(kw in full_text.lower() for kw in ["all set", "submitted", "24-48", "team will"])
    if not (has_email and has_submitted):
        return
    try:
        extract_resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "Extract agent lead data from this conversation. Return ONLY valid JSON with: name, email, vantage_user_id, referred_by, estimated_users_3months, estimated_avg_deposit_usd. Use null for missing. No markdown."},
                    {"role": "user", "content": str(convo[-24:])}
                ],
                "max_tokens": 300,
                "temperature": 0
            }
        )
        lead_raw = extract_resp.json()["choices"][0]["message"]["content"].strip()
        if "```" in lead_raw:
            lead_raw = lead_raw.split("```")[1]
            if lead_raw.startswith("json"):
                lead_raw = lead_raw[4:]
        lead_data = json.loads(lead_raw.strip())
        lead_data["telegram_username"] = username
        lead_data["telegram_user_id"] = user_id
        lead_data["status"] = "new"
        save_agent_lead(lead_data)
        agent_lead_data[user_id] = {"saved": True}
    except Exception as e:
        logger.error(f"Lead extraction error: {e}")


def should_show_commission_image(text: str) -> bool:
    keywords = [
        "commission", "provision", "earn", "verdien", "struktur", "structure",
        "level", "partner", "referral", "agent", "how much", "wie viel",
        "passive", "income", "einkommen", "geld", "money", "profit share",
        "10000", "10k", "verdienen"
    ]
    return any(kw in text.lower() for kw in keywords)


async def send_commission_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=COMMISSION_IMAGE_URL,
            caption="The Bit28 5-Level Commission Structure:"
        )
        context.user_data["commission_shown"] = True
    except Exception as e:
        logger.error(f"Failed to send commission image: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Visit Bit28.io", url="https://bit28.io")]]
    welcome = (
        "Welcome to Bit28 Support!\n\n"
        "I can help you with how Bit28 works, setting up your account, "
        "the commission structure, or becoming an agent.\n\n"
        "Just type or send a voice message - I speak your language.\n\n"
        "What can I help you with?"
    )
    await update.message.reply_text(welcome, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Visit Bit28.io", url="https://bit28.io")]]))
    last_message_time[str(update.effective_user.id)] = datetime.now()


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    username = user.username or ""
    message = update.message.text
    last_message_time[user_id] = datetime.now()

    if should_show_commission_image(message) and not context.user_data.get("commission_shown"):
        await send_commission_image(update, context)

    reply = chat_with_openai(user_id, message)
    await update.message.reply_text(reply)
    try_extract_and_save_lead(user_id, username)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    username = user.username or ""
    last_message_time[user_id] = datetime.now()

    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp_path = tmp.name
    await file.download_to_drive(tmp_path)
    transcribed = transcribe_voice(tmp_path)
    try:
        os.remove(tmp_path)
    except:
        pass

    if not transcribed:
        await update.message.reply_text("Could not make out the voice message - could you type it instead?")
        return

    if should_show_commission_image(transcribed) and not context.user_data.get("commission_shown"):
        await send_commission_image(update, context)

    reply = chat_with_openai(user_id, transcribed)
    await update.message.reply_text(reply)
    try_extract_and_save_lead(user_id, username)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    last_message_time[user_id] = datetime.now()

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = tmp.name
    await file.download_to_drive(tmp_path)

    try:
        with open(tmp_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
        os.remove(tmp_path)
    except Exception as e:
        logger.error(f"Image read error: {e}")
        await update.message.reply_text("Received your screenshot but had trouble reading it. What step are you on?")
        return

    convo = conversations.get(user_id, [])
    context_text = " ".join([m["content"] for m in convo[-6:] if isinstance(m["content"], str)])

    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": [
                        {"type": "text", "text": f"User sent this screenshot. Recent context: {context_text}\n\nAnalyze and tell them exactly what to do next. Short, plain text, no markdown."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                    ]}
                ],
                "max_tokens": 350
            }
        )
        reply = response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"Vision error: {e}")
        reply = "I can see your screenshot - what step are you on and what is not working?"

    conversations.setdefault(user_id, [])
    conversations[user_id].append({"role": "user", "content": "[User sent a screenshot]"})
    conversations[user_id].append({"role": "assistant", "content": reply})
    await update.message.reply_text(reply)


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    logger.info("Bit28Support Bot starting...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
