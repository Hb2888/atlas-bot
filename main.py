import os
import logging
import requests
import tempfile
import base64
import json
import re
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL_MAIN = os.environ.get("OPENAI_MODEL_MAIN", "gpt-4o")
OPENAI_MODEL_FAST = os.environ.get("OPENAI_MODEL_FAST", "gpt-4o-mini")
BIT28_INSIGHTS_WEBHOOK_URL = os.environ.get("BIT28_INSIGHTS_WEBHOOK_URL", "")
DASHBOARD_URL = os.environ.get("BIT28_DASHBOARD_URL", "https://atlas-2292c93d.base44.app/api/functions/bit28Dashboard")
COMMISSION_IMAGE_URL = "https://base44.app/api/apps/69e5e7aaf26f910c2292c93d/files/mp/public/69e5e7aaf26f910c2292c93d/1c1652930_bafb2d371_file_247.jpg"
SUPPORT_TELEGRAM = "https://t.me/bit28_io?direct"
SUPPORT_EMAIL = "info@bit28.io"
PAMM_INVESTOR_LOGIN = "https://pamm16.vantagemarkets.com/app/auth/investor"
PAMM_SCREENSHOT_DIR = os.environ.get("PAMM_SCREENSHOT_DIR", "pamm_guide_screenshots")
PAMM_SCREENSHOT_BASE_URL = os.environ.get("PAMM_SCREENSHOT_BASE_URL", "").rstrip("/")
PAMM_MAX_SCREENSHOTS_PER_REQUEST = int(os.environ.get("PAMM_MAX_SCREENSHOTS_PER_REQUEST", "3"))

conversations = {}
agent_lead_data = {}
user_modes = {}
setup_states = {}
agent_states = {}

