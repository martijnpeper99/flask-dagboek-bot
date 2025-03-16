import os
import sqlite3
import datetime
import logging
import requests
from flask import Flask, request, jsonify
from twilio.rest import Client
from dotenv import load_dotenv
from openai import OpenAI  # client-based import

# Logging instellen
logging.basicConfig(level=logging.DEBUG)

# Environment-variabelen laden
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
MY_PHONE_NUMBER = os.getenv("MY_PHONE_NUMBER")
TWILIO_SANDBOX_NUMBER = os.getenv("TWILIO_SANDBOX_NUMBER")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is not set. Check your .env or Railway variables!")
if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
    raise ValueError("TWILIO credentials missing. Check your .env or Railway variables!")
if not TWILIO_SANDBOX_NUMBER:
    logging.warning("TWILIO_SANDBOX_NUMBER is not set, might cause issues.")

# Clients initialiseren
openai_client = OpenAI(api_key=OPENAI_API_KEY)
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Flask-app
app = Flask(__name__)

# Database inrichten
def init_db():
    conn = sqlite3.connect("diary.db")
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        user TEXT,
        entry TEXT
    )
    """)
    conn.commit()
    conn.close()

init_db()

# =======================
#  Routes
# =======================

@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    """Webhook die Twilio aanroept als er een WhatsApp-bericht binnenkomt."""
    incoming_msg = request.values.get("Body", "").lower()
    sender = request.values.get("From", "")
    return jsonify({"status": "received", "message": incoming_msg, "from": sender})

@app.route("/get_messages", methods=["GET"])
def get_messages():
    """ Haalt berichten op uit Twilio Sandbox (handig voor debug of als je 'm extern wil aanroepen). """
    messages = twilio_client.messages.list(limit=50)
    recent_messages = []
    for msg in messages:
        # Filter alleen sandbox-berichten (afzender of ontvanger is de sandbox)
        if msg.from_ == TWILIO_SANDBOX_NUMBER or msg.to == TWILIO_SANDBOX_NUMBER:
            if msg.date_sent:
                date_str = msg.date_sent.strftime("%a, %d %b %Y %H:%M:%S GMT")
            else:
                date_str = None

            recent_messages.append({
                "from": msg.from_,
                "body": msg.body,
                "date_sent": date_str
            })
    return jsonify(recent_messages)

@app.route("/webhook", methods=["POST"])
def webhook():
    """Automatisch antwoorden op WhatsApp-berichten."""
    incoming_msg = request.values.get('Body', '').lower()
    sender = request.values.get('From', '')
    if "hallo" in incoming_msg:
        response_msg = "Hey! Hoe gaat het vandaag?"
    else:
        response_msg = "Sorry, ik begrijp dat niet."
    return jsonify({"message": response_msg})

def generate_openai_diary(prompt: str) -> str:
    """Hulpfunctie om de prompt naar OpenAI te sturen via de client-based methode."""
    try:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"OpenAI-fout: {e}")
        return "Er ging iets mis met OpenAI."

@app.route("/generate_diary_now", methods=["POST"])
def generate_diary_now():
    """
    Genereert twee dagboekverslagen (Martijn & Lisa) op basis van de laatste 24 uur 
    aan WhatsApp Sandbox-berichten. Slaat ze op in de DB. Stuurt JSON terug.
    """
    logging.debug("▶️ generate_diary_now aangeroepen.")

    # ======= Belangrijkste verandering! =======
    # We halen direct Twilio-berichten op, ipv via requests.get("/get_messages"):

    all_messages = twilio_client.messages.list(limit=50)
    if not all_messages:
        return jsonify({"error": "Geen berichten beschikbaar."}), 400

    now_utc = datetime.datetime.utcnow()
    one_day_ago = now_utc - datetime.timedelta(days=1)

    last_24h_bodies = []
    for msg in all_messages:
        # Filter alleen de sandbox-berichten
        if msg.from_ == TWILIO_SANDBOX_NUMBER or msg.to == TWILIO_SANDBOX_NUMBER:
            # Check of er een date_sent is
            if msg.date_sent:
                # msg.date_sent is een datetime-obj (UTC)
                if msg.date_sent > one_day_ago:
                    last_24h_bodies.append(msg.body)

    if not last_24h_bodies:
        return jsonify({"error": "Geen recente berichten (24 uur)."}), 400

    combined_text = "\n".join(last_24h_bodies)

    # Prompt voor Martijn
    prompt_martijn = f"""
Ik ben Martijn en dit zijn mijn WhatsApp-berichten van de laatste 24 uur:
{combined_text}

Schrijf een dagboekverslag over mijn dag vanuit mijn ik-perspectief.
"""

    # Prompt voor Lisa
    prompt_lisa = f"""
Ik ben Lisa en dit zijn mijn WhatsApp-berichten van de laatste 24 uur:
{combined_text}

Schrijf een dagboekverslag over mijn dag vanuit mijn ik-perspectief.
"""

    # OpenAI calls
    martijn_entry = generate_openai_diary(prompt_martijn)
    lisa_entry = generate_openai_diary(prompt_lisa)

    # Opslaan in database
    conn = sqlite3.connect("diary.db")
    c = conn.cursor()
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    c.execute("INSERT INTO entries (date, user, entry) VALUES (?, ?, ?)", (date_str, "Martijn", martijn_entry))
    c.execute("INSERT INTO entries (date, user, entry) VALUES (?, ?, ?)", (date_str, "Lisa", lisa_entry))
    conn.commit()
    conn.close()

    return jsonify({
        "martijn_entry": martijn_entry,
        "lisa_entry": lisa_entry
    })

# Startserver
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
