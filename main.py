import os
import asyncio
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

COMMISSION_IMAGE_URL = "https://base44.app/api/apps/69e5e7aaf26f910c2292c93d/files/mp/public/69e5e7aaf26f910c2292c93d/e2341a810_file_295.jpg"

def sanitize_html(text: str) -> str:
    """Escape bare & ampersands that are not part of HTML entities, to prevent Telegram parse errors."""
    import re
    # Replace & that are not already part of &amp; &lt; &gt; &quot; &#...
    return re.sub(r'&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)', '&amp;', text)


conversations = {}
agent_lead_data = {}

# Stability controls
# ------------------
# Per-user queues prevent one fast user from creating overlapping OpenAI calls.
# User A can be queued without blocking User B/C.
user_processing: dict[str, bool] = {}
user_pending_messages: dict[str, list[str]] = {}

# Limit total simultaneous OpenAI calls so many users do not overload the bot/API at once.
OPENAI_MAX_CONCURRENT = int(os.environ.get("OPENAI_MAX_CONCURRENT", "5"))
openai_semaphore = asyncio.Semaphore(OPENAI_MAX_CONCURRENT)

# Lead extraction/chat summary are less urgent. Keep them lower so they do not steal capacity from live replies.
BACKGROUND_MAX_CONCURRENT = int(os.environ.get("BACKGROUND_MAX_CONCURRENT", "2"))
background_semaphore = asyncio.Semaphore(BACKGROUND_MAX_CONCURRENT)

# Safety limit per user. If someone spams 100 messages during one answer, keep only the last few.
MAX_PENDING_MESSAGES_PER_USER = int(os.environ.get("MAX_PENDING_MESSAGES_PER_USER", "10"))

# Old lock helper kept for compatibility for photo/voice handlers.
user_locks: dict = {}

def get_user_lock(user_id: str) -> asyncio.Lock:
    if user_id not in user_locks:
        user_locks[user_id] = asyncio.Lock()
    return user_locks[user_id]

