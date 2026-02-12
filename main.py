import os
import time
import re

# ────────────────────────────────────────────────
# KONFIGURACJA – zmień tylko te dwie linie!
# ────────────────────────────────────────────────
LOG_DIR = "/config/ExpansionMod/Logs"                     # np. "/app/logs" lub "/opt/render/project/src/logs"
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/TWOJ_ID/TWOJ_TOKEN"

# Regex do plików logów
LOG_FILE_PATTERN = re.compile(r"ExpLog_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.log")

# Wydarzenia, które chcesz łapać
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

# ────────────────────────────────────────────────
def get_latest_log_file():
    files = [f for f in os.listdir(LOG_DIR) if LOG_FILE_PATTERN.match(f)]
    if not files:
        return None
    # najnowszy wg czasu modyfikacji pliku
    files.sort(key=lambda f: os.path.getmtime(os.path.join(LOG_DIR, f)), reverse=True)
    return os.path.join(LOG_DIR, files[0])

# ────────────────────────────────────────────────
def process_line(line):
    # Szukamy linii w stylu: 12:33:19.123 [Expansion Quests] ...
    match = re.match(r"(\d{2}:\d{2}:\d{2}\.\d{3}) \[(.*?)\]", line)
    if not match:
        return None

    timestamp = match.group(1)
    event_type = f"[{match.group(2)}]"

    if not any(ev in line for ev in INTERESTING_EVENTS):
        return None

    emoji = "🟢"  # możesz później dodać mapę emoji jak wcześniej
    full_ts = f"2026-02-12 {timestamp}"   # ← hardcoded, możesz parsować z nazwy pliku
    formatted = f"{full_ts} {emoji} . {line.strip()}"
    return formatted

# ────────────────────────────────────────────────
def send_to_discord(message):
    from discord import Webhook, RequestsWebhookAdapter
    webhook = Webhook.from_url(DISCORD_WEBHOOK_URL, adapter=RequestsWebhookAdapter())
    webhook.send(content=message)

# ────────────────────────────────────────────────
def main():
    current_file = None
    current_pos = 0
    last_size = 0

    print("Bot wystartował o " + time.strftime("%Y-%m-%d %H:%M:%S"))
    send_to_discord("Bot wystartował " + time.strftime("%Y-%m-%d %H:%M:%S"))

    while True:
        latest = get_latest_log_file()
        if not latest:
            print("Brak plików logów – czekam 30 s")
            time.sleep(30)
            continue

        if latest != current_file:
            print(f"Przełączam się na nowy plik: {os.path.basename(latest)}")
            send_to_discord(f"🔄 Przełączono na nowy plik logów: {os.path.basename(latest)}")
            current_file = latest
            current_pos = 0
            last_size = 0

        try:
            stat = os.stat(current_file)
            current_size = stat.st_size

            if current_size == last_size:
                # plik się nie zmienił → oszczędzamy cykle
                time.sleep(60)
                continue

            with open(current_file, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(current_pos)
                while True:
                    line = f.readline()
                    if not line:
                        break
                    formatted = process_line(line.strip())
                    if formatted:
                        print(formatted)
                        send_to_discord(formatted)
                current_pos = f.tell()
                last_size = current_size

        except Exception as e:
            print(f"Błąd przy czytaniu {current_file}: {e}")
            time.sleep(15)

        time.sleep(10)  # podstawowe opóźnienie pętli

if __name__ == "__main__":
    main()
