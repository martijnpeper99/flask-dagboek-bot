import os
import sqlite3
import datetime
import logging
import requests
import datetime
from flask import Flask, request, jsonify
from twilio.rest import Client
from dotenv import load_dotenv
from openai import OpenAI

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

# **Clients initialiseren**
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
    incoming_msg = request.values.get("Body", "").lower()
    sender = request.values.get("From", "")
    return jsonify({"status": "received", "message": incoming_msg, "from": sender})


# **Twilio API: Berichten ophalen**
@app.route("/get_messages", methods=["GET"])
def get_messages():
    """ Haalt berichten op uit de Twilio Sandbox """
    messages = twilio_client.messages.list(limit=50)
    recent_messages = [
        {
            "from": msg.from_,
            "body": msg.body,
            "date_sent": msg.date_sent
        }
        for msg in messages if msg.from_ == TWILIO_SANDBOX_NUMBER or msg.to == TWILIO_SANDBOX_NUMBER
    ]
    return jsonify(recent_messages)

# **Twilio Webhook voor automatische WhatsApp-reacties**
@app.route("/webhook", methods=["POST"])
def webhook():
    """Automatisch antwoorden op WhatsApp-berichten"""
    incoming_msg = request.values.get('Body', '').lower()
    sender = request.values.get('From', '')

    if "hallo" in incoming_msg:
        response_msg = "Hey! Hoe gaat het vandaag?"
    else:
        response_msg = "Sorry, ik begrijp dat niet."

    return jsonify({"message": response_msg})

# **OpenAI: Dagboek genereren**

@app.route("/generate_diary_now", methods=["POST"])
def generate_diary_now():
    """Genereert direct een dagboekverhaal en stuurt het terug."""
    print("📖 Direct een dagboek genereren...")

    # Haal de laatste 24 uur aan berichten op
    response = requests.get("https://flask-dagboek-bot-production.up.railway.app/get_messages")

    if response.status_code == 200:
        messages = response.json()
        if not messages:
            return jsonify({"error": "Geen berichten in de laatste 24 uur."}), 400

        # Filter berichten van de laatste 24 uur
        now = datetime.datetime.utcnow()
        recent_messages = [
            msg["body"] for msg in messages if datetime.datetime.strptime(msg["date_sent"], "%a, %d %b %Y %H:%M:%S GMT") > now - datetime.timedelta(days=1)
        ]

        # Verstuur berichten naar OpenAI voor dagboekverslag
        if recent_messages:
            prompt = f"""
            Ik ben Martijn en dit zijn mijn WhatsApp-berichten van de laatste 24 uur:
            {recent_messages}

            Schrijf een dagboekverslag over mijn dag vanuit mijn perspectief.
            """

            openai_response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}]
            )

            diary_entry = openai_response.choices[0].message.content

            # Sla het dagboek op in SQLite
            conn = sqlite3.connect("diary.db")
            c = conn.cursor()
            c.execute("INSERT INTO entries (date, user, entry) VALUES (?, ?, ?)", (datetime.datetime.now().strftime("%Y-%m-%d"), "Martijn", diary_entry))
            conn.commit()
            conn.close()

            print("✅ Dagboek direct gegenereerd en opgeslagen!")
            return jsonify({"entry": diary_entry})

        else:
            return jsonify({"error": "Geen recente berichten gevonden."}), 400

    else:
        return jsonify({"error": f"Fout bij ophalen berichten: {response.status_code}"}), 500

@app.route("/generate_diary", methods=["POST"])
def generate_diary():
    """ Genereert een dagboekverhaal op basis van WhatsApp-berichten """
    messages = request.json.get("messages")
    if not messages:
        return jsonify({"error": "Geen berichten ontvangen"}), 400

    prompt = f"""
    Ik ben Martijn en dit zijn mijn WhatsApp-berichten met Lisa van vandaag:
    {messages}

    Schrijf een dagboekverslag over mijn dag vanuit mijn perspectief.
    """

    try:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )

        entry = response.choices[0].message.content
        date = datetime.datetime.now().strftime("%Y-%m-%d")

        # **Opslaan in database**
        conn = sqlite3.connect("diary.db")
        c = conn.cursor()
        c.execute("INSERT INTO entries (date, user, entry) VALUES (?, ?, ?)", (date, "Martijn", entry))
        conn.commit()
        conn.close()

        return jsonify({"entry": entry})

    except Exception as e:
        logging.error(f"Error generating diary: {str(e)}")
        return jsonify({"error": str(e)}), 500

# **Server starten**
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
