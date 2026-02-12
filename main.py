import os
import time
import re
from discord import SyncWebhook, Embed  # ← Nowe importy dla v2.0+

# ────────────────────────────────────────────────
# KONFIGURACJA – zmień te wartości!
# ────────────────────────────────────────────────
LOG_DIR = "/ścieżka/do/folderu/z/logami"  # np. "/app/logs" lub "/opt/render/project/src/logs"
WEBHOOK_URL = "https://discord.com/api/webhooks/TWOJ_ID/TWOJ_TOKEN"  # ← Twój webhook URL

# Regex do wykrywania plików logów
LOG_FILE_PATTERN = re.compile(r"ExpLog_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.log")

# Wydarzenia, które Cię interesują
INTERESTING_EVENTS = [
    "[MissionAirdrop]",
    "[VehicleDeleted]",
    "[VehicleDestroyed]",
    "[VehicleCarKey]",
    "[VehicleEnter]",
    "[VehicleLeave]",
    "[VehicleEngine]",
    "[Expansion Quests]",
    "[BaseRaiding]",
    "[AI Object Patrol]",
    "[Safezone]"
]

# Emoji dla różnych typów (możesz rozszerzyć)
EVENT_EMOJI = {
    "[VehicleDeleted]": "🗑️",
    "[VehicleCarKey]": "🔑",
    "[MissionAirdrop]": "📦",
    "[VehicleDestroyed]": "💥",
    "[Expansion Quests]": "📜",
    "[BaseRaiding]": "🛡️",
    "[AI Object Patrol]": "🤖",
    "[Safezone]": "🟢",
    # default poniżej
}

# ────────────────────────────────────────────────
def get_latest_log_file():
    files = [f for f in os.listdir(LOG_DIR) if LOG_FILE_PATTERN.match(f)]
    if not files:
        return None
    files.sort(key=lambda f: os.path.getmtime(os.path.join(LOG_DIR, f)), reverse=True)
    return os.path.join(LOG_DIR, files[0])

# ────────────────────────────────────────────────
def process_line(line: str, current_date: str = "2026-02-12"):
    # Przykład: 12:33:19 [Expansion Quests] ...
    match = re.match(r"(\d{2}:\d{2}:\d{2}\.\d{3}) \[(.*?)\]", line)
    if not match:
        return None

    timestamp = match.group(1)
    event_type = f"[{match.group(2)}]"

    if not any(ev in line for ev in INTERESTING_EVENTS):
        return None

    emoji = EVENT_EMOJI.get(event_type, "🟢")
    full_ts = f"{current_date} {timestamp}"
    content = line.strip()

    return full_ts, emoji, event_type, content

# ────────────────────────────────────────────────
def send_to_discord(full_ts: str, emoji: str, event_type: str, content: str):
    webhook = SyncWebhook.from_url(WEBHOOK_URL)

    # Można dodać embed dla ładniejszego wyglądu
    embed = Embed(
        description=content,
        color=0x00ff00 if "🟢" in emoji else 0xffaa00  # zielony / pomarańczowy
    )
    embed.set_author(name=f"{emoji} {event_type}")
    embed.set_footer(text=full_ts)

    webhook.send(embed=embed, username="DayZ Log Bot", avatar_url="https://i.imgur.com/..." )  # opcjonalny avatar

# ────────────────────────────────────────────────
def main():
    current_file = None
    current_pos = 0
    last_size = 0

    print("Bot wystartował o", time.strftime("%Y-%m-%d %H:%M:%S"))
    webhook = SyncWebhook.from_url(WEBHOOK_URL)
    webhook.send(content="Bot wystartował " + time.strftime("%Y-%m-%d %H:%M:%S"))

    while True:
        latest = get_latest_log_file()
        if not latest:
            print("Brak plików logów – czekam...")
            time.sleep(30)
            continue

        if latest != current_file:
            print(f"Przełączam się na nowy plik: {os.path.basename(latest)}")
            webhook.send(content=f"🔄 Przełączono na nowy plik: {os.path.basename(latest)}")
            current_file = latest
            current_pos = 0
            last_size = 0

        try:
            stat = os.stat(current_file)
            if stat.st_size == last_size:
                # Plik się nie zmienił → pomijamy (jak w Twoich logach)
                time.sleep(60)  # sprawdzaj co minutę
                continue

            with open(current_file, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(current_pos)
                lines = f.readlines()
                current_pos = f.tell()
                last_size = stat.st_size

                for line in lines:
                    result = process_line(line.strip())
                    if result:
                        ts, emoji, etype, cont = result
                        print(f"{ts} {emoji} {cont}")
                        send_to_discord(ts, emoji, etype, cont)

        except Exception as e:
            print(f"Błąd przy czytaniu {current_file}: {e}")
            time.sleep(10)

        time.sleep(10)  # podstawowe opóźnienie pętli

if __name__ == "__main__":
    main()