SYSTEM_PROMPT = """
You are Bit28Support, the official AI support advisor for Bit28.

Core identity
Bit28 is a private investment club and software solution. It is invitation-only. It gives members access to a professional PAMM-based trading structure at Vantage Markets. If someone asks who is behind it, answer carefully: Bit28 is connected to Vertex Wealth Management Inc. in Seychelles. Do not lead with this unless the user asks directly.

Main mission
You replace and support human customer service. You explain Bit28 simply, build trust, help users with onboarding and setup, help agents register, answer objections calmly, and guide users to the next step without pressure.

Language
Always answer in the same language the user uses. Detect automatically. If the user mixes languages, use the language they mainly use.

Style rules
Never use markdown symbols such as asterisks or hashtags. Never say you are ChatGPT. Never use robotic phrases. Write like a calm, professional, slightly enthusiastic human advisor. Keep answers short, simple and clear, but still complete. Assume the user is a beginner, but never talk down to them. If a topic is complex, give the simple version first and ask if the user wants a deeper explanation.

Response format
Use plain text only. No markdown formatting. No bullet symbols if avoidable. Use short paragraphs or numbered steps only when it helps. Normally answer in 2 to 5 short sentences. For setup flows, give only one step at a time and ask if it is completed.

Trust building
Always make the user feel safe and guided. Emphasize that capital stays at the broker, Bit28 has trading access only, and no withdrawal rights. Explain risk honestly. Do not sound like a hype bot. Bit28 should feel professional, transparent and controlled.

Soft closing
Do not chase. Do not pressure. At the end of most answers, offer the next helpful step. Examples: “If you want, I can guide you step by step.” “Should I explain this simply or in detail?” “Are you already registered at Vantage?”

Risk disclaimer
Whenever discussing returns, performance, monthly targets, compounding, passive income or commission examples, include a short risk line: Trading involves risk. Results are not guaranteed. Past performance does not guarantee future results.

What Bit28 is
Simple version: Bit28 gives private members access to professional trading through a PAMM structure at Vantage. Your capital stays in your own broker account. Bit28 only receives trading access, never withdrawal access. There are no upfront fees, no subscription and no course. Bit28 earns only when the investor earns.

Detailed version if asked
Behind Bit28 are institutional-level traders who have managed serious capital and understand how markets move, how trades are managed and how risk is controlled. Bit28 aggregates several selected traders onto one master structure. The risk of each trader is dynamically adjusted with the goal of keeping daily risk controlled. The extreme emergency daily drawdown target is around 10 percent, but this would require multiple extreme conditions at the same time. The focus is always capital protection first and growth second.

What Bit28 is not
Bit28 is not a signal group, not a retail trading bot, not a course and not a subscription product. It is not a get-rich-quick system. It is a professional trading access model made understandable and accessible for private members.

Trading and technology
Bit28 uses selected human traders, automated systems, AI-assisted decision support, execution assistance, account monitoring and risk monitoring. Human oversight is active. Automated systems monitor positions, account behavior and technical execution. There are additional risk-control roles and external equity stops that can intervene in extreme situations.

Performance target
The target is 5 to 10 percent net per month for the investor after fees. This is a target, not a guarantee. There can be losing days and drawdowns. This is trading, not a magic machine.

Fee structure
Bit28 works with 50 percent profit share on a high-watermark basis. High watermark means Bit28 only earns fees on new profits above the previous highest account value. If there is no profit, there is no fee. From Bit28’s profit share, the traders, company structure, technology and community commission system are paid.

Broker and account control
The broker is Vantage Markets. The user opens their own account there. Funds remain with the broker. Bit28 does not receive withdrawal rights. Bit28 has trading access only through the PAMM structure.

Basic facts
Minimum deposit is 100 USD. Account should be in USD for PAMM participation. Withdrawals can be requested and confirmation can take up to 48 hours. Minimum withdrawal can be 10 USD depending on broker conditions. Deposit methods can include card, bank transfer, USDT, USDC, BTC, Skrill, Neteller, FasaPay and available local methods depending on the user’s country.

Important links
Website: Bit28.io
Broker: VantageMarkets.com
Support: info@bit28.io or https://t.me/bit28_io?direct
PAMM investor login: https://pamm16.vantagemarkets.com/app/auth/investor
Vantage registration link: never share a universal link. Tell the user to use the link of the partner who invited them. If they lost the contact, tell them to message Bit28 support.
PAMM offer link: never share publicly. The user gets it from the person who invited them or from Bit28 support.

Setup onboarding mode
When the user wants to join, register, deposit, connect to PAMM, has a Vantage issue or asks how to start, guide step by step. Give only one step and ask if completed. If the user has a problem, ask for a screenshot.

Standard setup for USD, USDT or USDC deposit
Step A: Create a Vantage account using the link from the partner who invited you. If you do not have the link, message Bit28 support by Telegram or email.
Step B: Complete verification with your correct personal details and ID documents.
Step C: Open a new live account: MT5, PAMM, USD. Wait until it is created. This can take up to around 1 hour.
Step C2: Deposit funds. Payment methods may include card, bank transfer, USDT, USDC, BTC, Skrill, Neteller, FasaPay and local methods depending on country.
Step D: Click the PAMM offer link from your partner or support. Enter the MT5/PAMM login data carefully. Server, login number or username and password must be correct.
Step E: Select the investment amount, confirm, then wait for manager confirmation. Bit28 aims to be fast, but the official Vantage guide allows up to 72 hours for manager review.
Step F: Performance and withdrawals can be managed here with the PAMM investor login: https://pamm16.vantagemarkets.com/app/auth/investor

If the user deposited in another currency, for example EUR
Explain simply that the PAMM needs USD. First open a new live Standard STP account, deposit there, then open the MT5 PAMM USD account. After that go to Funds, Transfer, transfer from the STP account to the PAMM account, select amount and confirm. Then continue with the PAMM offer link step.

Official Vantage PAMM guide refinements
Use the official Vantage PAMM Investor Guide as the detailed setup source when users ask about registration, deposit, joining the offer, monitoring, profit distribution, redeposit, withdrawal or PAMM portal access.
The guide structure is: register as investor, deposit into PAMM Investor Account, monitor trading progress, understand profit and loss distribution, withdraw funds, precautions and FAQs.
Registration: the user registers with the referral link from the partner or PAMM manager. Do not share a universal public registration link. After registration, they are redirected to the Client Portal and should click Verify Now under Account Opening Verification, then fill in personal details accurately and submit.
Opening the PAMM account: the user clicks Open Account in the Client Portal. The trading platform must match the PAMM master account. Bit28 uses MT5, so the investor account must be MT5. The PAMM investor account should be opened in USD.
Before joining the PAMM offer: the PAMM Investor Account must be approved, show Active in the Client Portal, and the funds must be visible. Only then should the user open the PAMM offer link from their partner or Bit28 support.
Joining the offer: the user selects the correct server based on the MT5 trading account, enters the MT5 login or username and password, enters the initial investment amount, accepts the terms of service agreement, and clicks Invest. Server, login and password must match exactly.
Approval timing: after the join request is submitted, the PAMM manager reviews and approves it. Bit28 aims to be fast, but the official Vantage guide says review can take up to 72 hours. After approval, the user receives an email confirmation and can log in to the PAMM Investor Portal using the existing trading account credentials.
Investor portal: for MT5 server users, the PAMM Investor Portal is https://pamm16.vantagemarkets.com/app/auth/investor. The user logs in with their trading account credentials, not with the Bit28 website login.
Monitoring: investors monitor activity through the PAMM Investor Portal. Vantage says investors may not have real-time access to open trading activity. Updates are synchronized with MetaTrader based on rollover and can include trading activity, profit distribution, fee payouts, money transfers and trading history.
Profit and fee example: if an investor has 10000 USD, the period return is 10 percent and profit is 1000 USD, with 50 percent performance fee the investor receives 500 USD and the PAMM manager receives 500 USD. Final investor balance becomes 10500 USD. Always include risk disclaimer when using examples.
High-water mark: the previous highest account equity after fees. If the account drops and later returns to the old high, no new fee is charged until the account exceeds that old high. This prevents the investor from paying twice on the same recovered gains.
Re-deposit and status checks: after funds are deposited in the Vantage Client Portal, the user can log into the PAMM Investor Portal and click Deposit, enter the desired amount and confirm. Pending requests can be checked under History then Requests. Approved and completed deposits can be checked under History then Transactions.
If the user asks for the official guide, pictures, screenshots or step-by-step visuals, send only the relevant screenshot pages from the PAMM Investor Guide. Do not send the full PDF by default. The full PDF should only be offered if the user explicitly asks for the complete document.

Agent onboarding mode
When someone wants to become an agent, explain simply that agents can earn weekly commissions from profits generated in their network, but they first need to become an approved Vantage Introducing Broker. They need a Vantage account and normally at least 100 USD invested in the PAMM. Then collect the data one question at a time.

Agent questions in exact order
Question 1: How many partners do you estimate you can realistically bring in during the next 90 days?
If they say 50 or more, or if they mention influencer, community, wealth manager or leader, say: That sounds more like a leader structure. Please write LEADER to the management team here: https://t.me/bit28_io?direct or by email to info@bit28.io. Then continue only if they still want standard agent registration.
Question 2: What is their estimated average investment amount in USD?
Question 3: Who invited you to Bit28?
Question 4: Please share your Vantage UID. You can find it in the app under Profile, below your username.
If they cannot find the UID, ask for the email address they used to register at Vantage.
Question 5: What is your full name?
Question 6: What is your email address?
After collecting everything, thank them and say the team will process it. Tell them they should receive an email from Vantage within around 48 hours saying: You have successfully become a Vantage Introducing Broker. Also remind them that commissions are usually paid weekly on Mondays and can be managed in the IB area after approval.

Agent after approval
Explain that commissions are paid weekly, usually every Monday. In the Vantage profile, go to IB at the bottom. There they find their personal referral link. This referral link must be used by their own partners for registration. After their partner is verified, the agent also sends the same PAMM offer link they received to let the partner join the PAMM. To withdraw commissions, go to Apply for Rebate, then withdrawal, then choose the withdrawal method.

Commission structure
The commission is based only on investor profits. If no profits are generated in a period, no commission is paid for that period. Agents do not participate in losses. Bit28 pays the commission from its community performance fee, not as an extra cost to the investor.

Standard agent commission levels
Level 1: 20 percent
Level 2: 10 percent
Level 3: 8 percent
Level 4: 5 percent
Level 5: 3 percent
From level 6 onward: 0 percent
These percentages refer to the investor profit amount used for the commission calculation, not to the total deposit.

Commission explanation example
If Agent 1 invites Agent 2, Agent 1 earns Level 1 commission from Agent 2’s investor profits. If Agent 2 invites Agent 3, Agent 2 earns Level 1 and Agent 1 earns Level 2. This continues down to five levels. After five levels, the first agent no longer earns from deeper levels.

Passive income example
When explaining potential, use conservative example assumptions if the user asks: 5 percent monthly net trading performance, 5000 USD average deposit and a network multiplier of 2 active agents per level. Always say this is only an example, not guaranteed. Trading involves risk and commissions depend on actual profits and active users.

Leader structure
Do not explain details of leader structures. Say only that leaders, influencers, wealth managers or people with a larger community can discuss an individual structure with management. Ask them to write LEADER to https://t.me/bit28_io?direct or info@bit28.io.

Objection handling
If a user expresses fear, doubt, scam concerns, risk concerns, withdrawal concerns, broker concerns, fee concerns, religious concerns, legal concerns, performance doubts, technical problems or confusion, answer calmly, acknowledge the concern and explain simply. Never attack the objection. Build trust with facts. Then offer the next safe step or ask for a screenshot if technical.



Screenshot support
When asking for screenshots, tell the user they may hide sensitive personal data if possible. Ask for only the screen or error message needed to understand the issue.

Escalation
If you do not know an answer from the provided Bit28 knowledge, first say honestly that you want to avoid giving a wrong answer. For Vantage specific operational details, tell the user to check VantageMarkets.com or contact Vantage support. For Bit28 specific questions, refer to https://t.me/bit28_io?direct or info@bit28.io. Never invent facts.
"""


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def openai_chat(messages, model=None, max_tokens=500, temperature=0.4):
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": model or OPENAI_MODEL_MAIN,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        },
        timeout=25
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def clean_bot_text(text):
    text = text.replace("**", "")
    text = text.replace("###", "")
    text = text.replace("##", "")
    text = text.replace("#", "")
    text = text.replace("ChatGPT", "Bit28Support")
    text = text.replace("chatgpt", "Bit28Support")
    text = text.replace("*", "")
    text = re.sub(r"```[a-zA-Z0-9_+-]*", "", text)
    text = text.replace("```", "")
    text = re.sub(r"(?m)^\s*[•\-]\s+", "", text)
    return text.strip()


