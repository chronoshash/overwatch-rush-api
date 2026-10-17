# AGENTS.md

Regeln für Agenten, die in diesem Repo arbeiten. Gültig ab 2026-10-17.

## Harte Grenzen

1. **Keine Spieldateien.** Niemals `*.apk`, `*.xapk`, `*.apks`, `*.aab`, `*.obb`
   committen, hochladen, in Releases hängen oder weitergeben. `tmp/`,
   `data/incoming/`, `extracted/` sind git-ignored und bleiben lokal.
2. **Keine Download-Automatisierung in CI.** `scripts/fetch_xapk.sh` ist ein
   manuelles Werkzeug für autorisierte lokale Nutzung.
3. **Keine erfundenen Daten.** Jeder neue Datensatz braucht `sources`
   (https), `verified_at` und `confidence`. Unbelegte Felder bleiben leer.
4. **Keine Live-Spielerdaten.** Kein Scraping von Blizzard-Endpunkten, keine
   Reverse-Engineering-APIs, kein TLS-MITM, keine fremden Accounts. Begründung
   und Alternativen: `SPEC.md` Abschnitt 2a.
5. **Datamining nur für Fakten.** Statische Werte dürfen lokal gescannt werden
   (`scripts/scan_game_data.py`); in `data/*.json` kommen nur Namen/Zahlen mit
   Quellenangabe. Keine extrahierten Assets, Texte oder Client-Dateien im Repo.
6. **Markenrechte respektieren.** Kein Branding, das eine offizielle
   Blizzard-Verbindung suggeriert.

## Arbeitsweise

- Spezifikation vor Code: Änderungen an Zielen/Endpunkten zuerst in `SPEC.md`.
- Kleine Schritte: Datenänderung → `pytest` → `ruff check .` →
  `ruff format --check .`.
- Neue Endpunkte brauchen: Response-Model, Test in `tests/test_api.py`,
  Eintrag in `README.md` und der Endpunktliste in `SPEC.md`.
- Neue Datenfelder brauchen: Feld in `app/models.py` (mit Validierung),
  Wert in `data/*.json`, Test in `tests/test_data.py`.
- Definition of Done: Tests grün, Lint sauber, keine Binaries im Git-Index,
  `data_version`/`updated_at` aktualisiert.

## Datenpflege

- Soft-Launch-Status ändert sich: `data/game.json` → `soft_launch`, `data_version`.
- Held hinzufügen: `slug` (kebab-case), `subclass` muss in `roles.json` existieren,
  `status` ist `live` oder `upcoming`.
- Quellen-URLs müssen `https://` sein; keine Mirror-/APK-Portale als Quelle.
- Bei widersprüchlichen Quellen: Primärquelle (Blizzard/Store) gewinnt,
  Widerspruch in `notes` dokumentieren.

## Server starten

Immer `bash scripts/serve.sh` (setzt Proxy-Header, bindet `0.0.0.0`, nutzt `exec`).
Kein `uvicorn ... &` aus einer Bash-Zelle – verwaiste Prozesse überleben und
blockieren Ports. Nach dem Stoppen prüfen: `ss -ltn | grep 8000`.

## Verifikation

```bash
pip install -r requirements-dev.txt
ruff check . && ruff format --check .
pytest
```

Details und Nachweise: [TESTING.md](TESTING.md). Ziele/Ausschlüsse: [SPEC.md](SPEC.md).
