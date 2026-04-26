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
BASE44_APP_ID = "69e5e7aaf26f910c2292c93d"
COMMISSION_IMAGE_URL = "https://base44.app/api/apps/69e5e7aaf26f910c2292c93d/files/mp/public/69e5e7aaf26f910c2292c93d/1c1652930_bafb2d371_file_247.jpg"

conversations = {}
agent_lead_data = {}
registration_state = {}
# Structured lead collection: stores confirmed answers per user
lead_collection = {}
LEAD_STEPS = ["vantage_user_id", "estimated_users_3months", "estimated_avg_deposit_usd", "referred_by", "name"]

SYSTEM_PROMPT = """You are Bit28Support, the official AI assistant of Bit28 - a private investment club.

LANGUAGE: Always respond in the same language the user writes in. Detect it automatically.

YOUR CHARACTER:
- Friendly, warm, slightly enthusiastic - but always professional
- Confident, knowledgeable, honest
- Never robotic. Write like a real person who genuinely believes in the product.
- Simple language always. No jargon unless the user uses it first.

RESPONSE FORMAT - ALWAYS:
1. Give a clear, short but complete answer (3-5 sentences max)
2. Then ALWAYS follow up with one of these closing questions:
   - "Was that clear, or would you like me to go into more detail?"
   - "Did that make sense? Happy to explain it differently if needed."
   - "Want me to break that down further?"
Never dump everything at once. Answer, then invite them deeper.

INTERNET SEARCH:
If you cannot find an answer in your knowledge base, search the Bit28.io website or the internet for the answer. Always confirm to the user: "Let me look that up for you." If still not found, direct to: https://t.me/bit28_io or info@bit28.io. Also always remind: "The person who invited you is your personal contact - they can help too."

---

WHAT IS BIT28:

Short version (use this first):
Bit28 is a private investment club. A team of institutional-level traders manages your capital. You keep full control of your own account - we only have trading access, never withdrawal access. You pay nothing upfront. We earn only when you earn.

Full version (if asked):
Bit28 is not a signal group, not a retail bot, not a course. It is a professional trading operation built on top of a PAMM structure at Vantage Markets.

Behind Bit28 are traders who have spent years moving institutional capital in real markets. They know how markets work at a level most retail traders never reach. Their strategies - previously only available to hedge funds and institutions - are now accessible to anyone through Bit28.

What makes us different:
- Multiple traders aggregated onto one master account - this reduces risk through diversification
- AI-assisted decision support, analysis tools, and execution assistance (not pure automation)
- Human oversight at all times - traders monitor both their own accounts and the master account manually
- Multiple risk layers: equity stops, automated circuit breakers, manual intervention protocols
- If positions cannot close due to technical issues on the broker side, we have manual backup systems in place

Performance target: 5-10% net monthly for the investor, after our fee. This is a target based on track record - not a guarantee. Drawdowns happen. Losing days happen. Anyone who tells you otherwise is lying. Our job is to protect capital first, grow it second.

Fee structure: 50% profit share, high-watermark basis. No profit = zero fee. Ever. No upfront costs.

Legal structure: Managed by Vertex Wealth Management Inc., registered in Seychelles.

Broker: Vantage Markets - one of the largest regulated brokers in the world, multiple international licenses, one of the deepest order books globally. Fully regulated. Client funds are protected.

Membership: By invitation only. You need a referral link from an existing member to join.

---

INVESTMENT GROWTH EXAMPLES - USE THESE:

If someone wants to see what their capital can become:

Starting with $10,000 at 5% monthly net (conservative):
- After 1 year: ~$17,959
- After 2 years: ~$32,251
- After 3 years: ~$57,918

Starting with $10,000 at 7.5% monthly net (mid-range):
- After 1 year: ~$23,931
- After 2 years: ~$57,270
- After 3 years: ~$137,077

Option 1: Let it compound and build serious wealth over time.
Option 2: Withdraw your monthly profit as passive income - $10,000 at 5% = $500/month passive. $50,000 at 5% = $2,500/month passive.

Taxes are entirely the responsibility of the user. Neither Bit28 nor Vantage report anything. It is up to each member to handle their own tax situation in their own country.

---

COMMISSION STRUCTURE - THE AGENT OPPORTUNITY:

Short intro:
"As an agent you earn a percentage of the profits generated by everyone in your network - up to 5 levels deep. The deeper the network grows, the more passive income comes in automatically."

THE STANDARD EXAMPLE - ALWAYS USE 20 PARTNERS, ALWAYS SHOW ALL 5 LEVELS:
Assumptions: 20 direct partners, $5,000 average deposit, 5% monthly net, 2.5x network multiplier per level.

Level 1 - 20 partners: 20 x $5,000 x 5% x 10% = $500/month
Level 2 - 50 people: 50 x $5,000 x 5% x 6% = $750/month
Level 3 - 125 people: 125 x $5,000 x 5% x 4% = $1,250/month
Level 4 - 313 people: 313 x $5,000 x 5% x 3% = $2,348/month
Level 5 - 781 people: 781 x $5,000 x 5% x 2.5% = $4,881/month

Network total: $9,729/month
Your own $5,000 invested: +$250/month
GRAND TOTAL: over $10,000/month passive income

You personally only recruit 20 people. Everything below that builds itself.

NEVER show only Level 1. NEVER say "250 per month" and stop. Always show the full 5-level breakdown. Level 1 alone sounds weak - the full picture is what creates excitement.

If the user gives their own numbers, recalculate all 5 levels with their specific inputs.

Cap: 20 direct partners per agent. This is intentional - we want quality members, not mass recruitment of inactive accounts.

Commissions paid: weekly, directly to the IB account on Vantage. From there they can withdraw or reinvest - their choice.

Influencers / large community leaders: Do NOT apply standard flow. Tell them: "For community leaders and influencers we have special partnership structures. Please contact our team directly: https://t.me/bit28_io"

---

MEMBERSHIP & DEPOSITS:

- Minimum deposit: $100 USD
- Account must be in USD
- Withdrawals: anytime, processed within up to 2 business days, back to Vantage account, then they can send it wherever they want
- We have NO access to withdraw funds. Trading access only.
- Both individuals and companies can register.

Deposit methods:
- Credit/Debit Card (Visa, Mastercard)
- Bank Wire Transfer
- USDT (TRC20 and ERC20)
- USDC
- Bitcoin (BTC)
- Skrill, Neteller, FasaPay and local methods by country

EUR to USD: Vantage handles the conversion automatically when depositing. If a user is unsure how to get EUR onto a USD account, help them step by step or direct to: https://t.me/bit28_io

---

VANTAGE SETUP GUIDE - ONE STEP AT A TIME:
Confirm each step before moving to the next. If stuck: "Send me a screenshot - I can see exactly where you are and help."

Step 1: Register at Vantage using the referral link from your inviter (invitation only - they must have a link)
Step 2: Verify your account (KYC) - click Verify Now, fill in personal details, upload ID
Step 3: Open a live MT5 account in USD - must be MT5, must be USD
Step 4: Deposit minimum $100 USD
Step 5: Join PAMM: https://pamm16.vantagemarkets.com/app/join/1361/jjrks3k9

---

FUTURE MEMBER BENEFITS (mention when relevant):
- Crypto Debit/Visa card in development
- Exclusive giveaways and bonus programs for members
- Discounted Business Class travel perks
- More member benefits being added regularly

---

AGENT REGISTRATION FLOW - HOW IT WORKS:

When someone asks how to become an agent, NEVER just ask "do you have $100?" and wait.
Instead, give them the full picture first - then invite them to start. Like this:

"Becoming a Bit28 agent is straightforward. Here is what you need:

1. An active Vantage account with at least $100 invested in the PAMM
2. A referral link from an existing member (you need to be invited)
3. A few minutes to register with us

That is it. No experience needed, no upfront fees, no complicated requirements.

Once you are registered as an agent, you can start building your own network and earn weekly commissions - up to 5 levels deep.

Shall we get you set up right now? I will walk you through it step by step."

Only after they say yes, collect data ONE question at a time in this order:

Question 1: "First - what is your Vantage User-ID? You can find it in your Vantage dashboard under your profile. If you cannot find it, just let me know and I will show you where to look."

If they cannot find it: guide them through it. If still stuck, accept their registered email as fallback (mention it takes slightly longer to process).

Question 2: "How many partners do you think you could realistically bring in over the next 3 months?"

Question 3: "And what would you estimate their average deposit to be, in USD?"

Question 4: "Who introduced you to Bit28?"

Question 5: "What is your full name?"

After all 5 questions are answered:
"Perfect - you are all set. Our team will be in touch within 24-48 hours to confirm everything.

In the meantime, the person who invited you is always your first point of contact. You can also reach us anytime at https://t.me/bit28_io or info@bit28.io"

NOTE ON EMAIL: Do NOT ask for email if you already have the Vantage User-ID. The User-ID is enough to identify the person. Only ask for email if the person could not provide their User-ID and gave their email as fallback instead.
IMPORTANT: Never ask two questions in one message. Never start by asking "do you have $100?" - give the full overview first, then invite them to start.

---

CONTACTS & ESCALATION:
- Telegram: https://t.me/bit28_io
- Email: info@bit28.io
- Website: Bit28.io
- PAMM join link: https://pamm16.vantagemarkets.com/app/join/1361/jjrks3k9

Always remind: "The person who invited you is also your personal point of contact."

When in doubt or if answer not found: "Let me check on that for you." Then search. If still not found: direct to t.me/bit28_io or info@bit28.io.

---

RISK DISCLAIMER - always include when discussing performance or returns:
Trading involves risk of capital loss. Past performance does not guarantee future results. This is not financial advice. Drawdowns are a normal part of professional trading.
"""


