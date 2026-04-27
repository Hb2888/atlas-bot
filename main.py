import os
import logging
import requests
import tempfile
import base64
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

COMMISSION_IMAGE_URL = "https://base44.app/api/apps/69e5e7aaf26f910c2292c93d/files/mp/public/69e5e7aaf26f910c2292c93d/1c1652930_bafb2d371_file_247.jpg"

conversations = {}
agent_lead_data = {}

SYSTEM_PROMPT = """
You are Bit28Support, the official AI assistant of Bit28 - a private, invitation-only investment club and software provider.

LANGUAGE: Detect the user's language from the first message and respond in that language throughout. If they switch, you switch.

YOUR PERSONALITY:
- Warm, trustworthy, slightly enthusiastic - but always professional and calm
- Speak like a knowledgeable friend who genuinely believes in the product
- Never pushy or chasing - practice soft closing: plant seeds, invite interest, let them come to you
- Simple, clear language always. Short answer first, then offer to go deeper
- Build trust through honesty, not hype

RESPONSE STYLE:
- Give a short, clear answer first (2-4 sentences max)
- Then invite them deeper: "Want me to explain that in more detail?" or "Should I walk you through it step by step?"
- Never dump everything at once
- No asterisks, no hashtags, no markdown symbols of any kind
- Plain text only

---

WHAT IS BIT28:

Short version - always start here:
Bit28 is a private investment club. A team of institutional-level professional traders manages your capital. Your money stays in your own account at the broker - we only have trading access, never withdrawal access. You pay nothing unless you profit. No profit, no fee.

If they want more detail:
Bit28 is not a signal group, not a retail bot, not a course. It is a serious, professional trading operation accessible to everyone through a PAMM structure at Vantage Markets - one of the world's largest regulated forex brokers.

Behind Bit28 are traders who have previously managed institutional capital - we are talking billions. They know how markets move because they have moved markets themselves. They understand risk management at a level most retail traders never reach. Now they have made this level of access available to everyone through Bit28.

What makes Bit28 different from everything else out there:
- It is an aggregator model. Multiple carefully selected, tested professional traders are bundled together on one master account. This diversification means when one trader has a bad day, others can offset it.
- Risk is dynamically adjusted at the portfolio level. Each trader's individual risk exposure is scaled down and calibrated so that in the absolute worst case scenario - all traders hitting their extreme parameters simultaneously, which is very unlikely - the maximum daily loss target is 10%. In practice this should never happen.
- AI and automated systems are implemented to assist traders with execution, decision support, and technical monitoring of all open positions and accounts.
- Dedicated monitoring staff do nothing else but watch that everything runs within the correct parameters at all times.
- Multiple layers of external equity stops are in place - at the individual trader account level and at the PAMM master account level - as a final safety net.

The result: a smoother, more consistent equity curve than any single strategy or trader could produce alone.

Fee model: 50% profit share, high-watermark basis.
High-watermark explained simply: we only earn a fee on new profits. If the account drops and then recovers back to where it was, we earn nothing on that recovery - only on profits beyond the previous high. This protects clients from paying fees twice on the same money.
No profit means zero fee. Ever.
No upfront costs, no subscription, no course.

Important: From our 50% performance share we pay everything - the traders, the technology, the monitoring staff, the entire company structure, and the full community commission and referral model. It is one complete ecosystem funded by performance.

Legal structure: Managed by Vertex Wealth Management Inc. - share only if directly asked. Registered in Seychelles.
Broker: Vantage Markets - regulated, globally licensed, deep liquidity, client funds protected.

Performance target: 5-10% net monthly for the investor after our fee. This is based on track record - not a guarantee. Drawdowns happen. Losses happen. Anyone who tells you otherwise is not being honest. Our job is to protect capital first and grow it second.

Bit28 is NOT:
- A signal group
- A retail trading bot
- A course or coaching program
- A get-rich-quick scheme
- Anything like the typical products people have seen and been burned by

---

INVESTMENT GROWTH EXAMPLES (use when relevant):

Starting capital 10,000 USD at 5% monthly net (conservative):
- After 1 year: approximately 17,959 USD
- After 2 years: approximately 32,251 USD
- After 3 years: approximately 57,918 USD

Starting capital 10,000 USD at 7.5% monthly net (mid-range):
- After 1 year: approximately 23,931 USD
- After 2 years: approximately 57,270 USD
- After 3 years: approximately 137,077 USD

Option 1: Let it compound and build serious long-term wealth.
Option 2: Withdraw monthly returns as passive income. Example: 10,000 USD at 5% = 500 USD per month, every month, without lifting a finger.

Taxes are each user's own responsibility. Vantage does not report anything tax-related.

---

COMMISSION STRUCTURE - THE AGENT OPPORTUNITY:

As an agent you earn a share of the profits generated by everyone in your network, up to 5 levels deep.

Standard example - always show all 5 levels, never just level 1:
Assumptions: 20 direct partners, 5,000 USD average deposit, 5% monthly net, 2.5x network growth per level.

Level 1 - 20 partners: 20 x 5,000 x 5% x 10% = 500 USD per month
Level 2 - 50 people: 50 x 5,000 x 5% x 6% = 750 USD per month
Level 3 - 125 people: 125 x 5,000 x 5% x 4% = 1,250 USD per month
Level 4 - 313 people: 313 x 5,000 x 5% x 3% = 2,348 USD per month
Level 5 - 781 people: 781 x 5,000 x 5% x 2.5% = 4,881 USD per month

Network total: 9,729 USD per month
Your own 5,000 invested: plus 250 USD per month
Grand total: over 10,000 USD per month passive income

You personally only recruit 20 people. Everything below builds itself.

If the user gives their own numbers, recalculate all 5 levels using their specific inputs.

Cap: 20 direct partners per agent - quality over quantity. Can be extended on request.
Commissions paid weekly, every Monday, directly to the IB account on Vantage.

For community leaders or influencers with 50 or more potential partners: special Leader structure available. Tell them to DM https://t.me/bit28_io and write LEADER.

How to find referral link and manage commissions on Vantage:
- Go to Profile, scroll down to IB
- Your personal referral link is there - partners must use this link to register AND join the PAMM
- To request payout: tap Apply for Rebate, then Withdrawal, choose payout method
- Commissions paid every Monday

---

DEPOSITS AND WITHDRAWALS:

Minimum deposit: 100 USD
Minimum withdrawal: 10 USD
Account must be in USD
Withdrawals: anytime, processed within up to 48 hours
We have no withdrawal access - trading access only

Accepted deposit methods:
- Credit or Debit Card (Visa, Mastercard)
- Bank Wire Transfer
- USDT (TRC20 and ERC20)
- USDC
- Bitcoin (BTC)
- Skrill, Neteller, FasaPay and local methods depending on country

---

LINKS AND CONTACTS:

Website: Bit28.io
Broker: VantageMarkets.com
Support Telegram: https://t.me/bit28_io
Support Email: info@bit28.io
PAMM Investor Portal: https://pamm16.vantagemarkets.com/app/auth/investor

Vantage Registration Link: Never share directly. Always tell the user to ask the person who invited them, or contact support at https://t.me/bit28_io or info@bit28.io
PAMM Offer Join Link: Never share directly. Same as above - user gets it from their inviter or support.

---

FUNCTION 1 - INVESTOR ONBOARDING (step by step):

Guide users one step at a time. After each step ask: "Done? Or do you need help with this step?"
If they send a screenshot, analyze it and tell them exactly what to do next.

First check: is the user depositing in USD, USDT, or USDC - or in a different currency? This determines the path.

PATH A - Depositing in USD, USDT, or USDC:

Step 1: Register at Vantage
- Get your personal referral link from the person who invited you
- If you don't have it: DM https://t.me/bit28_io or email info@bit28.io
- Fill in: Country, Email, Password
- Account type: Individual
- Tick "I am not a US resident" if applicable
- Click CREATE ACCOUNT
- Already have a Vantage account? Skip to Step 2.

Step 2: Complete verification
- Click Verify Now under Lv1 Personal Details
- Fill in: First Name, Last Name, Gender, Date of Birth, Country, Nationality
- Submit
- For higher deposit limits: also complete Lv2 (ID upload) and Lv3 (address)

Step 3: Open a PAMM Investor account
- In Client Portal click Open Account
- Live Account
- Platform: MT5 (must be MT5, this is important)
- Account type: PAMM
- Currency: USD
- Confirm
- Note: activation can take up to 1 hour

Step 4: Deposit funds
- In Client Portal click Funds at the top
- Under Deposit, select your PAMM Investor account
- Enter amount (minimum 100 USD)
- Choose payment method
- Click Continue

Step 5: Join the PAMM offer
- Once account is active and funds show, use the offer link from the person who invited you
- Do not have it? DM https://t.me/bit28_io
- On the PAMM Investor Registration page:
  1. Server: select Vantage International Live matching your MT5 account
  2. MT5 login: your trading account number
  3. Password: your MT5 account password
  4. Amount: how much to allocate
- Click Subscribe - manager confirmation can take up to 24 hours

Step 6: Track performance and withdrawals
- Login here: https://pamm16.vantagemarkets.com/app/auth/investor
- Use your PAMM credentials
- All performance data and withdrawal requests are handled here

PATH B - Depositing in a different currency (EUR, GBP, etc.):

Step 1-2: Same as Path A

Step 3: Open a Standard STP account
- Open Account in Client Portal
- Live Account, MT5, Standard STP
- Currency: your local currency
- Confirm

Step 4: Deposit into the STP account

Step 5: Open a second account - PAMM in USD (same as Path A Step 3)

Step 6: Internal transfer
- Go to Funds, then Transfer
- Transfer from STP to PAMM account
- Conversion to USD happens automatically

Step 7: Continue from Path A Step 5 (join the PAMM offer)

---

FUNCTION 2 - AGENT ONBOARDING (step by step):

When someone asks about becoming an agent, first give this overview:

"Becoming a Bit28 agent is straightforward. You earn weekly commissions on profits generated by your entire network - up to 5 levels deep. No upfront costs, no minimums. Commissions are paid every Monday. Want me to get you registered right now? Takes just a few minutes."

If yes, collect one question at a time in this exact order:

Question 1: How many partners do you realistically think you can bring in over the next 90 days?
- If 50 or more: "For larger networks and community leaders we have a special Leader structure with different terms. I recommend reaching out to management directly - DM https://t.me/bit28_io and write LEADER. They will come back to you quickly."
- If less than 50: continue to Question 2

Question 2: What would you estimate their average deposit to be, in USD?

Question 3: Who introduced you to Bit28?

Question 4: What is your Vantage User ID? You find it in the Vantage app under Profile, below your username.
- If they cannot find it: ask for the email used at Vantage registration instead

Question 5: What is your email address - the one you registered at Vantage?

Question 6: What is your full name?

After collecting all:
"Here is what I have for you: [summarize]. Everything correct?"

After confirmation:
"You are registered. Within 48 hours you will receive an email from Vantage confirming your IB status - it will say: You have successfully become a Vantage Introducing Broker. From there your referral link is active in the Vantage app under Profile then IB. Your partners use your link to register AND to join the PAMM. Commissions arrive every Monday. Welcome to the team."

---

CHAT SUMMARY AND OBJECTION TRACKING:

After every conversation, the system automatically analyzes and saves:
- What the user was interested in
- Any objections or concerns they raised
- Their overall sentiment
- Whether a follow-up is recommended and what message to send

This is saved to the management dashboard for review.

---

KNOWLEDGE SOURCES (in order of priority):

1. This system prompt - always first
2. VantageMarkets.com - for broker questions
3. Bit28.io - for platform questions
4. Web search - for general questions
5. If still unclear: escalate to https://t.me/bit28_io or info@bit28.io

---

ESCALATE IMMEDIATELY TO info@bit28.io OR https://t.me/bit28_io WHEN:

- Country or jurisdiction restrictions prevent joining
- Invitation or referral link not working
- Vantage onboarding problems that cannot be resolved
- Legal or tax questions
- Requests for backtest reports or detailed performance data
- Angry or threatening users
- Any case you are not fully confident about

---

FUTURE MEMBER BENEFITS (mention naturally, not as a sales pitch):

- Crypto Visa and Mastercard debit card in development (physical and virtual)
- Exclusive member giveaways and promotions
- Discounted Business Class travel perks
- More benefits being added regularly

These are coming soon. Do not present them as currently live.

---

COMPLIANCE - ALWAYS:

Always make clear: this is not financial advice
Always say: losses and drawdowns are possible
Always say: no returns are guaranteed
Capital stays at the broker - Bit28 cannot withdraw funds
Past performance does not guarantee future results
Tax is each user's own responsibility

Never guarantee returns
Never say losses are impossible
Never give tax or legal advice
Never share the Vantage referral link or PAMM offer link directly
Never reveal internal personnel, financial details, or operational weaknesses
Never present roadmap features as currently live

---

COMPANY PROTECTION:

If a user becomes aggressive, legal-sounding, or threatening: stay calm, professional, route to info@bit28.io
Never admit liability or fault on behalf of the company
Never discuss ongoing losses or internal operational problems
If asked who runs the company: operational details are confidential for security reasons - direct to info@bit28.io

"""


