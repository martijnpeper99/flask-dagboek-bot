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

# **OpenAI: Dagboek direct genereren (vanuit Martijn & Lisa)**
@app.route("/generate_diary_now", methods=["POST"])
def generate_diary_now():
    """
    Genereert direct twee dagboekverslagen: 
      - één vanuit Martijns ik-perspectief
      - één vanuit Lisa's ik-perspectief
    op basis van de laatste 24 uur aan WhatsApp-berichten uit Twilio.
    Slaat ze op in de database en geeft beide terug als JSON.
    """
    logging.debug("▶️ generate_diary_now aangeroepen.")

    # Haal de laatste 50 berichten op
    response = requests.get("https://flask-dagboek-bot-production.up.railway.app/get_messages")
    if response.status_code != 200:
        return jsonify({"error": f"Fout bij ophalen berichten: {response.status_code}"}), 500
    
    messages = response.json()
    if not messages:
        return jsonify({"error": "Geen berichten beschikbaar."}), 400

    # Filter alleen die van de laatste 24 uur
    now = datetime.datetime.utcnow()
    one_day_ago = now - datetime.timedelta(days=1)
    recent_texts = []

    for msg in messages:
        date_str = msg.get("date_sent")
        if not date_str:
            continue  # als er geen datum is, skip
        try:
            date_obj = datetime.datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S GMT")
        except ValueError:
            # Als de parse faalt, skip 
            # (of je kunt logging.debug() doen om te zien wat er misgaat)
            continue

        if date_obj > one_day_ago:
            # Pak de body
            recent_texts.append(msg["body"])

    if not recent_texts:
        return jsonify({"error": "Geen recente berichten (laatste 24 uur)."}), 400

    # Bouw 1 string met alle bericht-teksten (eventueel kun je formateren)
    combined_text = "\n".join(recent_texts)

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

    # Vraag aan OpenAI (client-based)
    martijn_entry = generate_openai_diary(prompt_martijn)
    lisa_entry    = generate_openai_diary(prompt_lisa)

    # Sla allebei op in SQLite
    conn = sqlite3.connect("diary.db")
    c = conn.cursor()
    date_now_str = datetime.datetime.now().strftime("%Y-%m-%d")

    c.execute("INSERT INTO entries (date, user, entry) VALUES (?, ?, ?)", 
              (date_now_str, "Martijn", martijn_entry))
    c.execute("INSERT INTO entries (date, user, entry) VALUES (?, ?, ?)", 
              (date_now_str, "Lisa", lisa_entry))
    conn.commit()
    conn.close()

    logging.debug("✅ Dagboekverslagen succesvol gegenereerd en opgeslagen.")

    # Beide verslagen teruggeven in JSON
    return jsonify({
        "martijn_entry": martijn_entry,
        "lisa_entry": lisa_entry
    })

# **Server starten**
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

