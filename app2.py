import os
import sqlite3
import datetime
import logging
import requests
from flask import Flask, request, jsonify
from twilio.rest import Client
from dotenv import load_dotenv
from openai import OpenAI  # <--- client-based import

# Logging voor debugging
logging.basicConfig(level=logging.DEBUG)

# **Laad environment variables**
load_dotenv()

# **API Keys laden**
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
MY_PHONE_NUMBER = os.getenv("MY_PHONE_NUMBER")
TWILIO_SANDBOX_NUMBER = os.getenv("TWILIO_SANDBOX_NUMBER")

# **Controleer of de variabelen zijn geladen**
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is not set. Check your .env file!")
if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
    raise ValueError("TWILIO credentials are missing. Check your .env file!")
if not TWILIO_SANDBOX_NUMBER:
    logging.warning("TWILIO_SANDBOX_NUMBER is not set. The app may not function correctly.")

# **Clients initialiseren** (client-based OpenAI)
openai_client = OpenAI(api_key=OPENAI_API_KEY)
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# **Flask app starten**
app = Flask(__name__)

# **SQLite Database aanmaken**
def init_db():
    conn = sqlite3.connect("diary.db")
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        user TEXT,
        entry TEXT
    )""")
    conn.commit()
    conn.close()

init_db()

@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    """Webhook die Twilio aanroept als er een WhatsApp-bericht binnenkomt."""
    incoming_msg = request.values.get("Body", "").lower()
    sender = request.values.get("From", "")
    # Je zou hier logica kunnen doen om direct te antwoorden, etc.
    return jsonify({"status": "received", "message": incoming_msg, "from": sender})

# **Twilio API: Berichten ophalen**
@app.route("/get_messages", methods=["GET"])
def get_messages():
    """ Haalt berichten op uit de Twilio Sandbox (laatste 50). """
    messages = twilio_client.messages.list(limit=50)
    recent_messages = []
    for msg in messages:
        # Filter alleen berichten die in/uit de Sandbox gaan
        if (msg.from_ == TWILIO_SANDBOX_NUMBER) or (msg.to == TWILIO_SANDBOX_NUMBER):
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

# **Twilio Webhook voor automatische WhatsApp-reacties**
@app.route("/webhook", methods=["POST"])
def webhook():
    """Automatisch antwoorden op WhatsApp-berichten (optioneel)."""
    incoming_msg = request.values.get('Body', '').lower()
    sender = request.values.get('From', '')

    if "hallo" in incoming_msg:
        response_msg = "Hey! Hoe gaat het vandaag?"
    else:
        response_msg = "Sorry, ik begrijp dat niet."

    return jsonify({"message": response_msg})

# **Hulpfunctie om OpenAI-chatcalls te doen (client-based)**
def generate_openai_diary(prompt: str):
    """
    Stuurt prompt naar OpenAI via client-gebaseerde aanroep
    en geeft de response content terug.
    """
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
    logging.debug("▶️ generate_diary_now aangeroepen.")

    # 1) Haal direct Twilio-berichten op
    all_messages = twilio_client.messages.list(limit=50)
    if not all_messages:
        return jsonify({"error": "Geen berichten beschikbaar."}), 400

    # 2) Filter laatste 24 uur
    now_utc = datetime.datetime.utcnow()
    one_day_ago = now_utc - datetime.timedelta(days=1)

    last_24h_bodies = []
    for msg in all_messages:
        if msg.from_ == TWILIO_SANDBOX_NUMBER or msg.to == TWILIO_SANDBOX_NUMBER:
            if msg.date_sent and msg.date_sent > one_day_ago:
                last_24h_bodies.append(msg.body)

    if not last_24h_bodies:
        return jsonify({"error": "Geen recente berichten (24 uur)."}), 400

    combined_text = "\n".join(last_24h_bodies)

    # 3) Bouw prompts en genereer met OpenAI
    prompt_martijn = f"""
    Ik ben Martijn...
    {combined_text}
    Schrijf een dagboekverslag...
    """
    prompt_lisa = f"""
    Ik ben Lisa...
    {combined_text}
    Schrijf een dagboekverslag...
    """

    martijn_entry = generate_openai_diary(prompt_martijn)
    lisa_entry = generate_openai_diary(prompt_lisa)

    # 4) Sla op in database
    conn = sqlite3.connect("diary.db")
    c = conn.cursor()
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    c.execute("INSERT INTO entries (date, user, entry) VALUES (?, ?, ?)", (date_str, "Martijn", martijn_entry))
    c.execute("INSERT INTO entries (date, user, entry) VALUES (?, ?, ?)", (date_str, "Lisa", lisa_entry))
    conn.commit()
    conn.close()

    # 5) Geef JSON terug
    return jsonify({
        "martijn_entry": martijn_entry,
        "lisa_entry": lisa_entry
    })


# **Server starten**
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

