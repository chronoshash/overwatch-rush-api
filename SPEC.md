# SPEC — overwatch-rush-api

Version 0.1.0 · Stand 2026-10-17

## 1. Ziel

Eine schlanke, öffentlich lesbare HTTP-API mit verifizierten Stammdaten zu
**Overwatch Rush** (Blizzard, Top-Down-Mobile-Hero-Shooter): Helden, Subklassen,
Modi, Maps, Regions-/Plattformstatus.

## 2. Nicht-Ziele (bewusst ausgeschlossen)

- **Keine Verteilung von APK/XAPK/OBB oder Spieldateien.** Das Repo enthält und
  veröffentlicht keine Blizzard-Binaries. `scripts/fetch_xapk.sh` lädt bewusst
  nur lokal in ein ignorier-tes `tmp/` und läuft nie in CI.
- **Keine erfundenen Werte.** Keine geschätzten Ability-Schadenszahlen, keine
  erfundenen Talente. Jeder Datensatz trägt `sources`, `verified_at` und
  `confidence`. Wo Daten fehlen, bleibt das Feld leer (`abilities: []`) statt
  geraten zu werden.
- Keine Auth, keine Schreib-API, keine Datenbank in v0.1 (Datei-Dataset).
- Keine Aussage über zukünftige Releases/Regionen über das hinaus, was Blizzard
  oder das Store-Listing belegt.
- **Keine Live-Spielerdaten (Stats, Match-History, Leaderboards).** Siehe
  Abschnitt 2a – das ist keine Designentscheidung, sondern eine harte Grenze.

## 2a. Warum es keine Live-Spielerdaten gibt

Drei voneinander unabhängige Blocker. Jeder einzelne reicht schon.

1. **Es existiert keine API.** Blizzard betreibt kein offizielles
   Overwatch-API; `develop.battle.net` deckt Battle.net-Konten ab, nicht
   Match-Statistiken. Ein Entwickler-Thread (Okt. 2026) fasst es zusammen:
   „there is no api for overwatch and there probably wont be one“. Auch für
   Overwatch Rush ist nichts angekündigt.
2. **Es gibt keine öffentliche Seite zum Auslesen.** Bekannte Community-APIs
   (`overfast-api`, `ow-api`, `owapi.eu`, `oversmash`) funktionieren, weil sie
   *öffentliche Overwatch-2-Karriereseiten scrapen*. Rush ist Mobile-only im
   Soft Launch – es gibt kein Karriereprofil im Web, also nichts zu scrapen.
3. **Stats liegen serverseitig hinter Login.** Sie sind nicht im Client
   enthalten. Sie zu bekommen hieße: eigene Zugangsdaten + reverse-engineerte
   private Endpunkte oder TLS-MITM. Das ist ein Verstoß gegen die Blizzard-EULA
   (unautorisierter Zugriff) – unabhängig davon, dass `com.blizzard.overwatch.rush`
   nur in ID/MY/PH überhaupt spielbar ist.

**Was im Client steckt:** Heldendefinitionen, Talente, Mods, UI-Strings,
Balance-Werte. Das ist die statische Ebene – keine fremden Spielerdaten.
Diese Werte lokal auszulesen (`scripts/ingest_local.py`) ist etwas anderes als
sie weiterzuverbreiten; Assets bleiben tabu, Zahlen nur als belegte Fakten.

**Was daraus folgt:** Dieses Projekt bleibt bei Stammdaten. Alles andere wäre
entweder erfunden, illegal oder beides.

### 2b. Statische Client-Daten (Datamining) – erlaubt, mit Regeln

RoyaleAPI bezieht Spieler-Stats aus Supercells offizieller API, nicht aus der
APK; aus dem Client stammen dort nur statische Konstanten (`cr-api-data`).

Für Rush gilt derselbe Trennschnitt. Statische Werte (Helden-IDs, Fähigkeits-
namen, Balance-Zahlen, Talent-/Mod-Listen) dürfen aus dem Client gelesen werden,
weil es Fakten ohne Assets sind. Regeln:

1. **Nur lokal.** `scripts/scan_game_data.py` läuft auf dem Rechner des Nutzers,
   schreibt nach `tmp/` (git-ignored) und lädt nichts hoch.
2. **Nur Fakten.** In `data/*.json` kommen Namen/Zahlen mit Quelle
   (`source: "local client scan, package sha256 …"`), keine Textblöcke,
   keine Bilder, keine Binärdateien.
3. **Keine Spieler-Daten.** Die existieren im Client nicht.
4. **Graubereich benennen.** Datamining kann gegen die EULA-RE-Klausel verstoßen;
   das Projekt veröffentlicht deshalb keine extrahierten Assets und keine
   Client-Dateien, nur aggregierte Fakten.
5. **Version dokumentieren.** Jeder Scan-Report nennt `package_sha256` und
   `unity_version`, damit Werte reproduzierbar bleiben.

