# main.py - Bot monitorujący logi DayZ Expansion na Render (Web Service)
import discord
from discord.ext import commands, tasks
import ftplib
import io
import os
from datetime import datetime
import asyncio
import threading

# ────────────────────────────────────────────────
# KONFIGURACJA – ZMIEŃ TYLKO TE ID KANAŁÓW
# ────────────────────────────────────────────────

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
if not DISCORD_TOKEN:
    print("BRAK DISCORD_TOKEN W ŚRODOWISKU → ZATRZYMUJĘ BOTA")
    exit(1)

FTP_HOST = os.getenv('FTP_HOST', '147.93.162.60')
FTP_PORT = int(os.getenv('FTP_PORT', 51421))
FTP_USER = os.getenv('FTP_USER', 'gpftp37275281809840533')
FTP_PASS = os.getenv('FTP_PASS', '8OhDv1P5')
FTP_LOG_DIR = os.getenv('FTP_LOG_DIR', '/config/ExpansionMod/Logs')

# ───── ID KANAŁÓW – WPISZ SWOJE PRAWDZIWE ID ─────
KANAŁ_TESTOWY_ID = 1234567890123456789      # ← kanał na WSZYSTKIE nowe linie (test)
KANAL_POJAZD_ID  = 1234567890123456789
KANAL_MISJE_ID   = 1234567890123456789
KANAL_RYNEK_ID   = 1234567890123456789
KANAL_STREFA_ID  = 1234567890123456789
KANAL_AI_ID      = 1234567890123456789
KANAL_AIRDROP_ID = 1234567890123456789
KANAL_RAIDING_ID = 1234567890123456789

# Słownik kanałów
KANAŁY = {
    'pojazd':   KANAL_POJAZD_ID,
    'misje':    KANAL_MISJE_ID,
    'rynek':    KANAL_RYNEK_ID,
    'strefa':   KANAL_STREFA_ID,
    'ai':       KANAL_AI_ID,
    'airdrop':  KANAL_AIRDROP_ID,
    'raiding':  KANAL_RAIDING_ID,
}

PLIK_STANU = 'stan.txt'

intents = discord.Intents.default()
intents.message_content = True          # wymagany do komend i czytania wiadomości

bot = commands.Bot(command_prefix='!', intents=intents)

# ────────────────────────────────────────────────
# FLASK – żeby Render nie zabił usługi (konieczne dla Web Service)
# ────────────────────────────────────────────────

from flask import Flask
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "HusariaBot – monitor logów DayZ Expansion – działa"

@flask_app.route('/health')
def health():
    return "OK", 200

def run_flask():
    port = int(os.getenv('PORT', 10000))
    flask_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ────────────────────────────────────────────────
# BOT – główne funkcje
# ────────────────────────────────────────────────

@bot.event
async def on_ready():
    print(f'===== BOT URUCHOMIONY =====')
    print(f'Zalogowano jako: {bot.user} (ID: {bot.user.id})')
    print(f'Serwery: {len(bot.guilds)}')

    # ──── Komunikat startowy na kanał testowy ────
    test_kanal = bot.get_channel(KANAŁ_TESTOWY_ID)
    if test_kanal:
        try:
            await test_kanal.send(
                f"🟢 **HusariaBot wystartował** – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"• Nasłuchuję logów z FTP co ~5 min\n"
                f"• Wszystkie nowe linie idą na ten kanał (test)\n"
                f"• Gotowy do pracy!"
            )
            print("Wysłano komunikat startowy")
        except Exception as e:
            print(f"Błąd wysyłania startowego: {e}")
    else:
        print(f"Nie znaleziono kanału testowego {KANAŁ_TESTOWY_ID}")

    if not sprawdz_logi.is_running():
        sprawdz_logi.start()
        print("Uruchomiono pętlę sprawdzającą logi")

