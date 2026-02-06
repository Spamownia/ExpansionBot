# main.py - Bot logów DayZ Expansion – odczyt CAŁEGO najnowszego logu co 60 s (test)
import discord
from discord.ext import commands, tasks   # ← TO JEST NAJWAŻNIEJSZA LINIA – tasks MUSI być tutaj
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

KANAL_TESTOWY_ID = 1469089759958663403
KANAL_AIRDROP_ID = 1469089759958663403
KANAL_MISJE_ID   = 1469089759958663403
KANAL_RAIDING_ID = 1469089759958663403
KANAL_POJAZDY_ID = 1469089759958663403

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Flask – do utrzymania Web Service przy życiu
from flask import Flask
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot logów DayZ działa"

@flask_app.route('/health')
def health():
    return "OK", 200

def run_flask():
    port = int(os.getenv('PORT', 10000))
    flask_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ==================================================
# BOT
# ==================================================

@bot.event
async def on_ready():
    teraz = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{teraz}] BOT URUCHOMIONY – on_ready OK")

    kanal_test = bot.get_channel(KANAL_TESTOWY_ID)
    if kanal_test:
        embed = discord.Embed(
            title="🟢 Bot HusariaEXAPL wystartował",
            description=f"Data: {teraz}\nOdczyt CAŁEGO najnowszego logu przy KAŻDYM sprawdzeniu\nLinie rozdzielane na kanały wg kategorii",
            color=0x00FF00
        )
        embed.set_footer(text="Sprawdzanie co 60 sekund – tryb testowy")
        await kanal_test.send(embed=embed)
        print("Wysłano komunikat startowy")

    print("Pierwsze sprawdzenie logów – zaraz...")
    await sprawdz_logi()

    if not sprawdz_logi.is_running():
        sprawdz_logi.start()

@tasks.loop(seconds=60)
async def sprawdz_logi():
    teraz = datetime.now().strftime("%H:%M:%S")
    print(f"[{teraz}] === START sprawdzania FTP – odczyt CAŁEGO pliku === ")

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

        # IGNORUJEMY stan – zawsze odczytujemy CAŁY plik (tryb testowy)
        print("Tryb testowy: ignoruję stan.txt – odczytuję CAŁY plik")

        buf = io.BytesIO()
        ftp.retrbinary(f'RETR {najnowszy}', buf.write)
        ftp.quit()
        buf.seek(0)
        tekst = buf.read().decode('utf-8', errors='ignore')
        linie = tekst.splitlines()

        print(f"Całkowita liczba linii: {len(linie)}")

        if linie:
            kanal_test = bot.get_channel(KANAL_TESTOWY_ID)
            if kanal_test:
                embed = discord.Embed(
                    title=f"Cały najnowszy log ({najnowszy}) – test",
                    description="Wysyłam pierwsze 10 linii (testowo)",
                    color=0xFFFF00
                )
                embed.add_field(name="Pierwsze linie", value="```log\n" + "\n".join(linie[:10]) + "\n```", inline=False)
                await kanal_test.send(embed=embed)
                print("Wysłano pierwsze 10 linii na testowy kanał")

        else:
            print("Plik pusty lub błąd odczytu")

        print("=== KONIEC ===\n")

    except Exception as e:
        print(f"Błąd: {type(e).__name__} → {e}")

if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print(f"Flask nasłuchuje na porcie {os.getenv('PORT', 10000)}")
    bot.run(DISCORD_TOKEN)
