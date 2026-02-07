# main.py - Bot logów DayZ Expansion – AGRESYWNY TEST: odczyt CAŁEGO logu co 60 s
import discord
from discord.ext import commands, tasks
import ftplib
import io
import os
from datetime import datetime
import asyncio
import threading

# ==================================================
# KONFIGURACJA – tylko Twój kanał testowy
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

KANAL_TESTOWY_ID = 1469089759958663403   # ← Twój kanał testowy

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Flask – do utrzymania usługi
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
# BOT – AGRESYWNY PARSER
# ==================================================

@bot.event
async def on_ready():
    teraz = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{teraz}] BOT URUCHOMIONY")

    kanal = bot.get_channel(KANAL_TESTOWY_ID)
    if kanal:
        embed = discord.Embed(
            title="🟢 Bot HusariaEXAPL wystartował",
            description=f"Data: {teraz}\n**TRYB TESTOWY** – odczyt CAŁEGO logu co 60 sekund\nPowinny przyjść wszystkie linie",
            color=0x00FF00
        )
        embed.set_footer(text="Jeśli nic nie przyjdzie – sprawdź logi Render")
        await kanal.send(embed=embed)
        print("Wysłano komunikat startowy")

    # Wymuszamy odczyt całego logu przy starcie
    if os.path.exists('stan.txt'):
        os.remove('stan.txt')
        print("Usunięto stan.txt – wymuszony odczyt całego logu przy starcie")

    await sprawdz_logi()  # pierwsze od razu
    if not sprawdz_logi.is_running():
        sprawdz_logi.start()

@tasks.loop(seconds=60)
async def sprawdz_logi():
    teraz = datetime.now().strftime("%H:%M:%S")
    print(f"[{teraz}] === START – odczyt CAŁEGO najnowszego pliku ===")

    try:
        ftp = ftplib.FTP()
        ftp.connect(FTP_HOST, FTP_PORT)
        ftp.login(FTP_USER, FTP_PASS)
        ftp.cwd(FTP_LOG_DIR)

        pliki = []
        ftp.retrlines('LIST', lambda line: pliki.append(line.split()[-1]))
        pliki_log = [f for f in pliki if f.startswith('ExpLog_') and f.endswith('.log')]

        if not pliki_log:
            print("Brak plików ExpLog_* na FTP")
            ftp.quit()
            return

        def parse_date(f):
            try:
                return datetime.strptime(f.split('ExpLog_')[1].split('.log')[0], '%Y-%m-%d_%H-%M-%S')
            except:
                return datetime.min

        pliki_log.sort(key=parse_date, reverse=True)
        najnowszy = pliki_log[0]
        print(f"Najnowszy plik: {najnowszy}")

        # Zawsze CAŁY plik – ignorujemy stan (tryb testowy)
        print("Tryb testowy: odczyt CAŁEGO pliku bez stanu.txt")

        buf = io.BytesIO()
        ftp.retrbinary(f'RETR {najnowszy}', buf.write)
        ftp.quit()
        buf.seek(0)
        tekst = buf.read().decode('utf-8', errors='ignore')
        linie = tekst.splitlines()

        print(f"Liczba linii w pliku: {len(linie)}")

        if linie:
            kanal = bot.get_channel(KANAL_TESTOWY_ID)
            if kanal:
                print("Wysyłam cały log w paczkach po 10 linii...")

                chunk_size = 10
                for i in range(0, len(linie), chunk_size):
                    part = linie[i:i+chunk_size]
                    embed = discord.Embed(
                        title=f"Log {najnowszy} – część {i//chunk_size + 1}",
                        description="```log\n" + "\n".join(part) + "\n```",
                        color=0xFFFF00,
                        timestamp=datetime.now()
                    )
                    embed.set_footer(text=f"Linie {i+1}–{min(i+chunk_size, len(linie))}")
                    await kanal.send(embed=embed)
                    print(f"Wysłano paczkę {i//chunk_size + 1} ({len(part)} linii)")
                    await asyncio.sleep(1.5)  # ochrona przed rate-limit

                print(f"Wysłano cały log – {len(linie)} linii")
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
