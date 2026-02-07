# main.py - Bot logów DayZ Expansion – każda linia osobno na kanał z kolorami ANSI
import discord
from discord.ext import commands, tasks
import ftplib
import io
import os
from datetime import datetime
import asyncio
import threading

# ==================================================
# KONFIGURACJA – Twoje ID kanałów
# ==================================================

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
if not DISCORD_TOKEN:
    print("BRAK DISCORD_TOKEN → STOP")
    exit(1)

FTP_HOST = os.getenv('FTP_HOST', '147.93.162.60')
FTP_PORT = int(os.getenv('FTP_PORT', 51421))
FTP_USER = os.getenv('FTP_USER', 'gpftp37275281809840533')
FTP_PASS = os.getenv('FTP_PASS', '8OhDv1P5')
FTP_LOG_DIR = os.getenv('FTP_LOG_DIR', '/config/ExpansionMod/Logs')

KANAL_TESTOWY_ID = 1469089759958663403     # ← test / debug / niepasujące
KANAL_AIRDROP_ID = 1469089759958663403
KANAL_MISJE_ID   = 1469089759958663403
KANAL_RAIDING_ID = 1469089759958663403
KANAL_POJAZDY_ID = 1469089759958663403

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Flask – wymagany dla Web Service
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

# ==================================================
# ANSI KOLORY DLA WIADOMOŚCI NA DISCORD
# ==================================================

ANSI_RESET   = "\x1b[0m"
ANSI_BOLD    = "\x1b[1m"
ANSI_RED     = "\x1b[31m"
ANSI_GREEN   = "\x1b[32m"
ANSI_YELLOW  = "\x1b[33m"
ANSI_BLUE    = "\x1b[34m"
ANSI_MAGENTA = "\x1b[35m"
ANSI_CYAN    = "\x1b[36m"
ANSI_WHITE   = "\x1b[37m"

# ==================================================
# BOT
# ==================================================

@bot.event
async def on_ready():
    teraz = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{teraz}] BOT URUCHOMIONY")

    kanal_test = bot.get_channel(KANAL_TESTOWY_ID)
    if kanal_test:
        embed = discord.Embed(
            title="🟢 Bot HusariaEXAPL wystartował",
            description=f"Data: {teraz}\nTRYB TESTOWY – odczyt CAŁEGO logu co 60 sekund\nKażda linia osobno na odpowiedni kanał z kolorami ANSI",
            color=0x00FF00
        )
        embed.set_footer(text="Sprawdzanie co 60 sekund")
        await kanal_test.send(embed=embed)
        print("Wysłano komunikat startowy")

    # Wymuszamy odczyt całego logu przy starcie
    if os.path.exists('stan.txt'):
        os.remove('stan.txt')
        print("Usunięto stan.txt – wymuszony odczyt całego logu przy starcie")

    await sprawdz_logi()
    if not sprawdz_logi.is_running():
        sprawdz_logi.start()

@tasks.loop(seconds=60)
async def sprawdz_logi():
    teraz = datetime.now().strftime("%H:%M:%S")
    print(f"[{teraz}] === START sprawdzania FTP – TRYB TESTOWY (cały plik) ===")

    try:
        ftp = ftplib.FTP()
        ftp.connect(FTP_HOST, FTP_PORT)
        ftp.login(FTP_USER, FTP_PASS)
        ftp.cwd(FTP_LOG_DIR)

        pliki = [f for f in ftp.nlst() if f.startswith('ExpLog_') and f.endswith('.log')]
        if not pliki:
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

        # Zawsze CAŁY plik – ignorujemy stan.txt (tryb testowy)
        print("Tryb testowy: odczyt CAŁEGO pliku bez stanu.txt")

        buf = io.BytesIO()
        ftp.retrbinary(f'RETR {najnowszy}', buf.write)
        ftp.quit()
        buf.seek(0)
        tekst = buf.read().decode('utf-8', errors='ignore')
        linie = tekst.splitlines()

        print(f"Liczba linii w pliku: {len(linie)}")

        if linie:
            for linia in linie:
                kolor_ansi = ANSI_WHITE
                kategoria = 'test'

                if '[MissionAirdrop]' in linia:
                    kategoria = 'airdrop'
                    kolor_ansi = ANSI_YELLOW
                elif '[Expansion Quests]' in linia:
                    kategoria = 'misje'
                    kolor_ansi = ANSI_BLUE
                elif '[BaseRaiding]' in linia:
                    kategoria = 'raiding'
                    kolor_ansi = ANSI_RED
                elif any(x in linia for x in ['[Vehicle', 'VehicleDeleted', 'VehicleEnter', 'VehicleLeave', 'VehicleEngine', 'VehicleCarKey']):
                    kategoria = 'pojazdy'
                    kolor_ansi = ANSI_GREEN

                # Wybieramy ID kanału
                kanal_id = {
                    'airdrop': KANAL_AIRDROP_ID,
                    'misje': KANAL_MISJE_ID,
                    'raiding': KANAL_RAIDING_ID,
                    'pojazdy': KANAL_POJAZDY_ID,
                    'test': KANAL_TESTOWY_ID
                }[kategoria]

                kanal = bot.get_channel(kanal_id)
                if kanal:
                    # Kolor ANSI + tekst w bloku kodu
                    wiadomosc = f"```ansi\n{kolor_ansi}{linia}{ANSI_RESET}\n```"

                    try:
                        await kanal.send(wiadomosc)
                        print(f"Wysłano linię do {kategoria}")
                    except Exception as e:
                        print(f"Błąd wysyłania do {kategoria}: {e}")
                    await asyncio.sleep(0.8)  # ochrona przed rate-limit

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