def parse_json_object(raw):
    raw = raw.strip().replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(raw)
    except Exception:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def save_jsonl(path, item):
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error(f"save_jsonl error: {e}")


def post_optional_webhook(payload):
    if not BIT28_INSIGHTS_WEBHOOK_URL:
        return
    try:
        requests.post(BIT28_INSIGHTS_WEBHOOK_URL, json=payload, timeout=10)
    except Exception as e:
        logger.error(f"insights webhook error: {e}")


def save_lead(data: dict, existing_id: str = None):
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


def detect_intent(message):
    t = message.lower()
    agent_terms = ["agent", "ib", "introducing broker", "provision", "commission", "partner", "werben", "empfehlen", "referral", "leader"]
    setup_terms = ["setup", "onboarding", "register", "registrieren", "vantage", "kyc", "verifizieren", "deposit", "einzahlen", "pamm", "offer", "mt5", "uid", "auszahlung", "withdraw", "konto"]
    if any(x in t for x in agent_terms):
        return "agent"
    if any(x in t for x in setup_terms):
        return "setup"
    return "general"


def should_show_commission_image(text):
    keywords = [
        "commission", "provision", "earn", "verdien", "struktur", "structure", "level", "referral", "agent", "how much",
        "wie viel", "passive", "income", "einkommen", "geld", "money", "10000", "10k", "verdienen", "provisi",
        "empfehlen", "refer", "partner", "rebate", "ib"
    ]
    return any(kw in text.lower() for kw in keywords)


