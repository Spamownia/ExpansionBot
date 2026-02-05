# bot.py
import discord
from discord.ext import commands, tasks
import ftplib
import io
import os
from datetime import datetime

# Pobierz zmienne środowiskowe (ustaw w Render lub .env)
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
FTP_HOST = os.getenv('FTP_HOST')
FTP_PORT = int(os.getenv('FTP_PORT', 21))  # Domyślnie 21, ale podano 51421
FTP_USER = os.getenv('FTP_USER')
FTP_PASS = os.getenv('FTP_PASS')
FTP_LOG_DIR = os.getenv('FTP_LOG_DIR')

# ID kanałów dla różnych typów logów - ustaw w env variables na Render
CHANNELS = {
    'vehicle': int(os.getenv('VEHICLE_CHANNEL_ID', 0)),  # Dla [Vehicle...
    'kill': int(os.getenv('KILL_CHANNEL_ID', 0)),        # Dla [Kill] (jeśli istnieją)
    'quests': int(os.getenv('QUESTS_CHANNEL_ID', 0)),    # Dla [Expansion Quests]
    'market': int(os.getenv('MARKET_CHANNEL_ID', 0)),    # Dla [Market]
    'safezone': int(os.getenv('SAFEZONE_CHANNEL_ID', 0)),# Dla [Safezone]
    'ai': int(os.getenv('AI_CHANNEL_ID', 0)),            # Dla [AI ...
    'airdrop': int(os.getenv('AIRDROP_CHANNEL_ID', 0)),  # Dla [MissionAirdrop]
    # Dodaj więcej jeśli potrzeba, np. 'baseraiding': int(os.getenv('BASERAIDING_CHANNEL_ID', 0)),
    # 'chat': int(os.getenv('CHAT_CHANNEL_ID', 0)),
}

# Stan: śledzenie ostatniego przetworzonego pliku i linii
STATE_FILE = 'state.txt'

bot = commands.Bot(command_prefix='!', intents=discord.Intents.default())

@bot.event
async def on_ready():
    print(f'Bot is ready as {bot.user}')
    check_logs.start()

@tasks.loop(minutes=5)  # Sprawdza co 5 minut
async def check_logs():
    try:
        # Połącz z FTP
        ftp = ftplib.FTP()
        ftp.connect(FTP_HOST, FTP_PORT)
        ftp.login(FTP_USER, FTP_PASS)
        ftp.cwd(FTP_LOG_DIR)

        # Pobierz listę plików
        files = [f for f in ftp.nlst() if f.startswith('ExpLog_') and f.endswith('.log')]

        if not files:
            print('No log files found.')
            ftp.quit()
            return

        # Sortuj pliki po dacie
        def parse_date(filename):
            date_str = filename.split('ExpLog_')[1].split('.log')[0]
            return datetime.strptime(date_str, '%Y-%m-%d_%H-%M-%S')

        files.sort(key=parse_date, reverse=True)
        latest_log = files[0]

        # Wczytaj stan
        last_file = ''
        last_line_num = 0
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                lines = f.readlines()
                if lines:
                    last_file = lines[0].strip()
                    last_line_num = int(lines[1].strip())

        # Pobierz zawartość
        content = io.BytesIO()
        ftp.retrbinary(f'RETR {latest_log}', content.write)
        content.seek(0)
        log_text = content.read().decode('utf-8', errors='ignore')
        lines = log_text.splitlines()

        # Nowe linie
        new_lines = []
        if latest_log != last_file:
            new_lines = lines
        else:
            new_lines = lines[last_line_num:]

        if new_lines:
            # Mapa keyword do typu kanału
            keyword_to_channel = {
                '[Vehicle': 'vehicle',
                '[Kill': 'kill',
                '[Expansion Quests]': 'quests',
                '[Market]': 'market',
                '[Safezone]': 'safezone',
                '[AI ': 'ai',
                '[MissionAirdrop]': 'airdrop',
                # Dodaj więcej, np. '[BaseRaiding]': 'baseraiding',
                # '[Chat - Admin]': 'chat',
            }

            for line in new_lines:
                for keyword, channel_type in keyword_to_channel.items():
                    if keyword in line:
                        channel_id = CHANNELS.get(channel_type, 0)
                        if channel_id != 0:
                            channel = bot.get_channel(channel_id)
                            if channel:
                                message = f'**Nowy wpis z {latest_log}:**\n{line}'
                                if len(message) > 2000:
                                    message = message[:1997] + '...'
                                await channel.send(message)
                        break  # Zakładamy, że linia pasuje tylko do jednego typu

            # Zapisz stan
            with open(STATE_FILE, 'w') as f:
                f.write(latest_log + '\n')
                f.write(str(len(lines)) + '\n')

        ftp.quit()
    except Exception as e:
        print(f'Error in check_logs: {e}')

@bot.command()
async def getlogs(ctx):
    await check_logs()
    await ctx.send('Sprawdzono logi.')

bot.run(DISCORD_TOKEN)
