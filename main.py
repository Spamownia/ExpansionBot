# main.py - Bot logów DayZ – każda linia osobno z ANSI + czasem
import discord
from discord.ext import commands, tasks
import ftplib
import io
import os
from datetime import datetime
import asyncio
import threading

# ==================================================
# KONFIGURACJA – ZMIEŃ ID KANAŁÓW NA RZECZYWISTE!
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

# <--- ZMIEŃ TE ID NA PRAWDZIWE NUMERY KANAŁÓW !!!
KANAL_TESTOWY_ID = 1469089759958663403      # ← kanał na resztę / debug
KANAL_AIRDROP_ID = 1234567890123456789      # ← ID kanału Airdrop
KANAL_MISJE_ID   = 1234567890123456789      # ← ID kanału Misje / Quests
KANAL_RAIDING_ID = 1234567890123456789      # ← ID kanału Raiding / Bazy
KANAL_POJAZDY_ID = 1234567890123456789      # ← ID kanału Pojazdy

PLIK_STANU = 'stan.txt'

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Flask – wymagany dla Render Web Service
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
# ANSI KOLORY (Discord wspiera w bloku ```ansi
# ==================================================

ANSI_RESET   = "\\x1b[0m"
ANSI_RED     = "\\x1b[31m"
ANSI_GREEN   = "\\x1b[32m"
ANSI_YELLOW  = "\\x1b[33m"
ANSI_BLUE    = "\\x1b[34m"
ANSI_WHITE   = "\\x1b[37m"

# ==================================================
# BOT
# ==================================================

@bot.event
async def on_ready():
    teraz = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{teraz}] BOT URUCHOMIONY")

    kanal_test = bot.get_channel(KANAL_TESTOWY_ID)
    if kanal_test:
        await kanal_test.send(f"🟢 Bot wystartował {teraz}\nKażda linia osobno z ANSI + czasem")
        print("Wysłano komunikat startowy")

    # Wymuszamy odczyt całego logu przy starcie (tylko raz – potem normalnie nowe linie)
    if os.path.exists(PLIK_STANU):
        os.remove(PLIK_STANU)
        print("Usunięto stan.txt – wymuszony pełny odczyt przy starcie")

    await sprawdz_logi()
    if not sprawdz_logi.is_running():
        sprawdz_logi.start()

@tasks.loop(seconds=60)
async def sprawdz_logi():
    teraz = datetime.now().strftime("%H:%M:%S")
    print(f"[{teraz}] === START sprawdzania FTP ===")

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

        # Odczyt stanu (jeśli istnieje)
        ostatni_plik = ''
        ostatnia_linia = 0
        if os.path.exists(PLIK_STANU):
            with open(PLIK_STANU, 'r', encoding='utf-8') as f:
                dane = f.read().strip().split('\n')
                if len(dane) >= 2:
                    ostatni_plik = dane[0]
                    ostatnia_linia = int(dane[1])

        print(f"Stan: plik={ostatni_plik}, linia={ostatnia_linia}")

        buf = io.BytesIO()
        ftp.retrbinary(f'RETR {najnowszy}', buf.write)
        ftp.quit()
        buf.seek(0)
        tekst = buf.read().decode('utf-8', errors='ignore')
        linie = tekst.splitlines()

        print(f"Całkowita liczba linii w pliku: {len(linie)}")

        # Tylko nowe linie (lub wszystkie przy pierwszym uruchomieniu / zmianie pliku)
        nowe_linje = linie if najnowszy != ostatni_plik else linie[ostatnia_linia:]

        print(f"Nowe linie do wysłania: {len(nowe_linje)}")

        if nowe_linje:
            for linia in nowe_linje:
                # Czas + linia
                linia_z_czasem = f"[{teraz}] {linia}"

                # Kolor ANSI + kategoria
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

                kanal_id = {
                    'airdrop': KANAL_AIRDROP_ID,
                    'misje': KANAL_MISJE_ID,
                    'raiding': KANAL_RAIDING_ID,
                    'pojazdy': KANAL_POJAZDY_ID,
                    'test': KANAL_TESTOWY_ID
                }[kategoria]

                kanal = bot.get_channel(kanal_id)
                if kanal:
                    wiadomosc = f"```ansi\n{kolor_ansi}{linia_z_czasem}{ANSI_RESET}\n```"
                    try:
                        await kanal.send(wiadomosc)
                        print(f"Wysłano linię do {kategoria}")
                    except Exception as e:
                        print(f"Błąd wysyłania do {kategoria}: {e}")
                    await asyncio.sleep(0.8)  # ochrona przed rate-limit

            print(f"Wysłano {len(nowe_linje)} nowych linii")

            # Zapisujemy nowy stan
            with open(PLIK_STANU, 'w', encoding='utf-8') as f:
                f.write(f"{najnowszy}\n{len(linie)}\n")
            print("Stan zapisany")

        else:
            print("Brak nowych linii")

        print("=== KONIEC ===\n")

    except Exception as e:
        print(f"Błąd: {e}")

if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print(f"Flask nasłuchuje na porcie {os.getenv('PORT', 10000)}")
    bot.run(DISCORD_TOKEN)
