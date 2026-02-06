# main.py - Bot Discord do logów DayZ Expansion (Python 3.12)
import discord
from discord.ext import commands, tasks
import ftplib
import io
import os
import asyncio
from datetime import datetime
import re

# KONFIGURACJA - TYLKO TE 2 ZMIENNE W ENV NA RENDERZE!
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')  # Twój token
FTP_HOST = os.getenv('FTP_HOST', '147.93.162.60')
FTP_PORT = int(os.getenv('FTP_PORT', '51421'))
FTP_USER = os.getenv('FTP_USER', 'gpftp37275281809840533')
FTP_PASS = os.getenv('FTP_PASS', '8OhDv1P5')
FTP_LOG_DIR = os.getenv('FTP_LOG_DIR', '/config/ExpansionMod/Logs')

# ID KANAŁÓW DISCORD - ZMIEN TUTAJ SWOJE ID KANAŁÓW!
# (Prawy przycisk na kanale Discord → Kopiuj ID, włącz Developer Mode w Discord Settings)
KANAL_POJAZDY_ID = 1469089759958663403  # #log-pojazdy
KANAL_MISJE_ID = 1469089759958663403    # #log-misje  
KANAL_RYNEK_ID = 1469089759958663403    # #log-rynek
KANAL_STREFA_ID = 1469089759958663403   # #log-strefa
KANAL_AI_ID = 1469089759958663403       # #log-ai
KANAL_AIRDROP_ID = 1469089759958663403  # #log-airdrop
KANAL_RAIDING_ID = 1469089759958663403  # #log-raiding
KANAL_ZABICIA_ID = 1469089759958663403  # #log-kills (jeśli masz kill logi)
KANAL_CZAT_ID = 1469089759958663403     # #log-czat

# Kanały w słowniku
KANAŁY = {
    'pojazd': KANAL_POJAZDY_ID,
    'misje': KANAL_MISJE_ID,
    'rynek': KANAL_RYNEK_ID,
    'strefa': KANAL_STREFA_ID,
    'ai': KANAL_AI_ID,
    'airdrop': KANAL_AIRDROP_ID,
    'raiding': KANAL_RAIDING_ID,
    'zabicie': KANAL_ZABICIA_ID,
    'czat': KANAL_CZAT_ID
}

# Plik stanu
PLIK_STANU = 'stan.txt'

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'🚀 Bot wystartował jako {bot.user} | Sprawdzam logi co 5 min...')
    if not sprawdz_logi.is_running():
        sprawdz_logi.start()
    print(f'📡 Połączono z kanałami: {len([ch for ch in KANAŁY.values() if ch != 1234567890123456789])} aktywnych')