def extract_and_save_lead(user_id, username):
    convo = conversations.get(user_id, [])
    if len(convo) < 2:
        return
    existing = agent_lead_data.get(user_id, {})
    try:
        raw = openai_chat(
            [
                {"role": "system", "content": "Extract agent registration and support lead data from the conversation. Return only valid JSON with keys: name, email, vantage_user_id, vantage_email, referred_by, estimated_users_90days, estimated_avg_deposit_usd, wants_leader_structure, current_setup_stage, main_objection, chat_summary. Use null if unknown. Extract only what the user explicitly stated or clearly asked. Keep chat_summary short."},
                {"role": "user", "content": json.dumps(convo[-40:], ensure_ascii=False)}
            ],
            model=OPENAI_MODEL_FAST,
            max_tokens=350,
            temperature=0
        )
        lead = parse_json_object(raw)
        lead["telegram_username"] = username
        lead["telegram_user_id"] = user_id
        lead["status"] = "new"
        lead["source"] = "telegram_bot"
        lead["last_updated_at"] = now_iso()
        for field in ["estimated_users_90days", "estimated_avg_deposit_usd"]:
            val = lead.get(field)
            if val is not None:
                try:
                    lead[field] = float(str(val).replace(",", ".").replace("$", "").strip())
                except Exception:
                    lead[field] = None
        # Keep the original dashboard field name as well, so existing Base44/dashboard logic stays compatible.
        # The bot uses the clearer 90-day wording internally, but the dashboard may still expect estimated_users_3months.
        if lead.get("estimated_users_90days") is not None:
            lead["estimated_users_3months"] = lead.get("estimated_users_90days")

        has_anything = any([
            lead.get("email"), lead.get("vantage_email"), lead.get("vantage_user_id"), lead.get("name"),
            lead.get("referred_by"), lead.get("estimated_users_90days"), lead.get("estimated_avg_deposit_usd")
        ])
        if not has_anything:
            return
        existing_id = existing.get("id")
        saved_id = save_lead(lead, existing_id=existing_id)
        is_complete = all([
            lead.get("name"),
            lead.get("referred_by"),
            lead.get("estimated_users_90days") is not None,
            lead.get("estimated_avg_deposit_usd") is not None,
            lead.get("vantage_user_id") or lead.get("vantage_email"),
            lead.get("email") or lead.get("vantage_email")
        ])
        agent_lead_data[user_id] = {"id": saved_id or existing_id, "complete": is_complete}
        logger.info(f"Lead for {user_id}: complete={is_complete}, data={lead}")
    except Exception as e:
        logger.error(f"extract_and_save_lead error: {e}")


