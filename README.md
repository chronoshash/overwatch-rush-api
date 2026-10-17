# Overwatch Rush API

Read-only Community-API mit **quellenbasierten Stammdaten** zu *Overwatch Rush*
(Blizzard, Top-Down-Mobile-Hero-Shooter): Helden, Subklassen, Spielmodi, Maps und
Soft-Launch-Status.

> **Keine Spieldateien.** Dieses Repository enthält und verteilt keine
> APK/XAPK/OBB-Dateien. Es lädt auch keine herunter. Overwatch ist eine Marke von
> Blizzard Entertainment; dieses Projekt steht in keiner Verbindung zu Blizzard.

---

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

uvicorn app.main:app --host 0.0.0.0 --port 8000
# -> http://localhost:8000/docs
```

```bash
pytest            # 30 Tests
ruff check .      # Lint
ruff format --check .
```

## Endpunkte

| Methode | Pfad | Beschreibung |
|---|---|---|
| GET | `/health` | Liveness, Datenversion, Anzahl Datensätze |
| GET | `/v1/meta` | Spiel-Metadaten: Paket-ID, Soft-Launch-Regionen, Mindestanforderungen |
| GET | `/v1/heroes` | Helden; Filter `subclass`, `status`, `q`; `limit`/`offset` |
| GET | `/v1/heroes/{slug}` | Einzelheld (Slug **oder** Alias, z. B. `soldier-76`, `s76`) |
| GET | `/v1/roles` | Die fünf Rush-Subklassen |
| GET | `/v1/modes` | Spielmodi |
| GET | `/v1/maps` | Maps inkl. Overwatch-Vorlage |
| GET | `/v1/search?q=` | Suche über Helden, Modi und Maps |
| GET | `/docs` | Interaktive OpenAPI-UI |

### Beispiele

```bash
curl -s localhost:8000/v1/heroes?subclass=vanguard
curl -s localhost:8000/v1/heroes?status=upcoming
curl -s localhost:8000/v1/heroes/s76
curl -s "localhost:8000/v1/search?q=dorado"
```

Antwort-Envelope:

```json
{
  "data": [ ... ],
  "meta": { "data_version": "2026.10.17", "total": 2, "limit": 50, "offset": 0, "returned": 2 }
}
```

Fehler:

```json
{ "error": { "code": "unknown_subclass", "message": "Unknown subclass 'tank'.",
             "detail": { "valid": ["assassin", "fighter", "long_ranger", "utility", "vanguard"] } } }
```

Jede GET-JSON-Antwort trägt einen `ETag` und `Cache-Control: public, max-age=60`.
Mit `If-None-Match` antwortet der Dienst mit `304` und leerem Body.

## Datenqualität

Jeder Datensatz trägt `sources`, `verified_at` und `confidence`. Die Regeln:

1. **Primärquellen zuerst** – Blizzard-News, Play-/App-Store-Listing.
2. **Nichts wird geschätzt.** Fehlt eine belastbare Quelle, bleibt das Feld leer
   (`abilities: []`) statt mit Fantasiewerten gefüllt zu werden.
3. Sekundärquellen sind erlaubt, dann aber `confidence: medium`.
4. `data_version` = `updated_at` als `YYYY.MM.DD`; jede Änderung am Datenset
   erzeugt automatisch neue ETags.

Aktuell belegt: 9 spielbare Helden (Soft Launch), 3 angekündigte Helden,
5 Subklassen, 4 Modi, 3 Maps. Ability-Namen existieren nur dort, wo sie
öffentlich belegt sind (Brigitte: Shield Bash, Whip Shot).

Quellen (Auswahl):
- Blizzard News – Development Update: <https://news.blizzard.com/en-us/article/24244645/development-update-overwatch-rush>
- Google Play: <https://play.google.com/store/apps/details?id=com.blizzard.overwatch.rush>
- App Store: <https://apps.apple.com/id/app/overwatch-rush/id6758123632>
- esportsinsider (Subklassen): <https://esportsinsider.com/overwatch-rush-heroes>
- GosuGamers (Soft Launch): <https://www.gosugamers.net/entertainment/news/79054>
- esports.gg (Modi/Maps): <https://esports.gg/news/overwatch/overwatch-rush-to-release-in-malaysia-indonesia-and-the-philippines/>

## Lokale XAPK-Analyse (optional, nur für dich)

Der Sandbox-/CI-Weg braucht die Binärdatei **nie**. Willst du lokal Metadaten
prüfen, gilt: Download nur auf deinem Rechner, ins ignorierte `tmp/`, niemals
committen.

```bash
# 1) Datei lokal in tmp/ legen (tmp/ ist git-ignored)
bash scripts/fetch_xapk.sh "<url-die-du-nutzen-darfst>" overwatch-rush.xapk

# 2) Metadaten auslesen (stdlib-only, keine Assets)
python scripts/ingest_local.py tmp/overwatch-rush.xapk

# 3) optional: APKs entpacken + aapt2-Permissions lesen
python scripts/ingest_local.py tmp/overwatch-rush.xapk --extract

# -> data/incoming/apk-report.json  (git-ignored)
```

Das Skript kopiert das Paket nicht, lädt nichts hoch, extrahiert standardmäßig
nichts und blockiert Pfad-Traversal beim Entpacken. Ergebnis ist ein
Metadaten-Report (Paket-ID, Version, Split-APKs, SHA-256, optional Permissions) –
**keine** Spiel-Assets.

## Projektstruktur

```
app/
  main.py        FastAPI-Routen, Envelopes, Fehlerbehandlung, ETag-Middleware
  models.py      Pydantic-Modelle, extra="forbid", Quellen-Validierung
  store.py       Laden + strikte Startvalidierung, Referenz-Checks
  cache.py       ETag-Berechnung
data/            Das eigentliche Datenset (JSON, versioniert)
scripts/         fetch_xapk.sh (lokal), ingest_local.py (Metadaten)
tests/           30 Tests: API, Datenintegrität, Ingest, Binary-Guard
```

Datenänderungen erfolgen in `data/*.json`; `pytest` erzwingt danach gültige
Quellen und Referenzen. Siehe [SPEC.md](SPEC.md) für Ziele und Ausschlüsse,
[TESTING.md](TESTING.md) für Nachweise und [AGENTS.md](AGENTS.md) für Regeln.

## Bekannte Einschränkungen

- Keine Ability-/Stat-Daten: für Rush-Kits existiert keine belastbare
  öffentliche Quelle, und Blizzard hat Kits bewusst gegenüber Overwatch 2
  verändert.
- Subklassen der drei angekündigten Helden stammen aus einem Sekundärbericht
  (`confidence: medium`).
- Der Soft-Launch-Status ist ein Stichtag (`verified_at`), keine Live-Abfrage.
- Keine Datenbank, keine Schreib-API, keine Auth – bewusst (v0.1).

## Lizenz

Code: MIT (siehe [LICENSE](LICENSE)). Die Daten sind Zusammenstellungen
öffentlich dokumentierter Fakten mit Quellenangabe. „Overwatch“ und zugehörige
Marken sind Eigentum von Blizzard Entertainment.
