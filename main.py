# main.py - Bot logów DayZ Expansion – odczyt CAŁEGO najnowszego logu CO 60 SEKUND (test)
import discord
from discord.ext import commands, tasks
import ftplib
import io
import os
from datetime import datetime
import asyncio
import threading

# ==================================================
# KONFIGURACJA – Zmień tylko ID kanałów
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

# ID kanałów – ZMIEŃ NA SWOJE PRAWDZIWE
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
    print(f"[{teraz}] === START sprawdzania FTP (tryb: odczyt CAŁEGO pliku) ===")

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

        # IGNORUJEMY stan – zawsze odczytujemy CAŁY plik
        print("Tryb testowy: ignoruję stan.txt – odczytuję CAŁY plik")

        buf = io.BytesIO()
        ftp.retrbinary(f'RETR {najnowszy}', buf.write)
        ftp.quit()
        buf.seek(0)
        tekst = buf.read().decode('utf-8', errors='ignore')
        linie = tekst.splitlines()

        print(f"Całkowita liczba linii w pliku: {len(linie)}")

        # Wysyłamy WSZYSTKIE linie (testowo – potem możesz ograniczyć do ostatnich N linii)
        nowe_linje = linie
        print(f"Wysyłam wszystkie {len(nowe_linje)} linie (tryb testowy)")

        if nowe_linje:
            # Słownik: kategoria → (kanał, kolor, nazwa)
            kategorie = {
                'airdrop':  (bot.get_channel(KANAL_AIRDROP_ID),  0xFFAA00, "Airdrop"),
                'misje':    (bot.get_channel(KANAL_MISJE_ID),    0x00AAFF, "Misje / Quests"),
                'raiding':  (bot.get_channel(KANAL_RAIDING_ID),  0xFF0000, "Raiding / Bazy"),
                'pojazdy':  (bot.get_channel(KANAL_POJAZDY_ID),  0x00FF88, "Pojazdy"),
                'test':     (bot.get_channel(KANAL_TESTOWY_ID),  0xAAAAAA, "Inne / Test")
            }

            wysłane = 0
            for linia in nowe_linje:
                kategoria = 'test'

                # Przypisanie kategorii
                if '[MissionAirdrop]' in linia:
                    kategoria = 'airdrop'
                elif '[Expansion Quests]' in linia:
                    kategoria = 'misje'
                elif '[BaseRaiding]' in linia:
                    kategoria = 'raiding'
                elif any(x in linia for x in ['[Vehicle', 'VehicleDeleted', 'VehicleEnter', 'VehicleLeave', 'VehicleEngine', 'VehicleCarKey']):
                    kategoria = 'pojazdy'

                kanal, kolor, nazwa = kategorie[kategoria]

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
                        print(f"Wysłano linię do {nazwa} ({kategoria})")
                    except Exception as e:
                        print(f"Błąd wysyłania do {nazwa}: {e}")
                    await asyncio.sleep(0.8)  # ochrona przed rate-limit

            print(f"Wysłano łącznie {wysłane} linii (cały plik)")

        else:
            print("Brak linii do wysłania (pusty plik?)")

        print("=== KONIEC sprawdzania ===\n")

    except Exception as e:
        print(f"Błąd sprawdzania: {type(e).__name__} → {e}")

if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print(f"Flask nasłuchuje na porcie {os.getenv('PORT', 10000)}")
    bot.run(DISCORD_TOKEN)