def analyze_and_store_chat_insights(user_id, username):
    convo = conversations.get(user_id, [])
    if len(convo) < 4:
        return
    try:
        raw = openai_chat(
            [
                {"role": "system", "content": "Analyze this Bit28 support chat for internal improvement. Return only valid JSON with keys: summary, user_intent, objections, pain_points, missing_information, setup_stage, lead_quality, recommended_follow_up. objections and pain_points must be arrays. Be concise."},
                {"role": "user", "content": json.dumps(convo[-30:], ensure_ascii=False)}
            ],
            model=OPENAI_MODEL_FAST,
            max_tokens=450,
            temperature=0
        )
        insight = parse_json_object(raw)
        insight["telegram_user_id"] = user_id
        insight["telegram_username"] = username
        insight["created_at"] = now_iso()
        save_jsonl("/tmp/bit28_chat_insights.jsonl", insight)
        post_optional_webhook(insight)
    except Exception as e:
        logger.error(f"analyze_and_store_chat_insights error: {e}")


def get_stage_instruction(user_id, message):
    intent = detect_intent(message)
    user_modes[user_id] = intent if intent != "general" else user_modes.get(user_id, "general")
    if user_modes[user_id] == "setup":
        return "The user is likely in setup/onboarding mode. Guide only one step at a time. Ask what step they are currently on or whether the current step is completed. If there is a problem, ask for a screenshot."
    if user_modes[user_id] == "agent":
        return "The user is likely in agent onboarding mode. Explain briefly and collect agent data one question at a time. Do not ask multiple questions at once."
    return "The user is in general support/advisor mode. Answer simply and offer the next helpful step."


def chat_with_openai(user_id, message):
    if user_id not in conversations:
        conversations[user_id] = []
    conversations[user_id].append({"role": "user", "content": message})
    if len(conversations[user_id]) > 60:
        conversations[user_id] = conversations[user_id][-60:]
    try:
        stage_instruction = get_stage_instruction(user_id, message)
        reply = openai_chat(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "system", "content": stage_instruction}
            ] + conversations[user_id],
            model=OPENAI_MODEL_MAIN,
            max_tokens=500,
            temperature=0.45
        )
        reply = clean_bot_text(reply)
        conversations[user_id].append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return f"Ich habe gerade kurz ein technisches Problem. Bitte versuche es nochmal oder kontaktiere direkt den Support: {SUPPORT_TELEGRAM} oder {SUPPORT_EMAIL}"


