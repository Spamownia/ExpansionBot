import os
import time
import re
import discord
from discord import Webhook, RequestsWebhookAdapter  # Dla webhooka, alternatywnie użyj discord.py async

# Konfiguracja
LOG_DIR = "/ścieżka/do/folderu/z/logami"  # Zmień na rzeczywistą ścieżkę
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/TWOJ_WEBHOOK_ID/TWOJ_WEBHOOK_TOKEN"  # Zmień na swój webhook URL

# Regex do nazwy pliku logów (ExpLog_YYYY-MM-DD_HH-MM-SS.log)
LOG_FILE_PATTERN = re.compile(r"ExpLog_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.log")

# Interesujące typy wydarzeń (na podstawie przykładów z Discorda i logów)
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

# Emoji dla wydarzeń (możesz dostosować)
EVENT_EMOJI = {
    "[VehicleDeleted]": "🟢",
    "[VehicleCarKey]": "🟢",
    "[MissionAirdrop]": "🟢",
    # Dodaj więcej jeśli potrzeba, default: "🟢"
}

# Funkcja do znalezienia najnowszego pliku logów
def get_latest_log_file():
    files = [f for f in os.listdir(LOG_DIR) if LOG_FILE_PATTERN.match(f)]
    if not files:
        return None
    # Sortuj po czasie modyfikacji (najnowszy na górze)
    files.sort(key=lambda f: os.path.getmtime(os.path.join(LOG_DIR, f)), reverse=True)
    return os.path.join(LOG_DIR, files[0])

# Funkcja do przetwarzania linii (filtruj i formatuj)
def process_line(line):
    # Szukaj daty i godziny na początku: np. 06:09:26.231
    match = re.match(r"(\d{2}:\d{2}:\d{2}\.\d{3}) \[(.*?)\]", line)
    if match:
        timestamp = match.group(1)
        event_type = f"[{match.group(2)}]"
        
        # Sprawdź czy to interesujące wydarzenie
        if any(event in line for event in INTERESTING_EVENTS):
            emoji = EVENT_EMOJI.get(event_type, "🟢")
            # Pełna data na podstawie nazwy pliku lub aktualnej daty (tutaj zakładam z pliku, ale upraszczam)
            full_timestamp = f"2026-02-{time.strftime('%d')} {timestamp}"  # Dostosuj do rzeczywistej daty z nazwy pliku
            formatted = f"{full_timestamp} {emoji} . {line.strip()}"
            return formatted
    return None

# Funkcja do wysyłania na Discorda via webhook
def send_to_discord(message):
    webhook = Webhook.from_url(DISCORD_WEBHOOK_URL, adapter=RequestsWebhookAdapter())
    webhook.send(content=message)  # Dla kolorów użyj embeds jeśli potrzeba

# Główna pętla bota
def main():
    current_file = None
    current_pos = 0  # Pozycja w pliku (offset)

    print("Bot wystartował o " + time.strftime("%Y-%m-%d %H:%M:%S"))
    send_to_discord("Bot wystartował " + time.strftime("%Y-%m-%d %H:%M:%S"))

    while True:
        latest = get_latest_log_file()
        if latest and latest != current_file:
            print(f"Przełączam się na nowy plik: {latest}")
            send_to_discord(f"🔄 Przełączono na nowy plik logów: {os.path.basename(latest)}")
            current_file = latest
            current_pos = 0  # Zaczynaj od początku nowego pliku lub os.stat(latest).st_size dla końca

        if current_file:
            try:
                with open(current_file, "r", encoding="utf-8", errors="ignore") as f:
                    f.seek(current_pos)
                    while True:
                        line = f.readline()
                        if not line:
                            break
                        formatted = process_line(line)
                        if formatted:
                            print(formatted)
                            send_to_discord(formatted)  # Wyślij na Discorda
                    current_pos = f.tell()  # Zapamiętaj pozycję
            except Exception as e:
                print(f"Błąd podczas czytania pliku: {e}")
                time.sleep(5)  # Retry po błędzie

        time.sleep(10)  # Sprawdzaj co 10 sekund (możesz zmniejszyć dla szybszego reagowania)

if __name__ == "__main__":
    main()
