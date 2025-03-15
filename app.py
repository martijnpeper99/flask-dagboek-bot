import openai
from flask import Flask, request, jsonify
import sqlite3
import datetime
from twilio.rest import Client
import os
from flask import Flask, request, jsonify
from twilio.rest import Client
import time
from collections import deque
from openai import OpenAI


#rm -rf /Users/martijn/Library/Mobile Documents/com~apple~CloudDocs/Desktop/Martijn zijn bots/venv/.git/

#git init
#git add .
#git commit -m "Eerste commit"
#git branch -M main
#git remote add origin https://github.com/martijnpeper99/flask-dagboek-bot.git
#git push -u origin main

#git remote add origin https://github.com/JOUW-GITHUB-NAAM/flask-dagboek-bot.git

#git add .
#git commit -m "Mijn wijzigingen opslaan"
#git pull origin main --rebase
#git push -u origin main

 

import time
from openai import OpenAI
from requests.exceptions import ConnectionError, Timeout
import wave
from collections import deque
import openai
import random
from collections import deque
import io
import requests
import re
from requests.auth import HTTPBasicAuth
from google.oauth2 import service_account
import json
from google.cloud import storage
from vosk import Model, KaldiRecognizer
import subprocess
from dotenv import load_dotenv
from pathlib import Path
from pydub import AudioSegment
import urllib.request
from twilio.twiml.voice_response import VoiceResponse
import logging
import openai


# Gebruik een omgevingsvariabele:
import os
openai_api_key = os.getenv("OPENAI_API_KEY")

logging.basicConfig(level=logging.DEBUG)

# Load environment variables

load_dotenv()

app = Flask(__name__)



# Laad de variabelen uit het .env-bestand
load_dotenv()

# Gebruik de variabelen in je code
openai_api_key = os.getenv("OPENAI_API_KEY")
twilio_account_sid = os.getenv("TWILIO_ACCOUNT_SID")
twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_phone_number = os.getenv('TWILIO_PHONE_NUMBER')
my_phone_number = os.getenv('MY_PHONE_NUMBER')


TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")


twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


# SQLite Database aanmaken
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

@app.route("/get_messages", methods=["GET"])
def get_messages():
    """ Haalt berichten op uit de Twilio Sandbox """
    messages = twilio_client.messages.list(limit=50)  # Laatste 50 berichten ophalen
    recent_messages = []
    
    for msg in messages:
        if msg.from_ == TWILIO_SANDBOX_NUMBER or msg.to == TWILIO_SANDBOX_NUMBER:
            recent_messages.append({
                "from": msg.from_,
                "body": msg.body,
                "date_sent": msg.date_sent
            })
    
    return jsonify(recent_messages)

@app.route("/generate_diary", methods=["POST"])
def generate_diary():
    """ Genereert een dagboekverhaal op basis van WhatsApp-berichten """
    messages = request.json.get("messages")

    prompt = f"""
    Ik ben Martijn en dit zijn mijn WhatsApp-berichten met Lisa van vandaag:
    {messages}

    Schrijf een dagboekverslag over mijn dag vanuit mijn perspectief.
    """

    response = openai_client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )

    entry = response.choices[0].message.content
    date = datetime.datetime.now().strftime("%Y-%m-%d")

    # Opslaan in SQLite
    conn = sqlite3.connect("diary.db")
    c = conn.cursor()
    c.execute("INSERT INTO entries (date, user, entry) VALUES (?, ?, ?)", (date, "Martijn", entry))
    conn.commit()
    conn.close()

    return jsonify({"entry": entry})

if __name__ == "__main__":
    app.run(debug=True)