@tasks.loop(minutes=5)
async def sprawdz_logi():
    try:
        print('🔄 Sprawdzam nowe logi...')
        
        # Połączenie FTP
        ftp = ftplib.FTP()
        ftp.connect(FTP_HOST, FTP_PORT)
        ftp.login(FTP_USER, FTP_PASS)
        ftp.cwd(FTP_LOG_DIR)

        # Lista plików logów
        pliki = []
        ftp.retrlines('LIST', lambda x: pliki.append(x.split()[-1]) if 'ExpLog_' in x else None)
        pliki_log = [f for f in pliki if f.startswith('ExpLog_') and f.endswith('.log')]

        if not pliki_log:
            print('❌ Brak plików logów')
            ftp.quit()
            return

        # Najnowszy plik
        def data_pliku(nazwa):
            try:
                data_str = nazwa.split('ExpLog_')[1].split('.log')[0]
                return datetime.strptime(data_str, '%Y-%m-%d_%H-%M-%S')
            except:
                return datetime.min

        pliki_log.sort(key=data_pliku, reverse=True)
        najnowszy_log = pliki_log[0]
        print(f'📄 Znaleziono: {najnowszy_log}')

        # Stan poprzedni
        ostatni_plik = ''
        ostatnia_linia = 0
        if os.path.exists(PLIK_STANU):
            try:
                with open(PLIK_STANU, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if len(lines) >= 2:
                        ostatni_plik = lines[0].strip()
                        ostatnia_linia = int(lines[1].strip())
            except:
                pass

        # Pobierz log
        buffer = io.BytesIO()
        ftp.retrbinary(f'RETR {najnowszy_log}', buffer.write)
        buffer.seek(0)
        tekst = buffer.read().decode('utf-8', errors='ignore')
        linie = tekst.splitlines()

        # Nowe linie
        nowe_linje = linie if najnowszy_log != ostatni_plik else linie[ostatnia_linia:]
        print(f'📊 Nowych linii: {len(nowe_linje)}')

        if nowe_linje:
            # Klasyfikacja i wysyłka
            klasyfikacja = {
                'pojazd': [],
                'misje': [],
                'rynek': [],
                'strefa': [],
                'ai': [],
                'airdrop': [],
                'raiding': [],
                'zabicie': [],
                'czat': []
            }

            for linia in nowe_linje:
                kategoria = klasyfikuj_linie(linia)
                if kategoria:
                    klasyfikacja[kategoria].append(linia)

            # Wyślij do kanałów
            for kategoria, linie_kat in klasyfikacja.items():
                if linie_kat and KANAŁY[kategoria] != 1234567890123456789:
                    kanal = bot.get_channel(KANAŁY[kategoria])
                    if kanal:
                        wiadomosc = f"**📋 {kategoria.upper()} | {najnowszy_log}**\n" + '\n'.join(linie_kat[:10])
                        if len(wiadomosc) > 2000:
                            wiadomosc = wiadomosc[:1997] + '\n...i więcej!'
                        
                        try:
                            await kanal.send(wiadomosc)
                            print(f'✅ Wysłano {len(linie_kat)} linii do #{kategoria}')
                        except Exception as e:
                            print(f'❌ Błąd wysyłki do {kategoria}: {e}')

            # Zapisz stan
            with open(PLIK_STANU, 'w', encoding='utf-8') as f:
                f.write(f'{najnowszy_log}\n{len(linie)}\n')

        ftp.quit()
        print('✅ Sprawdzanie zakończone')

    except Exception as e:
        print(f'💥 BŁĄD: {e}')

def klasyfikuj_linie(linia):
    """Klasyfikuje linię logu do odpowiedniej kategorii"""
    linia_lower = linia.lower()
    
    if '[vehicle' in linia or 'vehicleenter' in linia_lower or 'vehicleleave' in linia_lower or 'vehicleengine' in linia_lower or 'vehiclecar' in linia_lower or 'vehicledeleted' in linia_lower:
        return 'pojazd'
    elif '[expansion quests]' in linia_lower:
        return 'misje'
    elif '[market]' in linia_lower:
        return 'rynek'
    elif '[safezone]' in linia_lower:
        return 'strefa'
    elif '[ai ' in linia or 'ai patrol' in linia_lower:
        return 'ai'
    elif '[missionairdrop]' in linia_lower:
        return 'airdrop'
    elif '[baseraiding]' in linia_lower:
        return 'raiding'
    elif '[kill' in linia:
        return 'zabicie'
    elif '[chat' in linia:
        return 'czat'
    return None

@bot.command(name='sprawdz')
@commands.has_permissions(administrator=True)
async def sprawdz_ręcznie(ctx):
    """!sprawdz - Ręczne sprawdzenie logów (tylko admin)"""
    await ctx.message.delete()
    await sprawdz_logi()
    await ctx.send('🔍 Sprawdzono logi ręcznie!', delete_after=5)

@bot.command(name='status')
async def status_bot(ctx):
    """!status - Status bota"""
    uptime = datetime.now() - bot.start_time if hasattr(bot, 'start_time') else 'Nieznany'
    msg = f"🤖 **Status bota:**\nOnline: ✅\nSprawdzanie: {'✅' if sprawdz_logi.is_running() else '❌'}\nKanały: {len([ch for ch in KANAŁY.values() if ch != 1234567890123456789])}\nUptime: {uptime}"
    await ctx.send(msg)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send('⛔ Brak uprawnień!', delete_after=5)

if __name__ == '__main__':
    if not DISCORD_TOKEN:
        print('❌ Brak DISCORD_TOKEN w zmiennych środowiskowych!')
        exit(1)
    
    bot.start_time = datetime.now()
    bot.run(DISCORD_TOKEN)
