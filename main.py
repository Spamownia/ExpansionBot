# main.py - MINIMALNY DEBUG PARSER – tylko pokazuje czy czyta logi
import discord
from discord.ext import commands
import ftplib
import io
import os
from datetime import datetime
import asyncio

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
if not DISCORD_TOKEN:
    print("BRAK TOKENA → STOP")
    exit(1)

FTP_HOST = os.getenv('FTP_HOST', '147.93.162.60')
FTP_PORT = int(os.getenv('FTP_PORT', 51421))
FTP_USER = os.getenv('FTP_USER', 'gpftp37275281809840533')
FTP_PASS = os.getenv('FTP_PASS', '8OhDv1P5')
FTP_LOG_DIR = os.getenv('FTP_LOG_DIR', '/config/ExpansionMod/Logs')

KANAL_TESTOWY_ID = 1469089759958663403

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    teraz = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{teraz}] BOT URUCHOMIONY – on_ready")

    kanal = bot.get_channel(KANAL_TESTOWY_ID)
    if kanal:
        await kanal.send(f"🟢 Bot wystartował {teraz}\nRozpoczynam debug odczytu FTP...")
        print("Wysłano komunikat startowy")

    print("Próba połączenia FTP...")
    try:
        ftp = ftplib.FTP()
        ftp.connect(FTP_HOST, FTP_PORT)
        print("Połączono z FTP")
        ftp.login(FTP_USER, FTP_PASS)
        print("Zalogowano")
        ftp.cwd(FTP_LOG_DIR)
        print(f"Przeszedłem do katalogu: {FTP_LOG_DIR}")

        # Lista plików
        pliki = ftp.nlst()
        print(f"Pliki w katalogu: {pliki}")

        exp_logi = [f for f in pliki if f.startswith('ExpLog_') and f.endswith('.log')]
        if not exp_logi:
            print("Brak plików ExpLog_*")
            await kanal.send("Brak plików ExpLog_* w katalogu")
            ftp.quit()
            return

        # Najnowszy
        najnowszy = max(exp_logi, key=lambda f: datetime.strptime(f.split('ExpLog_')[1].split('.log')[0], '%Y-%m-%d_%H-%M-%S'))
        print(f"Najnowszy plik: {najnowszy}")

        # Pobieramy zawartość
        buf = io.BytesIO()
        ftp.retrbinary(f'RETR {najnowszy}', buf.write)
        ftp.quit()
        buf.seek(0)
        tekst = buf.read().decode('utf-8', errors='ignore')
        linie = tekst.splitlines()

        print(f"Liczba linii w pliku: {len(linie)}")

        if linie:
            pierwsze_20 = "\n".join(linie[:20])
            embed = discord.Embed(
                title=f"Pierwsze 20 linii z {najnowszy}",
                description=f"```log\n{pierwsze_20}\n```",
                color=0xFFFF00
            )
            await kanal.send(embed=embed)
            print("Wysłano pierwsze 20 linii")
        else:
            await kanal.send("Plik jest pusty")
            print("Plik pusty")

    except Exception as e:
        print(f"Błąd podczas odczytu FTP: {e}")
        if kanal:
            await kanal.send(f"Błąd FTP: {e}")

    print("=== DEBUG ZAKOŃCZONY ===")

bot.run(DISCORD_TOKEN)
