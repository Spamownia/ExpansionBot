# main.py - Bot logów DayZ – ANSI kolory W CODE BLOCKU ansi + data godzina emoji . treść
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

# ANSI kolory – używamy \x1b (ESC)
ANSI_RESET  = "\x1b[0m"
ANSI_RED    = "\x1b[31m"
ANSI_GREEN  = "\x1b[32m"
ANSI_YELLOW = "\x1b[33m"
ANSI_BLUE   = "\x1b[34m"
ANSI_WHITE  = "\x1b[37m"

@bot.event
async def on_ready():
    teraz = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{teraz}] BOT URUCHOMIONY")
    kanal_test = bot.get_channel(KANAL_TESTOWY_ID)
    if kanal_test:
        await kanal_test.send(f"🟢 Bot wystartował {teraz}\n```ansi
        print("Wysłano komunikat startowy")
    if os.path.exists('stan.txt'):
        os.remove('stan.txt')
        print("Usunięto stan.txt – wymuszony odczyt całego logu")
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

        buf = io.BytesIO()
        ftp.retrbinary(f'RETR {najnowszy}', buf.write)
        ftp.quit()
        buf.seek(0)
        tekst = buf.read().decode('utf-8', errors='ignore')
        linie = tekst.splitlines()

        print(f"Liczba linii w pliku: {len(linie)}")

        if linie:
            for linia in linie:
                # Godzina z loga (początek linii)
                match = re.match(r'^(\d{2}:\d{2}:\d{2}\.\d{3})', linia.strip())
                godzina_z_loga = match.group(1) if match else "--:--:--.---"

                # Kategoria, emoji, kolor
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
                    kolor = ANSI_WHITE  # lub inny jeśli chcesz odróżnić

                # Treść bez początkowej godziny
                clean_tresc = re.sub(r'^\d{2}:\d{2}:\d{2}\.\d{3}\s*', '', linia.strip())

                # Cała linia w ANSI
                tresc_kolorowa = f"{kolor}{emoji_kategorii} . {clean_tresc}{ANSI_RESET}"

                # Format z datą + godziną z loga
                cala_wiadomosc = f"{datetime.now().strftime('%Y-%m-%d')} {godzina_z_loga} {tresc_kolorowa}"

                # Wysyłamy jako code block ansi
                wiadomosc_do_discorda = f"```ansi\n{cala_wiadomosc}\n```"

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
                        await kanal.send(wiadomosc_do_discorda)
                        print(f"Wysłano linię do {kategoria}")
                    except Exception as e:
                        print(f"Błąd wysyłania do {kategoria}: {e}")
                    await asyncio.sleep(0.8)  # rate limit safety

            print(f"Wysłano wszystkie linie z pliku")

        else:
            print("Plik pusty lub błąd odczytu")

        print("=== KONIEC ===\n")

    except Exception as e:
        print(f"Błąd: {e}")

if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print(f"Flask nasłuchuje na porcie {os.getenv('PORT', 10000)}")
    bot.run(DISCORD_TOKEN)
