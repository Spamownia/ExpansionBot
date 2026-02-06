# main.py - Bot logów DayZ Expansion - odczyt całego najnowszego logu przy starcie
import discord
from discord.ext import commands, tasks
import ftplib
import io
import os
from datetime import datetime
import asyncio
import threading

# ==================================================
# KONFIGURACJA – Zmień tylko ID kanału testowego!
# ==================================================

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
if not DISCORD_TOKEN:
    print("BRAK TOKENA → STOP")
    exit(1)

FTP_HOST = os.getenv('FTP_HOST', '147.93.162.60')
FTP_PORT = int(os.getenv('FTP_PORT', 51421))
FTP_USER = os.getenv('FTP_USER', 'gpftp37275281809840533')
FTP_PASS = os.getenv('FTP_PASS', '8OhDv1P5')
FTP_LOG_DIR = os.getenv('FTP_LOG_DIR', '/config/ExpansionMod/Logs')

KANAŁ_TESTOWY_ID = 1234567890123456789          # ← ZMIEŃ NA PRAWDZIWE ID KANAŁU TESTOWEGO

PLIK_STANU = 'stan.txt'

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Flask – wymagany do Web Service na Render
from flask import Flask
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot logów DayZ Expansion działa"

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
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] BOT URUCHOMIONY jako {bot.user}")

    # Usuwamy plik stanu przy KAŻDYM starcie → odczyt całego najnowszego logu
    if os.path.exists(PLIK_STANU):
        os.remove(PLIK_STANU)
        print("Usunięto plik stanu → odczytam CAŁY najnowszy log")

    kanal = bot.get_channel(KANAŁ_TESTOWY_ID)
    if kanal:
        try:
            await kanal.send(
                f"🟢 **BOT RESTART / DEPLOY** {datetime.now():%Y-%m-%d %H:%M:%S}\n"
                f"• Zalogowano pomyślnie\n"
                f"• Odczyt CAŁEGO najnowszego logu przy starcie\n"
                f"• Sprawdzanie co 60 sekund\n"
                f"• Wszystkie nowe linie → ten kanał (test)"
            )
            print("Wysłano komunikat startowy")
        except Exception as e:
            print(f"Błąd wysyłania startowego: {e}")
    else:
        print(f"Nie znaleziono kanału testowego {KANAŁ_TESTOWY_ID}")

    print("Pierwsze sprawdzenie logów – zaraz...")
    await sprawdz_logi()           # ← natychmiast po starcie
    sprawdz_logi.start()

@tasks.loop(seconds=60)
async def sprawdz_logi():
    print(f"[{datetime.now():%H:%M:%S}] === START sprawdzania FTP ===")
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

        # Najnowszy plik
        def parse_date(f):
            try:
                return datetime.strptime(f.split('ExpLog_')[1].split('.log')[0], '%Y-%m-%d_%H-%M-%S')
            except:
                return datetime.min

        pliki.sort(key=parse_date, reverse=True)
        najnowszy = pliki[0]
        print(f"Najnowszy plik: {najnowszy}")

        # Stan (po usunięciu przy starcie będzie pusty → odczyt całego pliku)
        ostatni_plik = ''
        ostatnia_linia = 0
        if os.path.exists(PLIK_STANU):
            with open(PLIK_STANU, 'r', encoding='utf-8') as f:
                dane = f.read().strip().split('\n')
                if len(dane) >= 2:
                    ostatni_plik = dane[0]
                    ostatnia_linia = int(dane[1])

        print(f"Stan: plik={ostatni_plik}, linia={ostatnia_linia}")

        # Pobierz zawartość
        buf = io.BytesIO()
        ftp.retrbinary(f'RETR {najnowszy}', buf.write)
        ftp.quit()
        buf.seek(0)
        tekst = buf.read().decode('utf-8', errors='ignore')
        linie = tekst.splitlines()
        print(f"Całkowita liczba linii w pliku: {len(linie)}")

        nowe_linje = linie if najnowszy != ostatni_plik else linie[ostatnia_linia:]
        print(f"Nowe linie do przetworzenia: {len(nowe_linje)}")

        if nowe_linje:
            kanal = bot.get_channel(KANAŁ_TESTOWY_ID)
            if kanal:
                print("Wysyłam wszystkie nowe linie na kanał testowy...")
                chunk_size = 10
                for i in range(0, len(nowe_linje), chunk_size):
                    part = nowe_linje[i:i+chunk_size]
                    msg = f"**Nowe linie ({najnowszy}) – część {i//chunk_size + 1}**\n```log\n"
                    msg += "\n".join(part)
                    msg += "\n```"
                    if len(msg) > 1950:
                        msg = msg[:1950] + "\n... (zbyt długie)"
                    await kanal.send(msg)
                    print(f"Wysłano chunk {i//chunk_size + 1}")
                    await asyncio.sleep(1.5)  # ochrona przed rate-limit

            # Zapisz stan (po wysłaniu)
            with open(PLIK_STANU, 'w', encoding='utf-8') as f:
                f.write(f"{najnowszy}\n{len(linie)}\n")
            print("Stan zapisany")

        else:
            print("Brak nowych linii")

        print("=== KONIEC sprawdzania ===\n")

    except Exception as e:
        print(f"Błąd podczas sprawdzania: {type(e).__name__}: {e}")

if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print(f"Flask nasłuchuje na porcie {os.getenv('PORT', 10000)}")
    bot.run(DISCORD_TOKEN)