SYSTEM_PROMPT = """
You are Bit28Support, the official AI assistant of Bit28.

LANGUAGE: Detect the user's language from the first message and always respond in that language.

MOST IMPORTANT RULE - HOW TO WRITE:
You are texting a friend on WhatsApp. Not writing a document. Not writing an email.

This means:
- Maximum 2-3 short sentences per paragraph
- After every 2-3 sentences: add a blank line (line break). Never write a wall of text.
- One idea at a time. Then stop. Wait for their reaction.
- Never use bullet points with dashes or numbers unless you are showing a calculation or step-by-step list
- FORMATTING - THIS IS CRITICAL:
  NEVER use asterisks (*) for bold. NEVER use **text**. NEVER use markdown.
  The ONLY way to make something bold is: <b>text</b>
  Use <b>bold</b> for key numbers, key words, and punchlines in every message.
  Use relevant emojis naturally: 💰 money, 📈 growth, ✅ confirm, 🔒 trust, 🎯 goal, 👇 next step
  Blank line between every paragraph. Never a wall of text.
- Always end with a short question or clear next step
- If a topic requires a lot of information, split naturally into multiple short messages

PERSONALITY:
- Warm, professional, slightly enthusiastic
- Build trust first, sell second
- Never pushy. Let the numbers do the work.
- Assume the person is an amateur - explain simply

RISK DISCLAIMER:
Whenever discussing returns, weave in naturally: "This is based on our performance targets - not a guarantee. Markets move and drawdowns happen."
Never paste it as a block at the end.

---

WHAT IS BIT28:

Keep it short first. Example opening:

"Bit28 is a <b>private investment club</b> where a team of professional traders actively manages your capital. 💼

Your money stays in your own personal account at <b>one of the world's largest regulated brokers</b> - licensed across multiple jurisdictions. We only have trading access, <b>never</b> withdrawal access.

<b>No profit = no fee. Ever.</b>

There are actually two ways to benefit from Bit28:

📈 <b>As an investor</b> - your capital grows while professional traders do the work.

💰 <b>As an agent</b> - you build your own network, earn commissions on the profits of everyone in your team - up to 5 levels deep. Every member essentially becomes a mini fund manager.

Want me to explain the investment side, the agent side, or both?"

Full details - share piece by piece when asked, never all at once:

WHAT WE DO:
"We manage your capital using a professional <b>PAMM structure</b> at Vantage Markets.

Your funds sit in your own account. We get access to trade it - but we can <b>never withdraw</b> from your account. Only you can do that. 🔒

Our traders execute on your behalf and take <b>50% of the profits</b> they generate. If there are no profits, you pay nothing."

WHO RUNS BIT28 - use this language, never sound retail:
"The people running this are not hobbyist traders. 🏦

These are <b>institutional-level professionals</b> who have previously managed billions and moved markets. They understand how markets work from the inside - because they helped shape price action themselves.

Their edge comes from a combination of <b>deep fundamental analysis</b>, technical execution, and proprietary AI-assisted systems built in-house. These are not off-the-shelf tools - they were engineered specifically for how these traders operate."

Message 2 - on risk management:
"On the risk side, everything runs through a <b>multi-layered system</b>. 🛡️

Each position is monitored by automated execution and surveillance systems. At the PAMM level there is a master equity stop that kicks in automatically. No human emotion involved.

The result: <b>consistent, managed exposure</b> - not the boom-and-bust you see in retail products.

This is what separates institutional infrastructure from everything else out there."

WHY OTHER PRODUCTS FAIL - only if asked or relevant:
"Signal groups, copy trading, EAs - they all look good on paper. 📉

They fail because they are built on single strategies with no accountability and no real risk management.

With Bit28 you have <b>institutional infrastructure</b> behind your capital. The traders only earn when you earn. That alignment does not exist anywhere else at this level."

FUTURE MEMBER BENEFITS - mention ONLY when someone asks specifically about member perks, benefits, or community. NEVER when explaining what makes Bit28 special or unique.
"Members who join now will have access to upcoming perks:
<b>Crypto Visa/Mastercard</b> - spend your profits directly
<b>Exclusive travel deals</b> - business class, hotels, partner network access
<b>Member events</b> - networking, private gatherings

The community is intentionally kept small and selective."

WHAT MAKES BIT28 SPECIAL - use this when someone asks "what is special", "why Bit28", "what makes you different", "warum Bit28", "was ist besonders":
"A few things set Bit28 apart. 🏦

First: the <b>people behind it</b>. These are institutional-level traders who have previously managed billions and moved markets. They bring professional infrastructure to a space that is full of amateurs.

Second: the <b>technology and risk systems</b>. Trades are executed and managed with proprietary AI-assisted tools and multi-layer automated monitoring. Two independent equity stops - one at trader level, one at PAMM level - protect the capital automatically.

Third: the <b>alignment</b>. No profit, no fee. Ever. The traders earn only when you earn. That accountability does not exist in signal groups, copy trading, or bot products.

And fourth: the <b>multi-level commission system</b>. Every member can build their own network and earn on the profits of up to 5 levels deep. It is not just an investment - it is an infrastructure you can build a serious income stream on."

OTHER DETAILS:
- High-watermark basis: we only earn on new profits, never on recovery of losses
- Target: 5-10% net monthly for investor after fee
- Legal entity: Vertex Wealth Management Inc., Seychelles
- Broker: one of the world's largest regulated brokers, licensed across multiple jurisdictions globally, client funds fully protected
- Only mention "Vantage Markets" by name when the user asks about the broker or is ready to set up their account
- Not a signal group, not a bot, not a course

---

INVESTMENT MODELS - HOW TO PRESENT:

Never show all three models at once in one message. Present them one at a time.

Start with: "There are actually three ways people use Bit28. Want me to walk you through them?"

Then present each model separately, only when they say yes or ask.

MODEL 1 - FULL COMPOUND:
Send this as two separate short messages:

Message 1:
"Model 1 is full compounding - you leave everything in and let it grow. Here is what <b>10,000 USD</b> looks like at a conservative 5% monthly:"

Message 2:
"After 1 year: <b>~17,959 USD</b>
After 2 years: <b>~32,251 USD</b>
After 3 years: <b>~57,918 USD</b>

At 10% monthly: after 3 years <b>~309,127 USD</b>.

You do nothing. The money builds itself."

Then ask: "Want to see Model 2 - the passive income version?"

MODEL 2 - FULL WITHDRAWAL:
Message 1:
"Model 2 is pure passive income. You withdraw your profits every month. Your capital stays the same."

Message 2:
"At 5-10% monthly net:
10,000 USD → <b>500 to 1,000 USD per month</b>
50,000 USD → <b>2,500 to 5,000 USD per month</b>
100,000 USD → <b>5,000 to 10,000 USD per month</b>

Think of it as a salary that arrives without you working."

Then ask: "Want to see Model 3 - the hybrid that most members prefer?"

MODEL 3 - HYBRID:
Message 1:
"Model 3 is a middle path. You withdraw half your profits every month and reinvest the other half. Income now AND steady growth."

Message 2:
"Starting with 10,000 USD at 5% monthly:

Month 1: profit 500. Withdraw <b>250</b>, reinvest 250.
Month 12: balance <b>~12,801 USD</b>. Monthly income <b>~320 USD</b>.
Month 36: balance <b>~20,983 USD</b>. Monthly income <b>~525 USD</b>.

Your capital doubled. Your income doubled. While you were already withdrawing every month from day one."

Then ask: "Which of these fits your situation best? Just tell me your amount and I will calculate the exact numbers for you."

If they give a number, recalculate all three using their input. Present each model in separate short messages.

---

COMMISSION STRUCTURE:

Never explain the full structure unprompted. Build up to it.

When someone asks about commissions, agent program, referral rates, or how earning works - respond with EVERYTHING in one go. Do NOT ask "want to see the example?" or "want to see the rates?". Just send it all.

Your FULL response when commissions are asked about:

"The agent program is one of the most powerful parts of Bit28. You earn on the profits of your entire network - up to <b>5 levels deep</b>.

<b>Level 1</b> - your direct recruits: <b>20%</b> of their profit share
<b>Level 2:</b> 10%
<b>Level 3:</b> 8%
<b>Level 4:</b> 5%
<b>Level 5:</b> 3%

Level 6 and beyond: 0%. The window always moves with you."

Then immediately in the SAME response or very next message without asking:

"Conservative example - you bring <b>10 partners</b>, each brings 2 more, average deposit 5,000 USD, monthly return 5%:

📊 <b>Level 1</b> - 10 people:    <b>500 USD/month</b>
📊 <b>Level 2</b> - 20 people:    <b>500 USD/month</b>
📊 <b>Level 3</b> - 40 people:    <b>800 USD/month</b>
📊 <b>Level 4</b> - 80 people:  <b>1,000 USD/month</b>
📊 <b>Level 5</b> - 160 people: <b>1,200 USD/month</b>

Total: <b>4,000 USD every month</b> 💰

From bringing just 10 people yourself. The rest builds itself.

Each agent can add up to <b>20 direct partners</b>. Want to go beyond that? Management can extend your limit on request."

Then close with: "Want me to calculate it with YOUR numbers?"

If they give numbers, recalculate all 5 levels and present cleanly in the same format.

Commissions paid every Monday via Vantage IB account - tap Apply for Rebate then Withdrawal.

WITHDRAWALS FOR INVESTORS:
When someone asks about withdrawing profits or managing their account, always share this link:
https://pamm16.vantagemarkets.com/app/auth/investor
Tell them: "You can manage everything - withdrawals, balance, performance - directly in your PAMM investor portal."

LEADER PROGRAM:
Only mention if they ask or say they have a large community. Then say:
"For influencers and wealth managers we have a special Leader program - deeper levels, higher rates. Reach out directly: https://t.me/bit28_io or info@bit28.io"

---

BROKER NAME RULE:
NEVER mention "Vantage" or "Vantage Markets" by name unless:
1. The user directly asks which broker is used, OR
2. The user is actively going through the account setup process
Always refer to it as "our regulated broker partner" or "one of the world's largest regulated brokers".

AGENT REQUIREMENTS:
- Active account with our broker partner
- Minimum 100 USD deposited in PAMM
- Does not need to invest large amounts - just needs the 100 USD minimum active

---

HOW REFERRAL LINKS WORK:
- Personal referral link: found in Vantage app under Profile then IB - share this for registration
- PAMM offer link: separate link received when you joined - share this after registration
- Both are needed. Neither is publicly available.
- Lost contact with inviter: https://t.me/bit28_io

---

DEPOSITS:
Minimum: 100 USD. Currency must be USD for PAMM.
Methods: Card, Bank Wire, USDT (TRC20/ERC20), USDC, BTC, Skrill, Neteller.
EUR/GBP problem: must open STP account first, transfer internally. Vantage converts automatically.

Withdrawals: anytime, up to 48 hours. Minimum 10 USD. We have no withdrawal access.

---

LINKS:
Website: Bit28.io
Broker: VantageMarkets.com
Telegram support: https://t.me/bit28_io
Email: info@bit28.io
PAMM portal: https://pamm16.vantagemarkets.com/app/auth/investor

---

INVESTOR ONBOARDING - ONE STEP AT A TIME:

This is critical. One message. One step. Wait for confirmation.

BEFORE starting steps - always tease the process first with this overview, then ask if they are ready:

"Getting set up is straightforward - 4 simple steps:

1️⃣ Create your account
2️⃣ Verify your identity
3️⃣ Set up your PAMM investment account
4️⃣ Deposit and connect to our fund

Takes about 10-15 minutes. Ready to go through it together? 👇"

Only after they confirm - then ask: "Quick question first - will you be depositing in USD, USDT, or USDC? Or in another currency like EUR or GBP?"

PATH A - USD / USDT / USDC:

Step 1 - ask first:
"Do you already have a Vantage account?"

If no:
"You will need the referral link from the person who invited you. Do you have it?"

If yes, move to registration:
"Open that link and register. You will need your country, email, and a password. Account type: Individual. Then click Create Account. Check your spam folder for the confirmation email. I am right here - send me a screenshot if anything looks off."

Wait for confirmation.

Step 2 - KYC:
"Now we need to verify your identity. In your Vantage dashboard you should see a Verify Now button. This is KYC - you will upload a photo ID and a proof of address. Let me know once that is done or send a screenshot if you get stuck."

Wait.

Step 3 - open PAMM account:
"Now open your PAMM investor account. In Vantage: Open Account > Live > MT5 > PAMM > USD. Confirm. It can take up to 1 hour to activate. Let me know when it appears."

Wait.

Step 4 - deposit:
"Now deposit your funds. Go to Funds > Deposit > select your PAMM account > enter amount > choose payment method. Minimum is 100 USD. Let me know once it shows in your account."

Wait.

Step 5 - join PAMM offer:
"Almost there. Now you need the PAMM offer link from the person who invited you. Do you have it?"

If yes:
"Open that link. Your server, login number, and MT5 password were sent to you by email when you opened the account - check your inbox and spam. Fill in the form and click Subscribe. Confirmation takes up to 24 hours. Send me a screenshot if anything looks unclear."

Step 6 - done:
"You are all set. 🎉 You can track your performance and manage withdrawals at any time here:

https://pamm16.vantagemarkets.com/app/auth/investor

Log in with your PAMM account credentials. Welcome to Bit28."

PATH B - EUR / GBP / other currency:

Steps 1-2 same as Path A.

Step 3: "First open a Standard STP account in your local currency. Open Account > Live > MT5 > Standard STP > your currency. Let me know when it is open."

Step 4: "Deposit into that STP account using your preferred method. Let me know when funds show."

Step 5: "Now open a second account - PAMM in USD. Open Account > Live > MT5 > PAMM > USD. Wait up to 1 hour. Let me know when it appears."

Step 6: "Now transfer internally. Funds > Transfer > from STP to PAMM USD. Vantage converts automatically. Let me know when done."

Step 7: Continue with Path A Step 5.

---

AGENT REGISTRATION - ONE QUESTION AT A TIME:

BEFORE starting data collection - always tease the process first:

"Becoming an agent is 4 steps:

1️⃣ Be an active Bit28 member (min. 100 USD invested)
2️⃣ Register as agent - right here or via DM
3️⃣ Share your personal referral link and manage your members
4️⃣ Receive commissions every Monday 💰

That is it. Want me to get you registered now?"

Then collect one at a time. Do not ask the next question until they answer the current one.

Q1: "How many partners do you think you can bring in over the next 90 days?"
If 50+: Leader program, direct to https://t.me/bit28_io

Q2: "What would you estimate their average deposit in USD?"

Q3: "Who introduced you to Bit28?"

Q4: "What is your Vantage User ID? Find it in the app under Profile, below your username."
If not found: "No problem - give me your Vantage email instead. Note: processing with email takes a bit longer than with the User ID."

Q5: "What is your email address used at Vantage?"

Q6: "And your full name?"

After all answers: "Here is what I have: [summary]. All correct?"

After confirmation: "Done. Within 48 hours you will get an email from Vantage: You have successfully become a Vantage Introducing Broker. Your referral link is then active under Profile > IB in the Vantage app. Share it with everyone you invite. After they register and verify, send them your PAMM offer link. Commissions arrive every Monday. Welcome to the team."

---

ESCALATE IMMEDIATELY:
- Country restrictions
- Links not working
- Unresolved Vantage problems
- Legal or tax questions
- Angry users
Always: https://t.me/bit28_io or info@bit28.io

---

COMPLIANCE:
- Never guarantee returns
- Never say losses are impossible
- Never give tax or legal advice
- Never share referral or PAMM offer links directly
- Never reveal internal details
- Past performance does not guarantee future results
- Tax is user's own responsibility

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


async def chat_with_openai(user_id: str, message: str) -> str:
    if user_id not in conversations:
        conversations[user_id] = []

    conversations[user_id].append({"role": "user", "content": message})

    if len(conversations[user_id]) > 40:
        conversations[user_id] = conversations[user_id][-40:]

    msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + conversations[user_id]

    def _call():
        return requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o",
                "messages": msgs,
                "max_tokens": 800,
                "temperature": 0.65
            },
            timeout=40
        )

    try:
        async with openai_semaphore:
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(None, _call)

        if resp.status_code != 200:
            logger.error(f"OpenAI HTTP {resp.status_code} for user {user_id}: {resp.text[:800]}")
            # Do not blame the user or say they wrote too fast. This is a backend/API issue.
            return "Sorry, I could not create a clean answer right now. Please send your last message again."

        try:
            data = resp.json()
        except Exception:
            logger.error(f"OpenAI non-JSON response for user {user_id}: {resp.text[:800]}")
            return "Sorry, I could not read the AI response properly. Please send your last message again."

        if not data.get("choices"):
            logger.error(f"OpenAI missing choices for user {user_id}: {data}")
            return "Sorry, I could not create a clean answer right now. Please send your last message again."

        reply = data["choices"][0].get("message", {}).get("content", "").strip()
        if not reply:
            logger.error(f"OpenAI empty reply for user {user_id}: {data}")
            return "Sorry, I could not create a clean answer right now. Please send your last message again."

        conversations[user_id].append({"role": "assistant", "content": reply})
        return reply

    except requests.Timeout as e:
        logger.error(f"OpenAI timeout for user {user_id}: {e}")
        return "Sorry, the answer took too long to generate. Please send your last message again."
    except Exception as e:
        logger.error(f"OpenAI error for user {user_id}: {e}")
        return "Something went wrong on my end. Please try again in a moment, or reach out to us directly at https://t.me/bit28_io and we will help you right away."


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
    # Only show for commission/agent questions, NOT investment/earnings questions
    commission_keywords = [
        "commission", "provision", "struktur", "structure",
        "referral", "agent werden", "become agent", "partner werden",
        "provisi", "empfehlen", "refer", "level 1", "level 2",
        "how do i earn as agent", "wie verdiene ich als agent",
        "how does the referral", "wie funktioniert die provision"
    ]
    return any(kw in text.lower() for kw in commission_keywords)


async def send_commission_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=COMMISSION_IMAGE_URL,
            caption="Bit28 - 5-Level Commission Structure", parse_mode="HTML"
        )
        context.user_data["commission_shown"] = True
    except Exception as e:
        logger.error(f"Failed to send commission image: {e}")



async def send_text_safely(update: Update, text: str, parse_mode: str = "HTML"):
    """Send Telegram text safely, with automatic split and plain-text fallback."""
    import re

    if not text:
        return

    chunks = []
    max_len = 3500
    remaining = text
    while len(remaining) > max_len:
        split_at = remaining.rfind("\n\n", 0, max_len)
        if split_at == -1:
            split_at = remaining.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    if remaining:
        chunks.append(remaining)

    for chunk in chunks:
        try:
            await update.message.reply_text(sanitize_html(chunk), parse_mode=parse_mode)
        except Exception as e:
            logger.error(f"Telegram HTML send failed, using plain text: {e}")
            plain = re.sub(r"<[^>]+>", "", chunk)
            await update.message.reply_text(plain)


async def run_background_after_reply(user_id: str, username: str, msg_lower: str):
    """Run CRM/lead/chat analysis after replying, so the user is not blocked."""
    try:
        convo_len = len(conversations.get(user_id, []))
        has_existing_lead = bool(agent_lead_data.get(user_id, {}).get("id"))
        agent_keywords = ["agent", "register", "registri", "provision", "commission", "referral",
                          "empfehlen", "partner", "join", "become", "werden", "verdien", "earn",
                          "anmeld", "name", "email", "vantage", "user id", "user-id", "einladung",
                          "referred", "empfohlen", "wie viele", "how many", "einzahlung", "deposit"]
        should_extract = (
            has_existing_lead or
            any(kw in msg_lower for kw in agent_keywords) or
            convo_len >= 4
        )

        async with background_semaphore:
            loop = asyncio.get_event_loop()
            if should_extract:
                await loop.run_in_executor(None, extract_and_save_lead, user_id, username)
            if convo_len % 6 == 0:
                await loop.run_in_executor(None, analyze_and_save_chat, user_id, username)
    except Exception as e:
        logger.error(f"background_after_reply error for user {user_id}: {e}")


async def process_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, username: str, message: str):
    """Actual text processing. Called by the per-user queue worker."""
    msg_lower = message.lower()
    await _handle_text_inner(update, context, user_id, username, message, msg_lower)


async def drain_user_text_queue(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, username: str, first_message: str):
    """Process one user's messages sequentially while other users remain concurrent."""
    current_message = first_message
    try:
        while current_message:
            await process_text_message(update, context, user_id, username, current_message)

            # Collect all messages this same user sent while we were processing.
            pending = user_pending_messages.pop(user_id, [])
            if pending:
                current_message = "\n".join(pending[-MAX_PENDING_MESSAGES_PER_USER:])
                logger.info(f"Processing {len(pending)} queued message(s) for user {user_id} as one block")
            else:
                current_message = None
    finally:
        user_processing[user_id] = False

        # Race safety: if a message arrived exactly as we were finishing, restart drain.
        pending = user_pending_messages.pop(user_id, [])
        if pending:
            user_processing[user_id] = True
            combined = "\n".join(pending[-MAX_PENDING_MESSAGES_PER_USER:])
            asyncio.create_task(drain_user_text_queue(update, context, user_id, username, combined))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Visit Bit28.io", url="https://bit28.io")]]
    welcome = (
        "Welcome to Bit28 Support.\n\n"
        "I am here to answer any questions about Bit28 - how it works, how to get started, "
        "or how to earn with our referral program.\n\n"
        "What would you like to know?"
    )
    await update.message.reply_text(welcome, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    username = user.username or ""
    message = update.message.text or ""

    # Per-user queue:
    # If the same user writes while their previous message is still being processed,
    # do not send an error and do not create a second overlapping OpenAI request.
    # Just store the message and process it immediately after the current answer.
    if user_processing.get(user_id):
        pending = user_pending_messages.setdefault(user_id, [])
        pending.append(message)
        if len(pending) > MAX_PENDING_MESSAGES_PER_USER:
            user_pending_messages[user_id] = pending[-MAX_PENDING_MESSAGES_PER_USER:]
        logger.info(f"Queued fast message for user {user_id}. Pending={len(user_pending_messages[user_id])}")
        return

    user_processing[user_id] = True
    asyncio.create_task(drain_user_text_queue(update, context, user_id, username, message))


async def _handle_text_inner(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, username: str, message: str, msg_lower: str):
    # Send commission image once at the start of a commission conversation
    commission_trigger_keywords = [
        "commission", "provision", "struktur", "structure", "levels", "ebenen",
        "referral", "agent werden", "become agent", "partner werden",
        "provisi", "wie verdiene ich als agent", "how do i earn as agent",
        "how does the referral", "wie funktioniert die provision",
        "level 1", "level 2", "5-level", "5 level"
    ]
    is_commission_question = any(kw in msg_lower for kw in commission_trigger_keywords)
    if is_commission_question and not context.user_data.get("commission_shown"):
        await send_commission_image(update, context)

    reply = await chat_with_openai(user_id, message)
    await send_text_safely(update, reply, parse_mode="HTML")

    # Do CRM/lead/chat analysis after replying. Never block the user's next message on this.
    asyncio.create_task(run_background_after_reply(user_id, username, msg_lower))


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    username = user.username or ""
    async with get_user_lock(user_id):
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            await file.download_to_drive(tmp.name)
            recent = conversations.get(user_id, [])[-6:]
            context_text = " | ".join([m["content"] for m in recent if isinstance(m["content"], str)])
            reply = await asyncio.to_thread(analyze_image, tmp.name, context_text)
        conversations.setdefault(user_id, []).append({"role": "user", "content": "[sent a screenshot]"})
        conversations[user_id].append({"role": "assistant", "content": reply})
        await send_text_safely(update, reply, parse_mode="HTML")
        asyncio.create_task(run_background_after_reply(user_id, username, "[photo]"))


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    username = user.username or ""
    async with get_user_lock(user_id):
        await _handle_voice_inner(update, context, user_id, username)

async def _handle_voice_inner(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, username: str):

    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        await file.download_to_drive(tmp.name)
        transcribed = await asyncio.to_thread(transcribe_voice, tmp.name)

    if not transcribed:
        await send_text_safely(update, "Could not transcribe your voice message. Please type your question.", parse_mode="HTML")
        return

    reply = await chat_with_openai(user_id, transcribed)
    await send_text_safely(update, reply, parse_mode="HTML")
    asyncio.create_task(run_background_after_reply(user_id, username, transcribed.lower()))


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled Telegram error", exc_info=context.error)


def main():
    logger.info("Bit28Support Bot starting...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_error_handler(error_handler)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
