import os
import sys
from threading import Thread
from flask import Flask
import asyncio
import socket

# Tylko to, co na pewno istnieje w carim-discord-bot 2.2.5
from carim_discord_bot.rcon.rcon_protocol import RconProtocol

app = Flask(__name__)
app.config['PROPAGATE_EXCEPTIONS'] = True


@app.route('/')
def home():
    return "CARIM DayZ Bot is running! 🚀"


@app.route('/health')
@app.route('/ping')
def health_check():
    return "OK", 200


def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)


async def rcon_connection_loop():
    host = os.environ.get('RCON_IP', '').strip()
    port_str = os.environ.get('RCON_PORT', '3705').strip()
    password = os.environ.get('RCON_PASSWORD', '')

    if not host or not port_str or not password:
        print("BRAK RCON_IP / RCON_PORT / RCON_PASSWORD – RCon wyłączony")
        await asyncio.sleep(3600)  # śpij godzinę
        return

    try:
        port = int(port_str)
    except ValueError:
        print(f"Nieprawidłowy RCON_PORT: '{port_str}'")
        return

    print(f"Łączenie RCon: {host}:{port}")

    loop = asyncio.get_running_loop()

    # Ręczny resolve (już wiemy, że działa)
    try:
        addr_info = socket.getaddrinfo(host, port, family=socket.AF_INET, type=socket.SOCK_DGRAM)
        sockaddr = addr_info[0][4]
        print(f"Resolved: {sockaddr}")
    except Exception as e:
        print(f"Błąd resolve IP/port: {e}")
        return

    # Tworzymy transport z RconProtocol
    try:
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: RconProtocol(password),
            local_addr=('0.0.0.0', 0),
            remote_addr=sockaddr
        )
        print("=== RCON POŁĄCZENIE UDANE! ===")
        print("Transport i protokół utworzone")

        # Prosty loop – co 60 s wysyłamy "players" (możesz zmienić)
        while True:
            await asyncio.sleep(60)
            try:
                protocol.send_command("players")
                print("Wysłano: players")
            except Exception as e:
                print(f"Błąd wysyłania komendy: {e}")
                break  # lub reconnect, jeśli chcesz

        transport.close()
    except Exception as e:
        print(f"Błąd create_datagram_endpoint: {e}")


if __name__ == '__main__':
    print("=== MAIN START ===")
    print(f"RCON_IP   : '{os.environ.get('RCON_IP')}'")
    print(f"RCON_PORT : '{os.environ.get('RCON_PORT')}'")
    print(f"RCON_PASSWORD length: {len(os.environ.get('RCON_PASSWORD', ''))}")

    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print("Flask keep-alive uruchomiony")

    # Uruchamiamy asyncio loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(rcon_connection_loop())
    except KeyboardInterrupt:
        print("Wyłączanie...")
    except Exception as e:
        print(f"Błąd asyncio loop: {e}")
    finally:
        loop.close()
