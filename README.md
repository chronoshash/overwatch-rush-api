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

bash scripts/serve.sh
# -> http://localhost:8000  (Startseite)  ·  /docs (OpenAPI)
# anderer Port:  PORT=8080 bash scripts/serve.sh
```

```bash
pytest            # 33 Tests
ruff check .      # Lint
ruff format --check .
```

### Warum `scripts/serve.sh` statt `uvicorn` direkt?

Der Dienst läuft hinter einem Preview-Proxy, deshalb setzt das Skript:

- `--host 0.0.0.0` – sonst ist der Port von außen nicht erreichbar
- `--proxy-headers --forwarded-allow-ips='*'` – `X-Forwarded-Proto/Host` werden
  respektiert, statt Container-lokaler Werte
- `--timeout-keep-alive 65` – hält Verbindungen für Proxies offen
- `exec` – uvicorn ersetzt die Shell, Signale/Exit-Codes kommen sauber an

Bei fehlenden Abhängigkeiten bricht es mit einer klaren Anleitung ab, statt
mit `ImportError`.

## Standalone-App (eine HTML-Datei)

`docs/index.html` ist der komplette Explorer als **einzelne Datei**: ~45 KB,
HTML/CSS/Vanilla-JS, Daten eingebettet, **null externe Requests**. Kein Build,
kein Server, kein Framework, kein CDN — funktioniert per `file://`, im
Arena-Viewer und auf GitHub Pages.

Features:

- Tabs **Helden · Modi · Maps · Subklassen · Rohdaten (JSON)**
- Live-Suche mit `/`-Shortcut, Rollen- und Status-Filter
- Umschaltbare **Tabelle** mit sortierbaren Spalten
- **Detail-Drawer** je Eintrag: Fähigkeiten, Overwatch-Klasse, Konfidenz,
  Prüfdatum und **Quellenlinks**; schließt mit `Esc`
- **Deep-Links** (`#hero/tracer`, `#map/mansion-portero`, `#modes?role=utility`)
- Tastaturbedienung, `aria`-Rollen, `prefers-reduced-motion`

```bash
python scripts/build_static.py          # neu generieren
python scripts/build_static.py --check  # CI: schlägt bei veralteter Datei fehl
```

Verifikation der UI in einer echten DOM-Umgebung (jsdom, 27 Assertions):

```bash
npm ci --prefix tests/dom
node tests/dom/check.mjs
```

## Endpunkte

| Methode | Pfad | Beschreibung |
|---|---|---|
| GET | `/` | HTML-Startseite mit Links zu allen Endpunkten |
| GET | `/v1` | Maschinenlesbarer Endpunkt-Index (JSON) |
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

`HEAD` verhält sich wie `GET` (ohne Body) – nötig für Preview- und Uptime-Proxies.

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
tests/           33 Tests: API, Datenintegrität, Ingest, Binary-Guard
```

Datenänderungen erfolgen in `data/*.json`; `pytest` erzwingt danach gültige
Quellen und Referenzen. Siehe [SPEC.md](SPEC.md) für Ziele und Ausschlüsse,
[TESTING.md](TESTING.md) für Nachweise und [AGENTS.md](AGENTS.md) für Regeln.

## Kann man nicht wie RoyaleAPI die App-Dateien auslesen?

RoyaleAPI macht **zwei** Dinge, die oft verwechselt werden:

| RoyaleAPI-Feature | Quelle | Auf Rush übertragbar |
|---|---|---|
| Player-Stats, Battles, Decks | Supercells **offizielle API** | ❌ Overwatch hat keine |
| Kartenwerte, Arenen, Konstanten | Client-Datamining (`cr-api-data`: „Static data and constants") | ✅ ja |

Der Spielerteil kommt also **nicht** aus der APK, sondern aus einer offiziellen
API. Der statische Teil lässt sich sehr wohl auslesen — das ist genau der Weg
hier. Overwatch Rush läuft auf Unity, deshalb liegen Heldendaten in
`assets/bin/Data/*.assets`, AssetBundles und teils als JSON/CSV in
`StreamingAssets`.

```bash
# 1) lokal (auf deinem Rechner) die Datei in tmp/ legen, dann scannen:
python scripts/scan_game_data.py tmp/overwatch-rush.xapk

# Ergebnis: tmp/game_scan/report.json + kleine Text-Configs
#   - erkennt Unity-Version, AssetBundles, il2cpp
#   - findet Heldnamen in Binärblobs (Beweis, wo die Daten liegen)
#   - extrahiert nur kleine Text-Configs, keine Assets
```

Danach entscheidet der Report, ob [AssetRipper](https://github.com/AssetRipper/AssetRipper)
für die `.assets`/`.bundle`-Dateien nötig ist. Was daraus in `data/*.json`
wandert, sind **nur Namen und Zahlen mit Quelle** – niemals Dateien.

**Was auch Datamining nicht liefert:** Match-History und Stats anderer Spieler.
Die liegen serverseitig.

## Warum keine Live-Spielerdaten?

Häufige Frage, klare Antwort: **geht nicht** – nicht „noch nicht".

- **Keine offizielle API.** Blizzard bietet kein Overwatch-API; das
  Battle.net-Developer-Portal deckt Konten ab, nicht Match-Stats.
- **Keine Seite zum Scrapen.** Community-APIs wie `overfast-api` lesen
  öffentliche Overwatch-2-Karriereseiten. Rush hat keine – Mobile-only,
  Soft Launch, kein Web-Profil.
- **Stats sind serverseitig.** Sie stecken nicht in der App. Zugriff hieße:
  eigene Credentials + private Endpunkte oder TLS-MITM → EULA-Verstoß.

Der Client enthält nur statische Spieldaten (Helden, Talente, Mods, Balance).
Wer echte eigene Matchdaten will, kann sie lokal erfassen und die API um einen
**selbst gemeldeten** Match-Log erweitern (siehe SPEC, Abschnitt 2a) – das ist
legal, weil es die eigenen Daten sind.

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
