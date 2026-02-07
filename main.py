# main.py - Bot logów DayZ Expansion – ANSI kolory w logach + kolorowe embedy
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
    MAGENTA  = "\033[95m"
    CYAN     = "\033[96m"
    WHITE    = "\033[97m"

# ==================================================
# KONFIGURACJA – Twoje ID kanałów
# ==================================================

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
if not DISCORD_TOKEN:
    print(f"{ANSI.RED}{ANSI.BOLD}BRAK DISCORD_TOKEN → STOP{ANSI.RESET}")
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

PLIK_STANU = 'stan.txt'

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Flask – wymagany dla Web Service
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
# KOLORY EMBEDÓW NA DISCORD + ANSI w logach
# ==================================================

KOLOR_AIRDROP  = 0xFFAA00   # pomarańczowy
KOLOR_MISJE    = 0x00AAFF   # jasnoniebieski
KOLOR_RAIDING  = 0xFF0000   # czerwony
KOLOR_POJAZDY  = 0x00FF88   # jasnozielony
KOLOR_TEST     = 0xAAAAAA   # szary

ANSI_AIRDROP  = ANSI.YELLOW
ANSI_MISJE    = ANSI.BLUE
ANSI_RAIDING  = ANSI.RED
ANSI_POJAZDY  = ANSI.GREEN
ANSI_TEST     = ANSI.WHITE
ANSI_ERROR    = ANSI.RED
ANSI_INFO     = ANSI.CYAN

# ==================================================
# BOT
# ==================================================

@bot.event
async def on_ready():
    teraz = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{ANSI_INFO}{ANSI.BOLD}[{teraz}] BOT URUCHOMIONY – on_ready OK{ANSI.RESET}")

    # Wymuszamy odczyt całego logu przy KAŻDYM starcie
    if os.path.exists(PLIK_STANU):
        os.remove(PLIK_STANU)
        print(f"{ANSI.YELLOW}Usunięto stan.txt – wymuszony odczyt CAŁEGO logu{ANSI.RESET}")

    # Komunikat startowy
    kanal_test = bot.get_channel(KANAL_TESTOWY_ID)
    if kanal_test:
        embed = discord.Embed(
            title="🟢 Bot HusariaEXAPL wystartował",
            description=f"Data: {teraz}\nOdczyt całego najnowszego logu przy starcie\nLinie rozdzielane na kanały wg kategorii",
            color=0x00FF00
        )
        embed.set_footer(text="Sprawdzanie co 60 sekund")
        await kanal_test.send(embed=embed)
        print(f"{ANSI.GREEN}Wysłano komunikat startowy{ANSI.RESET}")

    print(f"{ANSI.CYAN}Pierwsze sprawdzenie logów – zaraz...{ANSI.RESET}")
    await sprawdz_logi()

    if not sprawdz_logi.is_running():
        sprawdz_logi.start()

@tasks.loop(seconds=60)
async def sprawdz_logi():
    teraz = datetime.now().strftime("%H:%M:%S")
    print(f"{ANSI.CYAN}{ANSI.BOLD}[{teraz}] === START sprawdzania FTP ==={ANSI.RESET}")

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

        # Stan
        ostatni_plik = ''
        ostatnia_linia = 0
        if os.path.exists(PLIK_STANU):
            with open(PLIK_STANU, 'r', encoding='utf-8') as f:
                dane = f.read().strip().split('\n')
                if len(dane) >= 2:
                    ostatni_plik = dane[0]
                    ostatnia_linia = int(dane[1])

        print(f"{ANSI.WHITE}Stan: plik={ostatni_plik}, linia={ostatnia_linia}{ANSI.RESET}")

        buf = io.BytesIO()
        ftp.retrbinary(f'RETR {najnowszy}', buf.write)
        ftp.quit()
        buf.seek(0)
        tekst = buf.read().decode('utf-8', errors='ignore')
        linie = tekst.splitlines()

        print(f"{ANSI.CYAN}Całkowita liczba linii w pliku: {len(linie)}{ANSI.RESET}")

        nowe_linje = linie if najnowszy != ostatni_plik else linie[ostatnia_linia:]
        print(f"{ANSI.YELLOW}Nowe linie do przetworzenia: {len(nowe_linje)}{ANSI.RESET}")

        if nowe_linje:
            # Słownik: kategoria → (kanał, kolor_embed, ansi_kolor, nazwa)
            kategorie = {
                'airdrop':  (bot.get_channel(KANAL_AIRDROP_ID),  0xFFAA00, ANSI_AIRDROP,  "Airdrop"),
                'misje':    (bot.get_channel(KANAL_MISJE_ID),    0x00AAFF, ANSI_MISJE,    "Misje / Quests"),
                'raiding':  (bot.get_channel(KANAL_RAIDING_ID),  0xFF0000, ANSI_RAIDING,  "Raiding / Bazy"),
                'pojazdy':  (bot.get_channel(KANAL_POJAZDY_ID),  0x00FF88, ANSI_POJAZDY,  "Pojazdy"),
                'test':     (bot.get_channel(KANAL_TESTOWY_ID),  0xAAAAAA, ANSI_TEST,     "Inne / Test")
            }

            wysłane = 0
            for linia in nowe_linje:
                kategoria = 'test'

                if '[MissionAirdrop]' in linia:
                    kategoria = 'airdrop'
                elif '[Expansion Quests]' in linia:
                    kategoria = 'misje'
                elif '[BaseRaiding]' in linia:
                    kategoria = 'raiding'
                elif any(x in linia for x in ['[Vehicle', 'VehicleDeleted', 'VehicleEnter', 'VehicleLeave', 'VehicleEngine', 'VehicleCarKey']):
                    kategoria = 'pojazdy'

                kanal, kolor, ansi_kolor, nazwa = kategorie[kategoria]

                if kanal:
                    embed = discord.Embed(
                        description=f"```log\n{linia}\n```",
                        color=kolor,
                        timestamp=datetime.now()
                    )
                    embed.set_author(name=nazwa)
                    embed.set_footer(text=f"{najnowszy} • {teraz}")

                    try:
                        await kanal.send(embed=embed)
                        wysłane += 1
                        print(f"{ansi_kolor}Wysłano linię do {nazwa} ({kategoria}){ANSI.RESET}")
                    except Exception as e:
                        print(f"{ANSI_ERROR}Błąd wysyłania do {nazwa}: {e}{ANSI.RESET}")
                    await asyncio.sleep(0.9)

            print(f"{ANSI.GREEN}{ANSI.BOLD}Wysłano łącznie {wysłane} linii{ANSI.RESET}")

            with open(PLIK_STANU, 'w', encoding='utf-8') as f:
                f.write(f"{najnowszy}\n{len(linie)}\n")
            print(f"{ANSI.GREEN}Stan zapisany{ANSI.RESET}")

        else:
            print(f"{ANSI.YELLOW}Brak nowych linii{ANSI.RESET}")

        print(f"{ANSI.CYAN}=== KONIEC sprawdzania ==={ANSI.RESET}\n")

    except Exception as e:
        print(f"{ANSI.RED}Błąd sprawdzania: {type(e).__name__} → {e}{ANSI.RESET}")

if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print(f"{ANSI.CYAN}Flask nasłuchuje na porcie {os.getenv('PORT', 10000)}{ANSI.RESET}")
    bot.run(DISCORD_TOKEN)
