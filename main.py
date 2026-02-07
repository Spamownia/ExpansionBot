# main.py - Bot logów DayZ Expansion – agresywny parser całego logu
import discord
from discord.ext import commands, tasks
import ftplib
import io
import os
from datetime import datetime
import asyncio
import threading

# ANSI kolory dla logów Render (konsola)
class ANSI:
    RESET    = "\033[0m"
    BOLD     = "\033[1m"
    RED      = "\033[91m"
    GREEN    = "\033[92m"
    YELLOW   = "\033[93m"
    BLUE     = "\033[94m"
    CYAN     = "\033[96m"
    WHITE    = "\033[97m"

# ==================================================
# KONFIGURACJA – Twój kanał testowy
# ==================================================

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
if not DISCORD_TOKEN:
    print(f"{ANSI.RED}BRAK TOKENA – STOP{ANSI.RESET}")
    exit(1)

FTP_HOST = os.getenv('FTP_HOST', '147.93.162.60')
FTP_PORT = int(os.getenv('FTP_PORT', 51421))
FTP_USER = os.getenv('FTP_USER', 'gpftp37275281809840533')
FTP_PASS = os.getenv('FTP_PASS', '8OhDv1P5')
FTP_LOG_DIR = os.getenv('FTP_LOG_DIR', '/config/ExpansionMod/Logs')

KANAL_TESTOWY_ID = 1469089759958663403   # ← Twój testowy kanał

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

# ==================================================
# BOT – PARSER
# ==================================================

@bot.event
async def on_ready():
    teraz = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{ANSI.CYAN}{ANSI.BOLD}[{teraz}] BOT URUCHOMIONY – on_ready OK{ANSI.RESET}")

    # Wymuszamy odczyt całego logu
    if os.path.exists('stan.txt'):
        os.remove('stan.txt')
        print(f"{ANSI.YELLOW}Usunięto stan.txt – odczyt CAŁEGO logu przy starcie{ANSI.RESET}")

    kanal = bot.get_channel(KANAL_TESTOWY_ID)
    if kanal:
        embed = discord.Embed(
            title="🟢 Bot HusariaEXAPL wystartował",
            description=f"Data: {teraz}\nOdczyt **całego** najnowszego logu co 60 sekund (tryb testowy)",
            color=0x00FF00
        )
        embed.set_footer(text="Powinny przyjść wszystkie linie")
        await kanal.send(embed=embed)
        print(f"{ANSI.GREEN}Wysłano komunikat startowy{ANSI.RESET}")

    await sprawdz_logi()
    if not sprawdz_logi.is_running():
        sprawdz_logi.start()

@tasks.loop(seconds=60)
async def sprawdz_logi():
    teraz = datetime.now().strftime("%H:%M:%S")
    print(f"{ANSI.CYAN}{ANSI.BOLD}[{teraz}] === START – odczyt CAŁEGO najnowszego pliku ==={ANSI.RESET}")

    try:
        ftp = ftplib.FTP()
        ftp.connect(FTP_HOST, FTP_PORT)
        ftp.login(FTP_USER, FTP_PASS)
        ftp.cwd(FTP_LOG_DIR)

        pliki = [f for f in ftp.nlst() if f.startswith('ExpLog_') and f.endswith('.log')]
        if not pliki:
            print(f"{ANSI.RED}Brak plików ExpLog_*{ANSI.RESET}")
            ftp.quit()
            return

        def parse_date(f):
            try:
                return datetime.strptime(f.split('ExpLog_')[1].split('.log')[0], '%Y-%m-%d_%H-%M-%S')
            except:
                return datetime.min

        pliki.sort(key=parse_date, reverse=True)
        najnowszy = pliki[0]
        print(f"{ANSI.YELLOW}Najnowszy plik: {najnowszy}{ANSI.RESET}")

        # Zawsze CAŁY plik (testowo ignorujemy stan)
        print(f"{ANSI.BLUE}Tryb testowy: odczyt CAŁEGO pliku bez stanu{ANSI.RESET}")

        buf = io.BytesIO()
        ftp.retrbinary(f'RETR {najnowszy}', buf.write)
        ftp.quit()
        buf.seek(0)
        tekst = buf.read().decode('utf-8', errors='ignore')
        linie = tekst.splitlines()

        print(f"{ANSI.CYAN}Całkowita liczba linii w pliku: {len(linie)}{ANSI.RESET}")

        if linie:
            kanal = bot.get_channel(KANAL_TESTOWY_ID)
            if kanal:
                print(f"{ANSI.GREEN}Wysyłam cały log w paczkach po 10 linii...{ANSI.RESET}")

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
                    print(f"{ANSI.GREEN}Wysłano paczkę {i//chunk_size + 1} ({len(part)} linii){ANSI.RESET}")
                    await asyncio.sleep(1.2)  # unikamy rate-limitu

                print(f"{ANSI.GREEN}{ANSI.BOLD}Wysłano cały log – {len(linie)} linii{ANSI.RESET}")
        else:
            print(f"{ANSI.YELLOW}Plik pusty lub błąd odczytu{ANSI.RESET}")

        print(f"{ANSI.CYAN}=== KONIEC ==={ANSI.RESET}\n")

    except Exception as e:
        print(f"{ANSI.RED}Błąd: {e}{ANSI.RESET}")

if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print(f"{ANSI.CYAN}Flask nasłuchuje na porcie {os.getenv('PORT', 10000)}{ANSI.RESET}")
    bot.run(DISCORD_TOKEN)
