# main.py
import discord
from discord.ext import commands, tasks
import ftplib
import io
import os
from datetime import datetime
import threading

# ────────────────────────────────────────────────
# KONFIGURACJA (zmień ID kanałów!)
# ────────────────────────────────────────────────

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
if not DISCORD_TOKEN:
    print("Brak DISCORD_TOKEN → bot nie wystartuje")
    exit(1)

FTP_HOST = os.getenv('FTP_HOST', '147.93.162.60')
FTP_PORT = int(os.getenv('FTP_PORT', 51421))
FTP_USER = os.getenv('FTP_USER', 'gpftp37275281809840533')
FTP_PASS = os.getenv('FTP_PASS', '8OhDv1P5')
FTP_LOG_DIR = os.getenv('FTP_LOG_DIR', '/config/ExpansionMod/Logs')

# ID kanałów – zmień na swoje!
KANAŁY = {
    'pojazd':   1234567890123456789,
    'misje':    1234567890123456789,
    'rynek':    1234567890123456789,
    'strefa':   1234567890123456789,
    'ai':       1234567890123456789,
    'airdrop':  1234567890123456789,
    'raiding':  1234567890123456789,
    'zabicie':  1234567890123456789,
}

PLIK_STANU = 'stan.txt'

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# ────────────────────────────────────────────────
# FLASK – serwer HTTP żeby Render nie zabił instancji
# ────────────────────────────────────────────────

from flask import Flask
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Discord bot działa – nasłuchuję logów DayZ Expansion"

@flask_app.route('/health')
def health():
    return "OK", 200

# Uruchamiamy Flask w osobnym wątku (bo bot.run() blokuje główny wątek)
def run_flask():
    port = int(os.getenv('PORT', 10000))   # Render wymaga zmiennej PORT
    flask_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ────────────────────────────────────────────────
# Logika bota – bez zmian (skrócona wersja z poprzedniego kodu)
# ────────────────────────────────────────────────

@bot.event
async def on_ready():
    print(f'Bot wystartował jako {bot.user}')
    sprawdz_logi.start()

@tasks.loop(minutes=1)
async def sprawdz_logi():
    # ... tutaj cała Twoja logika pobierania FTP i wysyłania do kanałów ...
    # (skopiuj funkcję sprawdz_logi z poprzedniej wersji)
    # dla skrócenia nie wklejam jej całej ponownie – tylko pamiętaj o niej
    print("Sprawdzam logi...")

# ────────────────────────────────────────────────
# START – Flask + bot równolegle
# ────────────────────────────────────────────────

if __name__ == '__main__':
    # Uruchamiamy Flask w tle
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print(f"Serwer HTTP nasłuchuje na porcie {os.getenv('PORT', 10000)}")
    
    # Startujemy bota (blokuje główny wątek)
    bot.run(DISCORD_TOKEN)