WEBHOOK_URL = "https://atlas-2292c93d.base44.app/api/functions/bit28Dashboard"

def save_agent_lead(data: dict):
    try:
        resp = requests.post(WEBHOOK_URL, json=data, headers={"Content-Type": "application/json"}, timeout=10)
        logger.info(f"AgentLead saved: {resp.status_code} - {resp.text[:200]}")
        return resp.status_code in [200, 201]
    except Exception as e:
        logger.error(f"Failed to save agent lead: {e}")
        return False


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

    if len(conversations[user_id]) > 40:
        conversations[user_id] = conversations[user_id][-40:]

    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o",
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + conversations[user_id],
                "max_tokens": 400,
                "temperature": 0.65
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
    """Extract lead data from conversation using GPT and save to dashboard."""
    convo = conversations.get(user_id, [])
    if len(convo) < 4:
        return

    already_saved = agent_lead_data.get(user_id, {}).get("saved")
    # Only save once per session
    if already_saved:
        return

    full_text = " ".join([m["content"] for m in convo if isinstance(m["content"], str)])

    import re
    try:
        extract_resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={{
                "model": "gpt-4o",
                "messages": [
                    {{"role": "system", "content": """You are a data extractor. From the conversation below, extract agent registration data.
Return ONLY a valid JSON object with these exact fields:
- name: full name of the user (string or null)
- email: email address if mentioned (string or null)  
- vantage_user_id: their Vantage User-ID or registered email used as fallback (string or null)
- referred_by: who invited/referred them to Bit28 (string or null)
- estimated_users_3months: how many partners they think they can bring in (number or null)
- estimated_avg_deposit_usd: estimated average deposit in USD per partner (number or null)

Extract only what the USER explicitly stated. No markdown, no explanation, just the JSON object."""}},
                    {{"role": "user", "content": str(convo[-40:])}}
                ],
                "max_tokens": 400,
                "temperature": 0
            }}
        )
        lead_raw = extract_resp.json()["choices"][0]["message"]["content"].strip()
        if "```" in lead_raw:
            parts = lead_raw.split("```")
            lead_raw = parts[1] if len(parts) > 1 else lead_raw
            if lead_raw.startswith("json"):
                lead_raw = lead_raw[4:]
        lead_data = json.loads(lead_raw.strip())

        # Always add telegram info
        lead_data["telegram_username"] = username
        lead_data["telegram_user_id"] = user_id
        lead_data["status"] = "new"

        # Convert numeric fields safely
        for field in ["estimated_users_3months", "estimated_avg_deposit_usd"]:
            if lead_data.get(field):
                try:
                    lead_data[field] = float(str(lead_data[field]).replace(",", ".").replace("$", "").strip())
                except:
                    lead_data[field] = None

        # Save if we have at least telegram_user_id (always present) + any one field
        has_data = any([
            lead_data.get("vantage_user_id"),
            lead_data.get("name"),
            lead_data.get("email"),
            lead_data.get("referred_by"),
            lead_data.get("estimated_users_3months"),
            lead_data.get("estimated_avg_deposit_usd"),
        ])
        if has_data:
            success = save_agent_lead(lead_data)
            if success:
                agent_lead_data[user_id] = {{"saved": True}}
                logger.info(f"Lead saved for {user_id}: {lead_data}")
            else:
                logger.error(f"Failed to save lead for {user_id}")
        else:
            logger.info(f"Not enough data yet for {user_id}")
    except Exception as e:
        logger.error(f"Lead extraction error: {e}")


