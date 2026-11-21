# RolnikSzukaWody

Zespół **GeoSatel** · HackNation 2026 · zadanie KOWR „Zatrzymaj wodę, chroń plony”.

Pełne README (uruchomienie, architektura, źródła danych, licencje) powstanie w trakcie prac — patrz `plan.md`, rozdz. M10.

**Działająca wersja:** https://129.121.162.156.sslip.io (VPS, wdrażana z `main` skryptem `deploy/deploy.sh`).

## Uruchomienie (Docker)

Wymagany jest tylko Docker z Compose v2. Żaden klucz API nie jest potrzebny.

```bash
docker compose up -d --build        # http://localhost  (Caddy na porcie 80 → aplikacja)
docker compose logs -f app          # logi (bez adresów IP)
docker compose down                 # zatrzymanie; raporty i cache zostają w wolumenie app-data
```

Z własną domeną (automatyczny certyfikat HTTPS z Let's Encrypt): `SITE_ADDRESS=moja.domena.pl docker compose up -d --build`.

### Wdrożenie na VPS

1. Jednorazowo na serwerze (Ubuntu, root): `scp deploy/setup-vps.sh root@<IP>:/root/ && ssh root@<IP> bash /root/setup-vps.sh`
   (Docker, 2 GB swap, zapora: tylko 22/80/443).
2. Z własnego komputera, z czystego `main`: `deploy/deploy.sh root@<IP> [domena]`. Bez domeny aplikacja dostaje adres
   `https://<IP>.sslip.io`. Skrypt buduje obraz na serwerze, czeka na `/api/health` i rozgrzewa cache (`scripts/warm_cache.py`).

Zabezpieczenia: limit analiz na klienta (10/min i 30/10 min, `RSW_RATE_LIMIT_*`) i zapytań o działkę (120/min), liczony po skrócie adresu
z losową solą, który nie jest nigdzie zapisywany · limit równoległych analiz · nagłówki bezpieczeństwa i CSP w Caddy ·
aplikacja jako użytkownik bez uprawnień root, port API niewystawiony na zewnątrz · logi bez adresów IP · brak sekretów.