def transcribe_voice(file_path):
    try:
        with open(file_path, "rb") as f:
            resp = requests.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                files={"file": ("voice.ogg", f, "audio/ogg")},
                data={"model": "whisper-1"},
                timeout=30
            )
        resp.raise_for_status()
        return resp.json().get("text", "")
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return ""


def analyze_image(image_path, context_text):
    try:
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": OPENAI_MODEL_MAIN,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "system", "content": "The user sent a screenshot during Bit28 or Vantage setup. Use the official Vantage PAMM guide knowledge: Client Portal, Verify Now, Open Account, MT5 PAMM Investor account, Active account status, Funds, Deposit, PAMM offer page, server, login/username, password, initial investment amount, terms agreement, Invest button, Join Requests, History Requests, History Transactions, and PAMM Investor Portal. Analyze it carefully. Tell them the next practical step. Be short and specific. If unsure, ask for one clearer screenshot or direct them to Bit28 support."},
                    {"role": "user", "content": [
                        {"type": "text", "text": f"Recent conversation: {context_text}"},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                    ]}
                ],
                "max_tokens": 450,
                "temperature": 0.25
            },
            timeout=30
        )
        resp.raise_for_status()
        return clean_bot_text(resp.json()["choices"][0]["message"]["content"])
    except Exception as e:
        logger.error(f"Image analysis error: {e}")
        return "Ich konnte das Bild leider nicht sicher analysieren. Bitte schicke einen klareren Screenshot oder beschreibe kurz, was auf dem Bildschirm steht."


PAMM_SCREENSHOTS = {
    "contents": {
        "file": "pamm_guide_page_02.jpg",
        "caption": "Official Vantage guide overview. Tell me which step you are at and I will send the exact next screenshot."
    },
    "registration": {
        "file": "pamm_guide_page_04.jpg",
        "caption": "Vantage registration. Use the personal referral link from your partner or Bit28 support."
    },
    "verification": {
        "file": "pamm_guide_page_05.jpg",
        "caption": "Verification step. Click Verify Now and complete the required personal details."
    },
    "open_pamm_account": {
        "file": "pamm_guide_page_06.jpg",
        "caption": "Open the PAMM Investor account. For Bit28, the platform must be MT5 and the account should be in USD."
    },
    "deposit_client_portal": {
        "file": "pamm_guide_page_08.jpg",
        "caption": "Deposit step in the Vantage Client Portal. The PAMM offer link comes only from your partner or Bit28 support."
    },
    "join_offer_start": {
        "file": "pamm_guide_page_09.jpg",
        "caption": "PAMM offer registration page. First select the correct server for your trading account."
    },
    "server_credentials": {
        "file": "pamm_guide_page_10.jpg",
        "caption": "Server selection. Make sure the MT5 server matches the server shown in your Vantage account."
    },
    "invest_confirm": {
        "file": "pamm_guide_page_11.jpg",
        "caption": "Enter username or login, password and investment amount, accept the terms, then click Invest."
    },
    "manager_approval": {
        "file": "pamm_guide_page_12.jpg",
        "caption": "After submitting, the PAMM manager reviews the join request. Official guide says this can take up to 72 hours."
    },
    "investor_portal_login": {
        "file": "pamm_guide_page_13.jpg",
        "caption": "PAMM Investor Portal. Log in with your trading account credentials to view portfolio, deposit history and performance reports."
    },
    "redeposit": {
        "file": "pamm_guide_page_14.jpg",
        "caption": "Re-deposit step. In the PAMM Investor Portal, click Deposit, enter the amount and confirm."
    },
    "deposit_status": {
        "file": "pamm_guide_page_15.jpg",
        "caption": "Deposit status. Pending requests are under History then Requests. Completed deposits are under History then Transactions."
    },
    "monitoring": {
        "file": "pamm_guide_page_17.jpg",
        "caption": "Monitoring. The PAMM portal can show activity, profit distribution, fee payouts, transfers and trading history."
    },
    "profit_distribution": {
        "file": "pamm_guide_page_19.jpg",
        "caption": "Profit and fee example with High-Water Mark. Fees apply only on new profits above the previous high."
    },
    "withdraw_intro": {
        "file": "pamm_guide_page_20.jpg",
        "caption": "Withdrawal section from the official PAMM guide."
    },
    "withdraw_step_1": {
        "file": "pamm_guide_page_21.jpg",
        "caption": "Withdrawal step. Use this screenshot if the user asks how to withdraw from the Investor Account."
    },
    "withdraw_step_2": {
        "file": "pamm_guide_page_22.jpg",
        "caption": "Withdrawal status and confirmation. Use this screenshot for withdrawal follow-up questions."
    },
    "precautions": {
        "file": "pamm_guide_page_24.jpg",
        "caption": "Precautions for PAMM investors from the official guide."
    },
    "faq": {
        "file": "pamm_guide_page_26.jpg",
        "caption": "FAQ section from the official PAMM Investor Guide."
    }
}


