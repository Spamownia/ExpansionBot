import discord
from discord.ext import commands, tasks
import ftplib
import io
import os
import datetime
import re
import logging

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Konfiguracja z zmiennych środowiskowych (Render używa env vars)
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
FTP_HOST = os.getenv("FTP_HOST")
FTP_PORT = int(os.getenv("FTP_PORT", 21))
FTP_USER = os.getenv("FTP_USER")
FTP_PASS = os.getenv("FTP_PASS")
FTP_LOG_DIR = os.getenv("FTP_LOG_DIR", "/config/")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", 300))

# Które logi nas interesują
LOG_PATTERNS = {
    'Airdrop':      re.compile(r'\[MissionAirdrop\]'),
    'Safezone':     re.compile(r'\[Safezone\]'),
    'Quests':       re.compile(r'\[Expansion Quests\]'),
    'Vehicle':      re.compile(r'\[Vehicle(?:Enter|Leave|Engine|CarKey|Deleted|Cover)\]'),
    'AI':           re.compile(r'\[AI(?: Object Patrol| Patrol)\]'),
    'Market':       re.compile(r'\[Market\]'),
    'BaseRaiding':  re.compile(r'\[BaseRaiding\]'),
    'Chat':         re.compile(r'\[Chat'),
}

class DayZLogBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)
        self.last_position = {}     # filename → ostatnia pozycja (w bajtach)

    async def setup_hook(self):
        self.check_logs.start()
        logger.info("Bot wystartował – zadanie cykliczne uruchomione")

    @tasks.loop(seconds=CHECK_INTERVAL_SECONDS)
    async def check_logs(self):
        if not DISCORD_TOKEN or not FTP_HOST or not DISCORD_CHANNEL_ID:
            logger.error("Brakuje kluczowych zmiennych środowiskowych!")
            return

        channel = self.get_channel(DISCORD_CHANNEL_ID)
        if not channel:
            logger.error(f"Nie znaleziono kanału o ID {DISCORD_CHANNEL_ID}")
            return

        new_entries = await self.fetch_new_log_entries()
        if not new_entries:
            logger.info("Brak nowych wpisów w logach")
            return

        for filename, lines in new_entries.items():
            if not lines:
                continue

            grouped = self.group_by_category(lines)
            for category, cat_lines in grouped.items():
                if not cat_lines:
                    continue

                message = f"**{filename}**  •  **{category}**  •  {datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n\n"
                message += "\n".join(cat_lines)

                # Discord limit 2000 znaków
                if len(message) > 1900:
                    message = message[:1890] + "… (wiadomość obcięta)"

                try:
                    await channel.send(message)
                    logger.info(f"Wysłano {len(cat_lines)} linii [{category}] z {filename}")
                except discord.HTTPException as e:
                    logger.error(f"Błąd wysyłania wiadomości: {e}")

    async def fetch_new_log_entries(self):
        new_data = {}
        try:
            with ftplib.FTP() as ftp:
                ftp.connect(FTP_HOST, FTP_PORT)
                ftp.login(FTP_USER, FTP_PASS)
                ftp.cwd(FTP_LOG_DIR)

                files = [f for f in ftp.nlst() if f.endswith('.log') and 'ExpLog' in f]

                for filename in files:
                    try:
                        size = ftp.size(filename)
                        last_pos = self.last_position.get(filename, 0)

                        if size <= last_pos:
                            continue

                        bio = io.BytesIO()
                        ftp.retrbinary(f"RETR {filename}", bio.write)
                        bio.seek(last_pos)
                        new_bytes = bio.read()
                        new_text = new_bytes.decode('utf-8', errors='replace').rstrip('\r\n')

                        if new_text:
                            lines = [line for line in new_text.splitlines() if line.strip()]
                            if lines:
                                new_data[filename] = lines

                        self.last_position[filename] = size
                        logger.info(f"Przetworzono {filename} – nowa pozycja: {size} bajtów")

                    except ftplib.all_errors as e:
                        logger.warning(f"Błąd podczas pobierania {filename}: {e}")

        except Exception as e:
            logger.error(f"Błąd połączenia FTP: {e}", exc_info=True)

        return new_data

    def group_by_category(self, lines):
        grouped = {cat: [] for cat in LOG_PATTERNS}
        grouped['Inne'] = []

        for line in lines:
            matched = False
            for cat, pattern in LOG_PATTERNS.items():
                if pattern.search(line):
                    grouped[cat].append(line)
                    matched = True
                    break
            if not matched:
                grouped['Inne'].append(line)

        return {k: v for k, v in grouped.items() if v}

    @check_logs.before_loop
    async def before_check(self):
        await self.wait_until_ready()
        logger.info("Bot gotowy – rozpoczynam cykliczne sprawdzanie logów")


bot = DayZLogBot()

@bot.event
async def on_ready():
    logger.info(f"Zalogowano jako {bot.user} (ID: {bot.user.id})")


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        logger.critical("DISCORD_TOKEN nie jest ustawiony!")
        exit(1)
    bot.run(DISCORD_TOKEN)