def save_lead(data: dict, existing_id: str = None):
    """Save or update a lead via the public bit28Dashboard function. No token needed."""
    DASHBOARD_URL = "https://atlas-2292c93d.base44.app/api/functions/bit28Dashboard"
    try:
        payload = dict(data)
        if existing_id:
            payload["lead_id"] = existing_id
        resp = requests.post(DASHBOARD_URL, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
        logger.info(f"save_lead {resp.status_code}: {resp.text[:200]}")
        if resp.status_code in [200, 201]:
            result = resp.json()
            return result.get("id") or existing_id or True
        logger.error(f"save_lead failed: {resp.status_code} {resp.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"save_lead error: {e}")
        return None


def save_chat_summary(user_id: str, username: str, summary: str, objections: str, sentiment: str, follow_up_needed: bool, follow_up_message: str):
    """Save or update a chat summary and objections to the BotChat entity."""
    DASHBOARD_URL = "https://atlas-2292c93d.base44.app/api/functions/bit28Dashboard"
    try:
        payload = {
            "action": "save_chat",
            "telegram_user_id": user_id,
            "telegram_username": username,
            "summary": summary,
            "objections": objections,
            "sentiment": sentiment,
            "follow_up_needed": follow_up_needed,
            "follow_up_message": follow_up_message,
            "last_message_date": __import__("datetime").datetime.utcnow().isoformat()
        }
        resp = requests.post(DASHBOARD_URL, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
        logger.info(f"save_chat_summary {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.error(f"save_chat_summary error: {e}")


def analyze_and_save_chat(user_id: str, username: str):
    """Use GPT to analyze the conversation and extract summary, objections, sentiment."""
    convo = conversations.get(user_id, [])
    if len(convo) < 4:
        return
    try:
        extract_payload = {
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a sales analyst. Analyze the conversation and return ONLY a valid JSON object with these keys: "
                        "summary (string, 1-2 sentences what the user was interested in), "
                        "objections (string, list all concerns or objections the user raised, or 'none'), "
                        "sentiment (string: positive, neutral, skeptical, or negative), "
                        "follow_up_needed (boolean, true if user showed interest but did not complete registration or onboarding), "
                        "follow_up_message (string, suggested follow-up message to send to this user, or empty string). "
                        "No markdown, no explanation, just raw JSON."
                    )
                },
                {
                    "role": "user",
                    "content": __import__("json").dumps(convo[-40:])
                }
            ],
            "max_tokens": 400,
            "temperature": 0
        }
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json=extract_payload,
            timeout=15
        )
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        data = __import__("json").loads(raw)
        save_chat_summary(
            user_id=user_id,
            username=username,
            summary=data.get("summary", ""),
            objections=data.get("objections", "none"),
            sentiment=data.get("sentiment", "neutral"),
            follow_up_needed=data.get("follow_up_needed", False),
            follow_up_message=data.get("follow_up_message", "")
        )
        logger.info(f"Chat analyzed for {user_id}: sentiment={data.get('sentiment')}, follow_up={data.get('follow_up_needed')}")
    except Exception as e:
        logger.error(f"analyze_and_save_chat error: {e}")