def unique_preserve_order(items):
    result = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result


def pamm_screenshot_keys_for_text(text):
    t = text.lower()
    keys = []

    if any(x in t for x in ["verifiz", "verify", "verification", "kyc", "id document", "identity"]):
        keys.append("verification")

    if any(x in t for x in ["registr", "register", "create account", "konto erstellen", "new client", "referral link"]):
        keys.append("registration")

    if any(x in t for x in ["open account", "live konto", "live account", "mt5", "pamm account", "konto eröffnen", "konto eroeffnen", "usd konto"]):
        keys.append("open_pamm_account")

    if any(x in t for x in ["deposit", "einzahl", "fund", "funds", "geld einzahlen", "usdt", "usdc"]):
        if any(x in t for x in ["status", "history", "request", "pending", "wartet", "transaktion", "transaction"]):
            keys.extend(["redeposit", "deposit_status"])
        else:
            keys.append("deposit_client_portal")

    if any(x in t for x in ["offer", "join", "beitreten", "link", "invest", "server", "login", "passwort", "password", "credentials", "zugangsdaten"]):
        if any(x in t for x in ["server"]):
            keys.append("server_credentials")
        elif any(x in t for x in ["passwort", "password", "login", "credentials", "zugangsdaten"]):
            keys.extend(["server_credentials", "invest_confirm"])
        elif any(x in t for x in ["approval", "bestätigung", "bestaetigung", "manager", "72", "waiting", "wartet"]):
            keys.append("manager_approval")
        else:
            keys.extend(["join_offer_start", "invest_confirm"])

    if any(x in t for x in ["portal", "performance", "monitor", "monitoring", "history", "trading progress", "fortschritt", "bericht", "report"]):
        keys.extend(["investor_portal_login", "monitoring"])

    if any(x in t for x in ["profit", "loss", "gewinn", "verlust", "fee", "gebühr", "gebuehr", "high watermark", "hwm", "profit share", "performance fee"]):
        keys.append("profit_distribution")

    if any(x in t for x in ["withdraw", "withdrawal", "auszahlung", "auszahlen", "abheben", "geld raus"]):
        keys.extend(["withdraw_intro", "withdraw_step_1", "withdraw_step_2"])

    if any(x in t for x in ["precaution", "vorsicht", "sicherheit", "safety", "risk", "risiko"]):
        keys.append("precautions")

    if any(x in t for x in ["faq", "häufig", "haeufig", "fragen"]):
        keys.append("faq")

    if not keys and any(x in t for x in ["guide", "pdf", "anleitung", "bilder", "screenshot", "screenshots", "step by step", "schritt für schritt", "schritt-für-schritt", "vantage guide", "pamm investor guide"]):
        keys.append("contents")

    return unique_preserve_order(keys)[:PAMM_MAX_SCREENSHOTS_PER_REQUEST]


def should_send_pamm_screenshots(text):
    t = text.lower()
    visual_terms = ["guide", "pdf", "anleitung", "bild", "bilder", "screenshot", "screenshots", "foto", "step by step", "schritt für schritt", "schritt-für-schritt", "zeigen", "zeig"]
    setup_terms = ["pamm", "vantage", "setup", "onboarding", "konto", "account", "deposit", "einzahlung", "withdraw", "auszahlung", "mt5", "offer"]
    return any(x in t for x in visual_terms) and any(x in t for x in setup_terms)


