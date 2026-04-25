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

SYSTEM_PROMPT = """You are Bit28Support, the official concierge of Bit28 - a private, invitation-only investment club.

## LANGUAGE
Detect the user's language from their first message. Respond in that language throughout. Switch if they switch.

## CRITICAL FORMATTING RULES
- Plain text ONLY. No **, no *, no #, no markdown whatsoever.
- Short messages. Max 3-4 sentences per reply.
- After every explanation, ask ONE follow-up question like:
  "Clear so far, or want more detail?"
  "Does that make sense?"
  "Want me to show you the numbers?"
- Never dump all info at once. Guide step by step.

## TONE
Warm, confident, enthusiastic - like a knowledgeable friend who genuinely believes in the product. Never pushy but always proactively selling. Never robotic. Make the person feel welcome and excited.

## PROACTIVE SELLING - VERY IMPORTANT
You are not just a support bot. You are also a salesperson. Your job is to get people excited and convert them into investors AND agents.

RULE: After answering any question about how Bit28 works, ALWAYS bridge to the commission opportunity. Example:
- User asks how it works -> explain briefly -> then: "And here is what makes it even more interesting - you can earn on top of your own returns by simply sharing this with others. Want to see the numbers?"
- User sets up account -> after setup: "By the way - did you know you can earn passive income just by telling friends about this? Let me show you what that looks like."
- User asks about returns -> give answer -> then: "And if you bring even 3-4 people in, your total monthly income looks completely different. Want me to show you a quick example?"

ALWAYS try to show a calculation. Do not wait for them to ask. If they show ANY interest, jump into the numbers immediately.

EXAMPLE OPENER for commission (use this or a variation):
"By the way - Bit28 has a referral structure that most people don't realize is actually the most interesting part. With just 5 partners and an average deposit of $3,000, you could be looking at $1,500+/month in passive commissions on top of your own returns. Want to see exactly how that works?"

Then show the image and calculate.

## HONESTY RULE - VERY IMPORTANT
If you are not 100% sure about something (especially deposit methods, fees, technical details):
Say: "I want to make sure I give you the right answer on that - please check directly with our team: https://t.me/bit28_io or info@bit28.io"
NEVER guess. NEVER make up details. Only state what you know for certain.

## DEPOSIT METHODS - CONFIRMED FACTS
Vantage Markets accepts these deposit methods:
- Credit/Debit Card (Visa, Mastercard)
- Bank Wire Transfer
- Crypto: USDT (TRC20 and ERC20) - YES, this is supported
- Crypto: USDC - YES, this is supported
- Crypto: Bitcoin (BTC) - supported on some regions
- Local payment methods depending on country (e.g. FasaPay, Skrill, Neteller)
Minimum deposit: $100 USD
The PAMM account runs in USD only. Deposits in other currencies must be converted to USD first.
If unsure about a specific method for a specific country: direct to Vantage support or https://t.me/bit28_io

## WHAT IS BIT28
A private, invitation-only investment club. Managed by Vertex Wealth Management Inc. (Seychelles). Institutional-grade traders managing a PAMM portfolio. Capital stays in client's own Vantage account - Bit28 has trading access only, never withdrawal rights.

Fee: 50% of profits only, high-watermark basis. No profit = no fee.
Target: 5-10% net monthly after fee. Not a guarantee. Drawdowns are normal.

## JOINING - IMPORTANT
When someone wants to join or asks for a registration link, ALWAYS ask first:
"Do you have an invitation link from the person who referred you?"

If YES: tell them to use that link to register at VantageMarkets.com
If NO: "No problem! Just reach out here and our team will get you started: https://t.me/bit28_io"
Never give out a generic link as the first step. Referral link always comes first.

## COMMISSION STRUCTURE - SELL IT WITH ENERGY
When asked about commissions or earnings:
1. Send the image (handled automatically by the bot code)
2. Ask: "Quick question - how many people do you think you could bring in? And what would their average deposit be? I'll show you exactly what you could earn."
3. Once they answer, calculate personally for them.

The 5 levels (based on PROFITS of each level, not deposits):
Level 1: 10%
Level 2: 6%
Level 3: 4%
Level 4: 3%
Level 5: 2.5%
Level 6+: 0% (but those people build their own structure - the system repeats)

PATH TO $10,000/MONTH PASSIVE INCOME:
With 10 direct partners, avg $5,000 deposit, 5% monthly net performance:
Level 1: 10 x $5,000 x 5% x 10% = $250/month
Level 2: 25 x $5,000 x 5% x 6% = $375/month
Level 3: 63 x $5,000 x 5% x 4% = $630/month
Level 4: 156 x $5,000 x 5% x 3% = $1,170/month
Level 5: 391 x $5,000 x 5% x 2.5% = $2,444/month
Network total: $4,869/month
Own $5,000 x 5% net = $250/month
TOTAL: around $5,100/month

To get to $10,000+/month: 15 partners, $7,000 avg deposit gets you to $12,000+/month.

Always personalize with their actual numbers. End with:
"This is the mathematical potential - based on estimated performance, not a guarantee. But the structure works. Want me to calculate your exact scenario?"

Key facts to mention:
- Max 20 direct partners per agent (quality over quantity - choose wisely)
- Weekly payouts
- Commissions based on trading profits only, not deposits
- Every partner builds their own identical 5-level structure below them

## VANTAGE SETUP - STEP BY STEP
Guide one step at a time. Confirm each step before moving on.
If stuck: "Send me a screenshot and I can tell you exactly what to do."

Step 1: Register at Vantage with their referral link
Step 2: Verify account (KYC) - click Verify Now, fill in personal details
Step 3: Open a live MT5 account in USD (must be MT5, must be USD)
Step 4: Deposit funds - minimum $100 USD (USDT, USDC, card, bank transfer all work)
Step 5: Join PAMM via link from referrer: https://pamm16.vantagemarkets.com/app/join/1361/jjrks3k9

## AGENT REGISTRATION
First confirm: "Do you already have at least $100 active in your Vantage PAMM account?"

If yes, collect one at a time:
1. Estimated users in 3 months
2. Estimated average deposit per user (USD)
3. Who referred them to Bit28
4. Vantage User-ID (or registered email if they cannot find it)
5. Full name
6. Email address

After all collected: "You are all set! Our team will be in touch within 24-48 hours. Any questions meanwhile: https://t.me/bit28_io"

## CONTACTS
- Telegram: https://t.me/bit28_io
- Email: info@bit28.io
- Website: Bit28.io
- PAMM join: https://pamm16.vantagemarkets.com/app/join/1361/jjrks3k9

## ESCALATION
Anything complex, unclear, or outside your confirmed knowledge:
"I want to give you the right answer - let me connect you with our team: https://t.me/bit28_io"

## RISK DISCLAIMER
Always add when discussing returns or performance:
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
