# main.py - Bot logów DayZ – ANSI kolory + tylko nowe linie (offset po rozmiarze pliku)
import discord
from discord.ext import commands, tasks
import ftplib
import io
import os
from datetime import datetime
import asyncio
import threading
import re

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
if not DISCORD_TOKEN:
    print("BRAK DISCORD_TOKEN → STOP")
    exit(1)

FTP_HOST = os.getenv('FTP_HOST', '147.93.162.60')
FTP_PORT = int(os.getenv('FTP_PORT', 51421))
FTP_USER = os.getenv('FTP_USER', 'gpftp37275281809840533')
FTP_PASS = os.getenv('FTP_PASS', '8OhDv1P5')
FTP_LOG_DIR = os.getenv('FTP_LOG_DIR', '/config/ExpansionMod/Logs')

KANAL_TESTOWY_ID = 1469089759958663403
KANAL_AIRDROP_ID = 1469089759958663403
KANAL_MISJE_ID  = 1469089759958663403
KANAL_RAIDING_ID = 1469089759958663403
KANAL_POJAZDY_ID = 1469089759958663403

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Flask
from flask import Flask
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot działa"

@flask_app.route('/health')
def health():
    return "OK", 200

def run_flask():
    port = int(os.getenv('PORT', 10000))
    flask_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ANSI kolory
ANSI_RESET  = "\x1b[0m"
ANSI_RED    = "\x1b[31m"
ANSI_GREEN  = "\x1b[32m"
ANSI_YELLOW = "\x1b[33m"
ANSI_BLUE   = "\x1b[34m"
ANSI_WHITE  = "\x1b[37m"

STATE_FILE = 'last_log_size.txt'

def load_last_size():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            try:
                return int(f.read().strip())
            except:
                return 0
    return 0

def save_last_size(size):
    with open(STATE_FILE, 'w') as f:
        f.write(str(size))

@bot.event
async def on_ready():
    teraz = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{teraz}] BOT URUCHOMIONY")
    
    kanal_test = bot.get_channel(KANAL_TESTOWY_ID)
    if kanal_test:
        wiadomosc_startowa = (
            f"🟢 Bot wystartował {teraz}\n"
            "```ansi\n"
            "Data godzina_z_loga emoji . treść loga (kolory powinny działać!)\n"
            "```"
        )
        await kanal_test.send(wiadomosc_startowa)
        print("Wysłano komunikat startowy")
    
    # Przy pierwszym starcie czyścimy stan, jeśli chcesz wymusić pełne odczytanie → odkomentuj
    # if os.path.exists(STATE_FILE):
    #     os.remove(STATE_FILE)
    #     print("Wymuszono pełne odczytanie logów przy starcie")
    
    await sprawdz_logi()
    if not sprawdz_logi.is_running():
        sprawdz_logi.start()

@tasks.loop(seconds=60)
async def sprawdz_logi():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] === START sprawdzania FTP ===")
    try:
        ftp = ftplib.FTP()
        ftp.connect(FTP_HOST, FTP_PORT)
        ftp.login(FTP_USER, FTP_PASS)
        ftp.cwd(FTP_LOG_DIR)

        pliki_raw = []
        ftp.retrlines('LIST', pliki_raw.append)
        pliki = [line.split()[-1] for line in pliki_raw if line.split()[-1]]

        exp_logi = [f for f in pliki if f.startswith('ExpLog_') and f.endswith('.log')]
        if not exp_logi:
            print("Brak plików ExpLog_*")
            ftp.quit()
            return

        def parse_date(f):
            try:
                return datetime.strptime(f.split('ExpLog_')[1].split('.log')[0], '%Y-%m-%d_%H-%M-%S')
            except:
                return datetime.min

        pliki.sort(key=parse_date, reverse=True)
        najnowszy = pliki[0]
        print(f"Najnowszy plik: {najnowszy}")

        # Sprawdzamy aktualny rozmiar pliku
        ftp.sendcmd('TYPE I')  # binary mode do SIZE
        current_size = ftp.size(najnowszy)
        last_size = load_last_size()

        if current_size <= last_size:
            print(f"Plik się nie zmienił ({current_size} bajtów) → pomijam")
            ftp.quit()
            return

        print(f"Plik urósł z {last_size} → {current_size} bajtów")

        # Pobieramy TYLKO nowe dane (od last_size)
        buf = io.BytesIO()
        ftp.retrbinary(f'RETR {najnowszy}', buf.write, rest=last_size)
        ftp.quit()

        buf.seek(0)
        nowe_bajty = buf.read().decode('utf-8', errors='ignore')

        if not nowe_bajty.strip():
            print("Brak nowych linii")
            save_last_size(current_size)
            return

        linie = nowe_bajty.splitlines()
        print(f"Nowe linie: {len(linie)}")

        for linia in linie:
            if not linia.strip():
                continue

            match = re.match(r'^(\d{2}:\d{2}:\d{2}\.\d{3})', linia.strip())
            godzina_z_loga = match.group(1) if match else "--:--:--.---"

            emoji_kategorii = "⬜"
            kolor = ANSI_WHITE
            kategoria = 'test'

            if '[MissionAirdrop]' in linia:
                kategoria = 'airdrop'
                emoji_kategorii = "🟡"
                kolor = ANSI_YELLOW
            elif '[Expansion Quests]' in linia:
                kategoria = 'misje'
                emoji_kategorii = "🔵"
                kolor = ANSI_BLUE
            elif '[BaseRaiding]' in linia:
                kategoria = 'raiding'
                emoji_kategorii = "🔴"
                kolor = ANSI_RED
            elif any(x in linia for x in ['[Vehicle', 'VehicleDeleted', 'VehicleEnter', 'VehicleLeave', 'VehicleEngine', 'VehicleCarKey']):
                kategoria = 'pojazdy'
                emoji_kategorii = "🟢"
                kolor = ANSI_GREEN
            elif '[AI Object Patrol' in linia:
                kolor = ANSI_WHITE

            clean_tresc = re.sub(r'^\d{2}:\d{2}:\d{2}\.\d{3}\s*', '', linia.strip())

            tresc_kolorowa = f"{kolor}{emoji_kategorii} . {clean_tresc}{ANSI_RESET}"

            cala_linia = f"{datetime.now().strftime('%Y-%m-%d')} {godzina_z_loga} {tresc_kolorowa}"

            wiadomosc = f"```ansi\n{cala_linia}\n```"

            kanal_id = {
                'airdrop':  KANAL_AIRDROP_ID,
                'misje':    KANAL_MISJE_ID,
                'raiding':  KANAL_RAIDING_ID,
                'pojazdy':  KANAL_POJAZDY_ID,
                'test':     KANAL_TESTOWY_ID
            }[kategoria]

            kanal = bot.get_channel(kanal_id)
            if kanal:
                try:
                    await kanal.send(wiadomosc)
                    print(f"Wysłano → {kategoria}")
                except Exception as e:
                    print(f"Błąd wysyłania do {kategoria}: {e}")
                await asyncio.sleep(0.8)

        # Zapisujemy nowy rozmiar dopiero po udanym przetworzeniu
        save_last_size(current_size)
        print(f"Zapisano nowy offset: {current_size}")

        print("=== KONIEC ===\n")

    except Exception as e:
        print(f"Błąd FTP: {e}")

if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print(f"Flask nasłuchuje na porcie {os.getenv('PORT', 10000)}")
    bot.run(DISCORD_TOKEN)
