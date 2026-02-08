# main.py - Bot logów DayZ – format: Data godzina_z_loga • treść (kolorowa kropka)
import discord
from discord.ext import commands, tasks
import ftplib
import io
import os
from datetime import datetime
import asyncio
import threading

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
KANAL_MISJE_ID   = 1469089759958663403
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

@bot.event
async def on_ready():
    teraz = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{teraz}] BOT URUCHOMIONY")

    kanal_test = bot.get_channel(KANAL_TESTOWY_ID)
    if kanal_test:
        await kanal_test.send(f"🟢 Bot wystartował {teraz}\nFormat: Data godzina_z_loga • treść loga (kolorowa kropka)")
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
                # Parsujemy godzinę zdarzenia z loga (pierwsze 8 znaków HH:MM:SS)
                if len(linia) >= 8 and linia[2] == ':' and linia[5] == ':':
                    godzina_z_loga = linia[:8]
                else:
                    godzina_z_loga = "--:--:--"

                # Kropka + kategoria (kolorowa •)
                kropka = "•"
                kategoria = 'test'

                if '[MissionAirdrop]' in linia:
                    kategoria = 'airdrop'
                    kropka = "🟡•"
                elif '[Expansion Quests]' in linia:
                    kategoria = 'misje'
                    kropka = "🔵•"
                elif '[BaseRaiding]' in linia:
                    kategoria = 'raiding'
                    kropka = "🔴•"
                elif any(x in linia for x in ['[Vehicle', 'VehicleDeleted', 'VehicleEnter', 'VehicleLeave', 'VehicleEngine', 'VehicleCarKey']):
                    kategoria = 'pojazdy'
                    kropka = "🟢•"

                # Format: Data godzina_z_loga • treść loga
                wiadomosc = f"{datetime.now().strftime('%Y-%m-%d')} {godzina_z_loga} {kropka} {linia}"

                kanal_id = {
                    'airdrop': KANAL_AIRDROP_ID,
                    'misje': KANAL_MISJE_ID,
                    'raiding': KANAL_RAIDING_ID,
                    'pojazdy': KANAL_POJAZDY_ID,
                    'test': KANAL_TESTOWY_ID
                }[kategoria]

                kanal = bot.get_channel(kanal_id)
                if kanal:
                    try:
                        await kanal.send(wiadomosc)
                        print(f"Wysłano linię do {kategoria}")
                    except Exception as e:
                        print(f"Błąd wysyłania do {kategoria}: {e}")
                    await asyncio.sleep(0.8)

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