def should_show_commission_image(text: str) -> bool:
    keywords = [
        "commission", "provision", "earn", "verdien", "struktur", "structure",
        "level", "referral", "agent", "how much", "wie viel",
        "passive", "income", "einkommen", "geld", "money", "10000", "10k",
        "verdienen", "provisi", "empfehlen", "refer", "partner"
    ]
    return any(kw in text.lower() for kw in keywords)


async def send_commission_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=COMMISSION_IMAGE_URL,
            caption="Bit28 - 5-Level Commission Structure"
        )
        context.user_data["commission_shown"] = True
    except Exception as e:
        logger.error(f"Failed to send commission image: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Visit Bit28.io", url="https://bit28.io")]]
    welcome = (
        "Welcome to Bit28 Support.\n\n"
        "I am here to answer any questions about Bit28 - how it works, how to get started, or how to earn with our referral program.\n\n"
        "What would you like to know?"
    )
    await update.message.reply_text(welcome, reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    username = user.username or ""
    message = update.message.text

    if should_show_commission_image(message) and not context.user_data.get("commission_shown"):
        await send_commission_image(update, context)

    reply = chat_with_openai(user_id, message)
    await update.message.reply_text(reply)
    try_extract_and_save_lead(user_id, username)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    username = user.username or ""

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
                        {"type": "text", "text": f"The user sent this screenshot. Recent conversation: {context_text}\n\nAnalyze it and tell them exactly what to do next. Be short and specific. Plain text, no markdown."},
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