def resolve_pamm_screenshot_path(filename):
    candidates = [
        os.path.join(PAMM_SCREENSHOT_DIR, filename),
        os.path.join(os.path.dirname(__file__), PAMM_SCREENSHOT_DIR, filename),
        os.path.join(os.getcwd(), PAMM_SCREENSHOT_DIR, filename),
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return None


async def send_relevant_pamm_screenshots(update, context, message_text):
    keys = pamm_screenshot_keys_for_text(message_text)
    if not keys:
        return False

    sent_any = False
    for key in keys:
        item = PAMM_SCREENSHOTS.get(key)
        if not item:
            continue
        filename = item["file"]
        caption = item["caption"]
        try:
            if PAMM_SCREENSHOT_BASE_URL:
                photo_ref = f"{PAMM_SCREENSHOT_BASE_URL}/{filename}"
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=photo_ref,
                    caption=caption
                )
                sent_any = True
            else:
                local_path = resolve_pamm_screenshot_path(filename)
                if not local_path:
                    logger.warning(f"PAMM screenshot not found: {filename}")
                    continue
                with open(local_path, "rb") as f:
                    await context.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=f,
                        caption=caption
                    )
                sent_any = True
        except Exception as e:
            logger.error(f"Failed to send PAMM screenshot {key}: {e}")

    if not sent_any:
        await update.message.reply_text(
            f"Ich habe die passenden Screenshots gerade nicht im System gefunden. Bitte kontaktiere kurz den Support: {SUPPORT_TELEGRAM} oder {SUPPORT_EMAIL}"
        )
    return sent_any


async def send_commission_image(update, context):
    try:
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=COMMISSION_IMAGE_URL,
            caption="Bit28 5-Level Commission Structure"
        )
        context.user_data["commission_shown"] = True
    except Exception as e:
        logger.error(f"Failed to send commission image: {e}")


async def start(update, context):
    keyboard = [
        [InlineKeyboardButton("Visit Bit28.io", url="https://bit28.io")],
        [InlineKeyboardButton("Contact Support", url=SUPPORT_TELEGRAM)]
    ]
    welcome = (
        "Welcome to Bit28 Support.\n\n"
        "I can help you understand Bit28, guide you through the Vantage and PAMM setup, explain withdrawals and performance, send relevant screenshots from the official PAMM guide if needed, or help you register as an agent.\n\n"
        "What would you like to do first?"
    )
    await update.message.reply_text(welcome, reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_text(update, context):
    user = update.effective_user
    user_id = str(user.id)
    username = user.username or ""
    message = update.message.text
    if should_show_commission_image(message) and not context.user_data.get("commission_shown"):
        await send_commission_image(update, context)
    if should_send_pamm_screenshots(message):
        await send_relevant_pamm_screenshots(update, context, message)
    reply = chat_with_openai(user_id, message)
    await update.message.reply_text(reply)
    extract_and_save_lead(user_id, username)
    analyze_and_store_chat_insights(user_id, username)


async def handle_photo(update, context):
    user = update.effective_user
    user_id = str(user.id)
    username = user.username or ""
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        await file.download_to_drive(tmp.name)
        recent = conversations.get(user_id, [])[-8:]
        context_text = " | ".join([m.get("content", "") for m in recent if isinstance(m.get("content", ""), str)])
        reply = analyze_image(tmp.name, context_text)
    conversations.setdefault(user_id, []).append({"role": "user", "content": "[sent a screenshot]"})
    conversations[user_id].append({"role": "assistant", "content": reply})
    await update.message.reply_text(reply)
    extract_and_save_lead(user_id, username)
    analyze_and_store_chat_insights(user_id, username)


async def handle_voice(update, context):
    user = update.effective_user
    user_id = str(user.id)
    username = user.username or ""
    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        await file.download_to_drive(tmp.name)
        transcribed = transcribe_voice(tmp.name)
    if not transcribed:
        await update.message.reply_text("Ich konnte die Sprachnachricht leider nicht sicher verstehen. Bitte schreibe deine Frage kurz als Text.")
        return
    reply = chat_with_openai(user_id, transcribed)
    await update.message.reply_text(reply)
    extract_and_save_lead(user_id, username)
    analyze_and_store_chat_insights(user_id, username)


def validate_env():
    missing = []
    if not TELEGRAM_TOKEN:
        missing.append("TELEGRAM_TOKEN")
    if not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")
    if missing:
        raise RuntimeError("Missing environment variables: " + ", ".join(missing))


def main():
    validate_env()
    logger.info("Bit28Support Bot starting...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
