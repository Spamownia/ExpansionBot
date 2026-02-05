import discord
from discord.ext import commands, tasks
import ftplib
import io
import os
import datetime
import re
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Konfiguracja z env (Render)
DISCORD_TOKEN          = os.getenv("DISCORD_TOKEN")
FTP_HOST               = os.getenv("FTP_HOST")
FTP_PORT               = int(os.getenv("FTP_PORT", 51421))
FTP_USER               = os.getenv("FTP_USER")
FTP_PASS               = os.getenv("FTP_PASS")
FTP_LOG_DIR            = os.getenv("FTP_LOG_DIR", "/config/")
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", 300))

# Mapowanie kategorii → ID kanału Discord
CHANNEL_MAPPING = {
    "Airdrop":     int(os.getenv("CHANNEL_AIRDROP",     0)),
    "Safezone":    int(os.getenv("CHANNEL_SAFEZONE",    0)),
    "Quests":      int(os.getenv("CHANNEL_QUESTS",      0)),
    "Vehicle":     int(os.getenv("CHANNEL_VEHICLE",     0)),
    "AI":          int(os.getenv("CHANNEL_AI",          0)),
    "Market":      int(os.getenv("CHANNEL_MARKET",      0)),
    "BaseRaiding": int(os.getenv("CHANNEL_BASERAIDING", 0)),
    "Chat":        int(os.getenv("CHANNEL_CHAT",        0)),
    "Other":       int(os.getenv("CHANNEL_OTHER",       0)),   # fallback
}

# Wzorce rozpoznawania kategorii
CATEGORY_PATTERNS = {
    "Airdrop":     re.compile(r'\[MissionAirdrop\]'),
    "Safezone":    re.compile(r'\[Safezone\]'),
    "Quests":      re.compile(r'\[Expansion Quests\]'),
    "Vehicle":     re.compile(r'\[Vehicle(?:Enter|Leave|Engine|CarKey|Deleted|Cover)\]'),
    "AI":          re.compile(r'\[AI(?: Object Patrol| Patrol)\]'),
    "Market":      re.compile(r'\[Market\]'),
    "BaseRaiding": re.compile(r'\[BaseRaiding\]'),
    "Chat":        re.compile(r'\[Chat'),
}

class DayZLogBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)
        self.last_position = {}  # filename → ostatnia pozycja w bajtach

    async def setup_hook(self):
        self.check_logs.start()
        logger.info("Bot uruchomiony – cykliczne sprawdzanie logów aktywne")

    @tasks.loop(seconds=CHECK_INTERVAL_SECONDS)
    async def check_logs(self):
        if not DISCORD_TOKEN or not FTP_HOST:
            logger.error("Brak kluczowych zmiennych środowiskowych")
            return

        new_entries = await self.fetch_new_entries()
        if not new_entries:
            return

        for filename, lines in new_entries.items():
            grouped = self.group_lines_by_category(lines)

            for category, cat_lines in grouped.items():
                if not cat_lines:
                    continue

                channel_id = CHANNEL_MAPPING.get(category, CHANNEL_MAPPING.get("Other", 0))
                if channel_id == 0:
                    logger.warning(f"Brak kanału dla kategorii: {category}")
                    continue

                channel = self.get_channel(channel_id)
                if not channel:
                    logger.error(f"Nie znaleziono kanału {channel_id} dla {category}")
                    continue

                # Budujemy wiadomość
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                message = f"**{filename}**  ┇  **{category}**  ┇  {timestamp}\n\n"
                message += "\n".join(cat_lines[:40])  # limitujemy ilość linii w jednej wiadomości

                if len(cat_lines) > 40:
                    message += f"\n\n… i jeszcze {len(cat_lines)-40} linii"

                if len(message) > 1900:
                    message = message[:1890] + "… (obcięto)"

                try:
                    await channel.send(message)
                    logger.info(f"Wysłano {len(cat_lines)} linii → {category} ({channel.name})")
                except Exception as e:
                    logger.error(f"Błąd wysyłki do {category}: {e}")

    async def fetch_new_entries(self):
        new_data = {}
        try:
            with ftplib.FTP() as ftp:
                ftp.connect(FTP_HOST, FTP_PORT)
                ftp.login(FTP_USER, FTP_PASS)
                ftp.cwd(FTP_LOG_DIR)

                files = [f for f in ftp.nlst() if 'ExpLog' in f and f.endswith('.log')]

                for fn in files:
                    try:
                        size = ftp.size(fn)
                        last = self.last_position.get(fn, 0)

                        if size <= last:
                            continue

                        bio = io.BytesIO()
                        ftp.retrbinary(f"RETR {fn}", bio.write)
                        bio.seek(last)
                        new_content = bio.read().decode('utf-8', errors='replace')

                        lines = [l for l in new_content.splitlines() if l.strip()]
                        if lines:
                            new_data[fn] = lines

                        self.last_position[fn] = size
                        logger.info(f"{fn} → nowa pozycja: {size} B")

                    except ftplib.all_errors as e:
                        logger.warning(f"Błąd pobierania {fn}: {e}")

        except Exception as e:
            logger.error(f"Błąd FTP: {e}", exc_info=True)

        return new_data

    def group_lines_by_category(self, lines):
        groups = {cat: [] for cat in CATEGORY_PATTERNS}
        groups["Other"] = []

        for line in lines:
            matched = False
            for cat, pattern in CATEGORY_PATTERNS.items():
                if pattern.search(line):
                    groups[cat].append(line)
                    matched = True
                    break
            if not matched:
                groups["Other"].append(line)

        return groups

    @check_logs.before_loop
    async def before(self):
        await self.wait_until_ready()
        logger.info("Bot gotowy – start monitorowania logów")


bot = DayZLogBot()

@bot.event
async def on_ready():
    logger.info(f"Zalogowano jako {bot.user}")


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