@tasks.loop(minutes=5)  # na testy możesz zmienić na seconds=45
async def sprawdz_logi():
    print("=== Sprawdzam logi FTP ===")
    try:
        ftp = ftplib.FTP()
        ftp.connect(FTP_HOST, FTP_PORT)
        ftp.login(FTP_USER, FTP_PASS)
        ftp.cwd(FTP_LOG_DIR)

        pliki = [f for f in ftp.nlst() if f.startswith('ExpLog_') and f.endswith('.log')]
        if not pliki:
            print("Brak plików logów")
            ftp.quit()
            return

        # Najnowszy plik
        def data_z_nazwy(n):
            try:
                return datetime.strptime(n.split('ExpLog_')[1].split('.log')[0], '%Y-%m-%d_%H-%M-%S')
            except:
                return datetime.min

        pliki.sort(key=data_z_nazwy, reverse=True)
        najnowszy = pliki[0]
        print(f"Najnowszy plik: {najnowszy}")

        # Stan
        ostatni_plik = ''
        ostatnia_linia = 0
        if os.path.exists(PLIK_STANU):
            with open(PLIK_STANU, 'r', encoding='utf-8') as f:
                linie = f.readlines()
                if len(linie) >= 2:
                    ostatni_plik = linie[0].strip()
                    ostatnia_linia = int(linie[1].strip())

        # Pobierz zawartość
        buf = io.BytesIO()
        ftp.retrbinary(f'RETR {najnowszy}', buf.write)
        ftp.quit()
        buf.seek(0)
        tekst = buf.read().decode('utf-8', errors='ignore')
        wszystkie_linje = tekst.splitlines()

        nowe_linje = wszystkie_linje if najnowszy != ostatni_plik else wszystkie_linje[ostatnia_linia:]
        print(f"Nowe linie: {len(nowe_linje)}")

        if nowe_linje:
            # ──── WSZYSTKO NA KANAŁ TESTOWY ────
            test_k = bot.get_channel(KANAŁ_TESTOWY_ID)
            if test_k:
                for i in range(0, len(nowe_linje), 12):
                    part = nowe_linje[i:i+12]
                    msg = f"**Nowe linie – {najnowszy}** (część {i//12 + 1})\n```log\n" + "\n".join(part) + "\n```"
                    if len(msg) > 1990:
                        msg = msg[:1950] + "\n... (skrócone)"
                    await test_k.send(msg)
                    await asyncio.sleep(1.2)  # unikamy rate limitu

            # ──── Normalna klasyfikacja i wysyłka ────
            for linia in nowe_linje:
                kategoria = None
                if any(x in linia for x in ['[Vehicle', 'VehicleEnter', 'VehicleLeave', 'VehicleEngine', 'VehicleCarKey']):
                    kategoria = 'pojazd'
                elif '[Expansion Quests]' in linia:
                    kategoria = 'misje'
                elif '[Market]' in linia:
                    kategoria = 'rynek'
                elif '[Safezone]' in linia:
                    kategoria = 'strefa'
                elif '[AI ' in linia:
                    kategoria = 'ai'
                elif '[MissionAirdrop]' in linia:
                    kategoria = 'airdrop'
                elif '[BaseRaiding]' in linia:
                    kategoria = 'raiding'

                if kategoria and KANAŁY.get(kategoria, 0) != 1234567890123456789:
                    kanal = bot.get_channel(KANAŁY[kategoria])
                    if kanal:
                        msg = f"**{kategoria.upper()}** – {najnowszy}\n```log\n{linia}\n```"
                        await kanal.send(msg)

            # Zapisz stan
            with open(PLIK_STANU, 'w', encoding='utf-8') as f:
                f.write(f"{najnowszy}\n{len(wszystkie_linje)}\n")

        print("=== Sprawdzenie zakończone ===")

    except Exception as e:
        print(f"Błąd sprawdzania logów: {e}")

# ────────────────────────────────────────────────
# START – Flask w tle + bot
# ────────────────────────────────────────────────

if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print(f"HTTP health nasłuchuje na porcie {os.getenv('PORT', 10000)}")

    bot.run(DISCORD_TOKEN)