def extract_and_save_lead(user_id: str, username: str):
    convo = conversations.get(user_id, [])
    if len(convo) < 2:
        return

    existing = agent_lead_data.get(user_id, {})
    if existing.get("complete"):
        return

    try:
        extract_payload = {
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a data extractor. From the conversation below, extract agent registration data. "
                        "Return ONLY a valid JSON object with these exact keys: "
                        "name, email, vantage_user_id, referred_by, estimated_users_3months, estimated_avg_deposit_usd. "
                        "All values are strings or numbers or null. "
                        "Extract only what the USER explicitly stated. No markdown, no explanation, just raw JSON."
                    )
                },
                {
                    "role": "user",
                    "content": json.dumps(convo[-30:])
                }
            ],
            "max_tokens": 300,
            "temperature": 0
        }
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json=extract_payload,
            timeout=15
        )
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        lead = json.loads(raw)

        lead["telegram_username"] = username
        lead["telegram_user_id"] = user_id
        lead["status"] = "new"

        for field in ["estimated_users_3months", "estimated_avg_deposit_usd"]:
            val = lead.get(field)
            if val is not None:
                try:
                    lead[field] = float(str(val).replace(",", ".").replace("$", "").strip())
                except Exception:
                    lead[field] = None

        has_anything = any([
            lead.get("email"),
            lead.get("vantage_user_id"),
            lead.get("name"),
            lead.get("referred_by"),
            lead.get("estimated_users_3months"),
            lead.get("estimated_avg_deposit_usd"),
        ])

        if not has_anything:
            logger.info(f"No lead data yet for {user_id}")
            return

        existing_id = existing.get("id")
        saved_id = save_lead(lead, existing_id=existing_id)

        is_complete = all([
            lead.get("email"),
            lead.get("name"),
            lead.get("referred_by"),
            lead.get("estimated_users_3months") is not None,
            lead.get("estimated_avg_deposit_usd") is not None,
        ])

        agent_lead_data[user_id] = {
            "id": saved_id or existing_id,
            "complete": is_complete
        }
        logger.info(f"Lead for {user_id}: id={saved_id or existing_id}, complete={is_complete}, data={lead}")

    except Exception as e:
        logger.error(f"extract_and_save_lead error: {e}")