## 3. Datenquellen (Primärquellen zuerst)

| Quelle | Nutzung |
|---|---|
| Blizzard News — Development Update | Existenz, Positionierung, Testphasen |
| Google Play / App Store Listing | Paket-ID, Modi, Brigitte-Kit-Namen, Party-Feature-Status |
| esportsinsider, gosugamers, esports.gg, redreactions | Soft-Launch-Datum, Roster, Subklassen, Maps |

Sekundärquellen werden nur für Felder genutzt, die sie explizit belegen, und
mit `confidence: medium` markiert.

## 4. Datenmodell

`Hero`
- `slug`, `name`, `aliases[]`
- `subclass` → Referenz auf `roles.json` (`assassin`, `fighter`, `long_ranger`, `utility`, `vanguard`)
- `overwatch_class` → `tank | damage | support` (nur Referenz, nicht Rush-Rolle)
- `status` → `live | upcoming`
- `abilities[]` → nur belegte Einträge; **aktuell leer**, wird über `scripts/ingest.py` aus lokaler Analyse befüllt
- `sources[]`, `verified_at`, `confidence`

`Mode` · `MapFeature` · `Subclass` · `GameMeta` — jeweils mit `sources`/`verified_at`.

## 5. Endpunkte (v1)

| Methode | Pfad | Beschreibung |
|---|---|---|
| GET | `/` | HTML-Startseite (Übersicht, Links) |
| GET | `/v1` | JSON-Index der Endpunkte |
| GET | `/health` | Liveness + Dataset-Version |
| GET | `/v1/meta` | Spiel-Metadaten, Soft-Launch, Anforderungen, Disclaimer |
| GET | `/v1/heroes` | Liste; Filter `subclass`, `status`, `q`; Pagination `limit`/`offset` |
| GET | `/v1/heroes/{slug}` | Einzelheld, 404-Envelope bei unbekanntem Slug |
| GET | `/v1/roles` | Die fünf Rush-Subklassen |
| GET | `/v1/modes` | Spielmodi |
| GET | `/v1/maps` | Maps inkl. Vorlage |
| GET | `/v1/search?q=` | Suche über Helden, Modi, Maps |
| GET | `/docs` | OpenAPI-UI |

Antwort-Envelope für Listen: `{ "data": [...], "meta": { total, limit, offset, returned } }`.
Fehler: `{ "error": { code, message, detail } }`.

## 6. Nicht-funktionale Anforderungen

- **Caching:** `ETag` + `Cache-Control: public, max-age=60` auf Listen-Reads; `If-None-Match` → `304` ohne Body.
- **Determinismus:** stabile Sortierung (live zuerst, dann Name), identische Anfrage ⇒ identischer ETag.
- **Validierung:** Dataset wird beim Start strikt gegen Pydantic-Modelle geprüft (`extra="forbid"`); kaputte Daten starten den Dienst nicht.
- **CORS:** offen für Lesezugriff (`*`), da rein öffentliche Daten.
- **HEAD:** identisch zu GET ohne Body (`app/head.py`), damit Proxies/Healthchecks nicht 405 sehen.

## 7. Erfolgskriterien (überprüfbar)

1. `pytest` grün: API-, Datenintegritäts- und Ingest-Tests.
2. Server startet mit `uvicorn app.main:app`; `/health` liefert `200`.
3. Jeder Held hat ≥1 Quelle und eine gültige Subklassen-Referenz.
4. `GET /v1/heroes` ohne Filter liefert 9 `live` + 3 `upcoming` = 12.
5. Kein `*.apk`/`*.xapk`/`*.obb` im Git-Index.
6. CI (GitHub Actions) führt `ruff` + `pytest` auf Python 3.11 aus.

## 8. Statischer Export

`scripts/build_static.py` erzeugt `docs/index.html` aus `data/*.json`:
vollständig self-contained (Inline-CSS/JS, eingebettetes JSON, keine externen
Requests), damit die Daten ohne Server, ohne Proxy und ohne CDN lesbar sind.

- Erfolgskriterium: `--check` ist grün, d. h. die Datei entspricht exakt dem Datenset.
- Die Seite ist Anzeige, keine zweite Datenquelle: Änderungen nur in `data/`.

## 9. Versionierung

`data_version` (Datum) + `app_version` in `/v1/meta` und `/health`.
Breaking Changes nur unter `/v2`.

## 10. Bekannte Einschränkungen

- Ability-Daten sind leer (keine belastbare öffentliche Quelle für Rush-Kits;
  Kits weichen laut Blizzard bewusst von Overwatch 2 ab).
- Subklassen-Zuordnung der drei `upcoming`-Helden stammt aus einem
  Sekundärbericht → `confidence: medium`.
- Soft-Launch-Status ändert sich; `verified_at` ist der Stichtag.
