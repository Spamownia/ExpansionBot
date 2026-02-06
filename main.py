# ... (reszta kodu bez zmian, tylko zmień funkcję sprawdz_logi na tę)

@tasks.loop(seconds=60)
async def sprawdz_logi():
    teraz = datetime.now().strftime("%H:%M:%S")
    print(f"[{teraz}] === START sprawdzania FTP – odczyt CAŁEGO pliku === ")

    try:
        ftp = ftplib.FTP()
        ftp.connect(FTP_HOST, FTP_PORT)
        ftp.login(FTP_USER, FTP_PASS)
        ftp.cwd(FTP_LOG_DIR)

        pliki = [f for f in ftp.nlst() if f.startswith('ExpLog_') and f.endswith('.log')]
        if not pliki:
            print("Brak plików ExpLog_*")
            ftp.quit()
            return

        def parse_date(f):
            try:
                return datetime.strptime(f.split('ExpLog_')[1].split('.log')[0], '%Y-%m-%d_%H-%M-%S')
            except:
                return datetime.min

        pliki.sort(key=parse_date, reverse=True)
        najnowszy = pliki[0]
        print(f"Najnowszy plik: {najnowszy}")

        # IGNORUJEMY stan całkowicie – zawsze cały plik
        print("Tryb testowy: odczyt CAŁEGO pliku bez stanu")

        buf = io.BytesIO()
        ftp.retrbinary(f'RETR {najnowszy}', buf.write)
        ftp.quit()
        buf.seek(0)
        tekst = buf.read().decode('utf-8', errors='ignore')
        linie = tekst.splitlines()

        print(f"Całkowita liczba linii: {len(linie)}")

        if linie:
            kanal_test = bot.get_channel(KANAL_TESTOWY_ID)
            if kanal_test:
                embed = discord.Embed(
                    title=f"Cały najnowszy log ({najnowszy}) – test",
                    description="Wysyłam pierwsze 10 linii (testowo)",
                    color=0xFFFF00
                )
                embed.add_field(name="Pierwsze linie", value="```log\n" + "\n".join(linie[:10]) + "\n```", inline=False)
                await kanal_test.send(embed=embed)
                print("Wysłano pierwsze 10 linii na testowy kanał")

        else:
            print("Plik pusty lub błąd odczytu")

        print("=== KONIEC ===\n")

    except Exception as e:
        print(f"Błąd: {type(e).__name__} → {e}")