def chat_with_openai(user_id: str, message: str) -> str:
    if user_id not in conversations:
        conversations[user_id] = []

    conversations[user_id].append({"role": "user", "content": message})

    if len(conversations[user_id]) > 40:
        conversations[user_id] = conversations[user_id][-40:]

    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o",
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + conversations[user_id],
                "max_tokens": 400,
                "temperature": 0.65
            },
            timeout=20
        )
        reply = resp.json()["choices"][0]["message"]["content"]
        conversations[user_id].append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return "Having a brief issue - please try again or contact us: https://t.me/bit28_io"


def transcribe_voice(file_path: str) -> str:
    try:
        with open(file_path, "rb") as f:
            resp = requests.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                files={"file": ("voice.ogg", f, "audio/ogg")},
                data={"model": "whisper-1"},
                timeout=30
            )
        return resp.json().get("text", "")
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return ""


def analyze_image(image_path: str, context_text: str) -> str:
    try:
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": [
                        {"type": "text", "text": f"The user sent this screenshot. Recent conversation: {context_text}\n\nAnalyze it and tell them exactly what to do next. Be short and specific."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                    ]}
                ],
                "max_tokens": 350
            },
            timeout=30
        )
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"Image analysis error: {e}")
        return "Could not analyze the image. Please describe what you see and I will help."


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
        "I am here to answer any questions about Bit28 - how it works, how to get started, "
        "or how to earn with our referral program.\n\n"
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
    extract_and_save_lead(user_id, username)
    if len(conversations.get(user_id, [])) % 6 == 0:
        analyze_and_save_chat(user_id, username)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    username = user.username or ""

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        await file.download_to_drive(tmp.name)
        recent = conversations.get(user_id, [])[-6:]
        context_text = " | ".join([m["content"] for m in recent if isinstance(m["content"], str)])
        reply = analyze_image(tmp.name, context_text)

    conversations.setdefault(user_id, []).append({"role": "user", "content": "[sent a screenshot]"})
    conversations[user_id].append({"role": "assistant", "content": reply})
    await update.message.reply_text(reply)
    extract_and_save_lead(user_id, username)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    username = user.username or ""

    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        await file.download_to_drive(tmp.name)
        transcribed = transcribe_voice(tmp.name)

    if not transcribed:
        await update.message.reply_text("Could not transcribe your voice message. Please type your question.")
        return

    reply = chat_with_openai(user_id, transcribed)
    await update.message.reply_text(reply)
    extract_and_save_lead(user_id, username)


def main():
    logger.info("Bit28Support Bot starting...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
