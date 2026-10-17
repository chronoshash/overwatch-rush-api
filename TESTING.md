# TESTING.md

Nachweise, nicht Behauptungen. Stand: 2026-10-17.

## Umgebung

| Komponente | Version |
|---|---|
| Python | 3.11.2 |
| FastAPI | 0.143.3 |
| Pydantic | 2.14.1 |
| Uvicorn | 0.54.0 |
| httpx (Testclient) | 0.28.1 |
| pytest | 9.1.1 |
| Ruff | 0.17.1 |

## Ausführen

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
ruff check .
ruff format --check .
pytest -q
```

## Testabdeckung (30 Tests)

| Datei | Prüft |
|---|---|
| `tests/test_api.py` | Health, Meta, Filter (`subclass`, `status`, `q`), Alias-Lookup, Pagination, 400/404/422-Envelopes, Suche, ETag/304, CORS, OpenAPI |
| `tests/test_data.py` | Quellen-Pflicht (https), Subklassen-Referenzen, 9 live + 3 upcoming, nur belegte Abilities, `data_version`-Format, **Binary-Guard** (keine `.apk`/`.xapk` im Tree) |
| `tests/test_ingest.py` | XAPK-Manifest-Parsing, APK ohne Manifest, fehlende Datei (Exit 2), Nicht-ZIP (Exit 3), CLI-Ausgabe, Pfad-Traversal-Schutz beim Entpacken |

## Verifizierte Ergebnisse (Letzter Lauf)

```
$ ruff check .
All checks passed!

$ ruff format --check .
13 files already formatted

$ pytest
30 passed, 1 warning in 0.14s
```

Bekannte Warnung (harmlos, Upstream):
`StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.`
Kein Testfehler; kann nach Migration des Testclients entfernt werden.

## Live-HTTP-Nachweis

Server: `uvicorn app.main:app --host 0.0.0.0 --port 8000`

```
$ curl -s localhost:8000/health
{"status":"ok","app_version":"0.1.0","data_version":"2026.10.17","updated_at":"2026-10-17",
 "counts":{"heroes":12,"roles":5,"modes":4,"maps":3}}

$ curl -s "localhost:8000/v1/heroes?subclass=vanguard"
→ 2 Treffer: brigitte, reinhardt (meta.total=2)

$ curl -sI localhost:8000/v1/heroes
etag: "c030475a090e8691a2f696c00ace9477"
cache-control: public, max-age=60

$ curl -H 'If-None-Match: "c030475a090e8691a2f696c00ace9477"' localhost:8000/v1/heroes
status=304 bytes=0

$ curl localhost:8000/v1/heroes/nobody   → 404 {"error":{"code":"hero_not_found",...}}
$ curl "localhost:8000/v1/heroes?subclass=tank" → 400 {"error":{"code":"unknown_subclass",...}}
$ curl localhost:8000/docs → 200   /openapi.json → 200
```

## Ingest-Nachweis (synthetische Fixture)

```
$ python scripts/ingest_local.py /tmp/owr-demo.xapk --json-out /tmp/owr-report.json --no-hash
file        : owr-demo.xapk (0.0 MiB)
container   : xapk
package     : com.blizzard.overwatch.rush
version     : 1.3.0 (code 1300)
apk splits  : 2
exit=0
```

Der Report enthält nur Metadaten; das Paket wurde nicht kopiert
(`git status` zeigt keine `.apk`/`.xapk`).

## CI

`.github/workflows/ci.yml` führt auf Python 3.11 und 3.12 aus:
`ruff check`, `ruff format --check`, `pytest`, plus Guard gegen committete
Spiel-Binaries (`git ls-files | grep -E '\.(apk|xapk|apks|aab|obb)$'`).

Verifizierter Lauf (2026-10-17, Run 39044815131):

```
test (3.11)   pass   13s
test (3.12)   pass   12s
```

https://github.com/chronoshash/overwatch-rush-api/actions/runs/39044815131

## Nicht getestet / offen

- Python 3.12: in CI grün, lokal nicht separat ausgeführt (Sandbox hat 3.11).
- iOS-Daten (App Store) nur als Quelle, kein eigenes Feld.
- `aapt2`-Pfad im Ingest-Skript ist implementiert, aber im Sandbox nicht
  verfügbar (kein Java) → Zweig ungetestet, wird sauber als `None` gemeldet.
- Keine Lasttests; Ziel ist ein statisches Datenset.
