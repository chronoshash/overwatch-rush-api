#!/usr/bin/env python3
"""Build a self-contained static explorer from data/*.json.

The output (docs/index.html) has no external dependencies: the dataset is
embedded as JSON, styling and JS are inline. That makes it usable
  * in the Arena file viewer,
  * on GitHub Pages,
  * from a plain `file://` open, with no server and no proxy.

Usage:
    python scripts/build_static.py            # writes docs/index.html
    python scripts/build_static.py --check    # exit 1 if the file is stale
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "docs" / "index.html"

TEMPLATE = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ — Datenset</title>
<style>
  :root { color-scheme: dark; --line:#22314a; --muted:#8fa1b8; --accent:#8fd3ff; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
         background: radial-gradient(1200px 600px at 20% -10%, #1f3a5f 0%, #0b1220 55%, #070b12 100%);
         color:#e6edf7; min-height:100vh; }
  .wrap { width:min(1100px,100%); margin:0 auto; padding:32px 20px 64px; }
  .badge { display:inline-block; font-size:11px; letter-spacing:.14em; text-transform:uppercase;
           color:var(--accent); border:1px solid #2b4a6b; border-radius:999px; padding:4px 12px; }
  h1 { font-size:clamp(26px,4.5vw,40px); margin:14px 0 6px; }
  .lead { color:var(--muted); max-width:70ch; line-height:1.6; margin:0 0 22px; }
  .stats { display:flex; flex-wrap:wrap; gap:10px; margin-bottom:24px; }
  .stat { background:rgba(255,255,255,.04); border:1px solid var(--line); border-radius:12px;
          padding:10px 16px; min-width:110px; }
  .stat b { display:block; font-size:20px; }
  .stat span { font-size:12px; color:var(--muted); }
  .controls { display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin-bottom:18px; }
  input[type=search] { flex:1 1 240px; min-width:200px; padding:11px 14px; border-radius:11px;
      border:1px solid var(--line); background:rgba(255,255,255,.05); color:inherit; font-size:14px; }
  input[type=search]:focus { outline:2px solid #3d6ea0; outline-offset:1px; }
  .chip { cursor:pointer; border:1px solid var(--line); background:rgba(255,255,255,.04);
          color:var(--muted); border-radius:999px; padding:7px 14px; font-size:13px; }
  .chip[aria-pressed=true] { border-color:#3d6ea0; color:#e6edf7; background:rgba(61,110,160,.25); }
  .tabs { display:flex; gap:6px; margin:26px 0 16px; border-bottom:1px solid var(--line); }
  .tab { background:none; border:none; color:var(--muted); padding:10px 16px; cursor:pointer;
         font-size:14px; border-bottom:2px solid transparent; }
  .tab[aria-selected=true] { color:#e6edf7; border-bottom-color:var(--accent); }
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(250px,1fr)); gap:12px; }
  .card { background:rgba(255,255,255,.04); border:1px solid var(--line); border-radius:14px; padding:16px 18px; }
  .card h3 { margin:0 0 4px; font-size:16px; }
  .card .sub { font-size:12px; color:var(--accent); text-transform:uppercase; letter-spacing:.08em; }
  .card p { margin:10px 0 0; font-size:13px; color:var(--muted); line-height:1.55; }
  .tag { display:inline-block; font-size:11px; border:1px solid var(--line); border-radius:6px;
         padding:2px 7px; margin:8px 6px 0 0; color:var(--muted); }
  .tag.upcoming { border-color:#7a5a1f; color:#e3c07b; }
  .tag.live { border-color:#24523a; color:#83d9a8; }
  .empty { color:var(--muted); padding:40px 0; text-align:center; }
  footer { margin-top:40px; font-size:12px; color:#6f819a; line-height:1.7; border-top:1px solid var(--line); padding-top:18px; }
  a { color:var(--accent); }
  code { background:rgba(255,255,255,.06); padding:1px 6px; border-radius:6px; }
</style>
</head>
<body>
<div class="wrap">
  <span class="badge">data __DATAVERSION__ · __CHECKED__</span>
  <h1>__TITLE__ — Datenset</h1>
  <p class="lead">__LEAD__ Diese Seite ist statisch: kein Server, keine externen Assets, alle Daten eingebettet.</p>

  <div class="stats">__STATS__</div>

  <div class="controls">
    <input type="search" id="q" placeholder="Suchen: Held, Modus, Map …" aria-label="Suche">
    <button class="chip" data-filter="all" aria-pressed="true">Alle</button>__CHIPS__
  </div>

  <div class="tabs" role="tablist">__TABS__</div>
  <div id="grid" class="grid"></div>
  <div id="empty" class="empty" hidden>Keine Treffer.</div>

  <footer>
    Quellen: Blizzard News, Google Play, App Store, Fachpresse (siehe <code>sources</code> je Eintrag).
    Overwatch ist eine Marke von Blizzard Entertainment. Dieses Projekt verteilt keine Spieldateien.
    API-Version: <code>GET /v1/heroes</code> · statisch generiert mit <code>scripts/build_static.py</code>.
  </footer>
</div>
<script>
const DATA = __DATA__;
const state = { tab: "heroes", filter: "all", q: "" };

const roleName = Object.fromEntries(DATA.roles.map(r => [r.slug, r.name]));

function heroCard(h) {
  const abilities = h.abilities.length
    ? `<p><strong>Belegt:</strong> ${h.abilities.map(a => a.name).join(", ")}</p>` : "";
  return `<article class="card">
    <span class="sub">${roleName[h.subclass] || h.subclass}</span>
    <h3>${h.name}</h3>
    <p>${h.notes || ""}</p>${abilities}
    <span class="tag ${h.status}">${h.status === "live" ? "spielbar" : "angekündigt"}</span>
    <span class="tag">${h.overwatch_class}</span>
  </article>`;
}

function modeCard(m) {
  return `<article class="card">
    <span class="sub">${m.teams ? m.teams + " Teams" : "offen"}</span>
    <h3>${m.name}</h3>
    <p>${m.description}</p>
    <span class="tag">${m.team_size} pro Team</span>
  </article>`;
}

function mapCard(m) {
  return `<article class="card">
    <span class="sub">Vorlage: ${m.inspired_by || "—"}</span>
    <h3>${m.name}</h3>
    <p>${m.setting || ""}</p>
    <span class="tag">${m.built_from_scratch ? "neu gebaut" : "Port"}</span>
  </article>`;
}

function current() {
  if (state.tab === "heroes") return DATA.heroes.filter(h =>
    (state.filter === "all" || h.subclass === state.filter) &&
    (!state.q || (h.name + " " + h.slug + " " + h.notes + " " + (h.aliases||[]).join(" ")).toLowerCase().includes(state.q)));
  if (state.tab === "modes") return DATA.modes.filter(m =>
    !state.q || (m.name + " " + m.description).toLowerCase().includes(state.q));
  return DATA.maps.filter(m =>
    !state.q || (m.name + " " + (m.inspired_by||"") + " " + (m.setting||"")).toLowerCase().includes(state.q));
}

function render() {
  const items = current();
  const card = state.tab === "heroes" ? heroCard : state.tab === "modes" ? modeCard : mapCard;
  document.getElementById("grid").innerHTML = items.map(card).join("");
  document.getElementById("empty").hidden = items.length > 0;
  document.querySelectorAll(".chip[data-filter]").forEach(el =>
    el.setAttribute("aria-pressed", String(el.dataset.filter === state.filter)));
}

document.getElementById("q").addEventListener("input", e => {
  state.q = e.target.value.trim().toLowerCase(); render();
});
document.querySelectorAll(".chip[data-filter]").forEach(el => el.addEventListener("click", () => {
  state.filter = el.dataset.filter; render();
}));
document.querySelectorAll(".tab").forEach(el => el.addEventListener("click", () => {
  state.tab = el.dataset.tab;
  document.querySelectorAll(".tab").forEach(t => t.setAttribute("aria-selected", String(t === el)));
  render();
}));
document.querySelectorAll(".chip[data-filter]").forEach(el => {
  if (state.tab !== "heroes") el.style.display = "none";
});
render();
</script>
</body>
</html>
"""


def build() -> str:
    game = json.loads((DATA / "game.json").read_text(encoding="utf-8"))
    heroes = json.loads((DATA / "heroes.json").read_text(encoding="utf-8"))
    roles = json.loads((DATA / "roles.json").read_text(encoding="utf-8"))
    modes = json.loads((DATA / "modes.json").read_text(encoding="utf-8"))
    maps = json.loads((DATA / "maps.json").read_text(encoding="utf-8"))

    dataset = {
        "game": game,
        "heroes": heroes,
        "roles": roles,
        "modes": modes,
        "maps": maps,
    }
    live = sum(1 for hero in heroes if hero["status"] == "live")
    upcoming = len(heroes) - live

    stats = "".join(
        f'<div class="stat"><b>{value}</b><span>{label}</span></div>'
        for value, label in (
            (live, "Helden spielbar"),
            (upcoming, "angekündigt"),
            (len(modes), "Spielmodi"),
            (len(maps), "Maps"),
            (len(roles), "Subklassen"),
        )
    )
    chips = "".join(
        f'<button class="chip" data-filter="{role["slug"]}" aria-pressed="false">{role["name"]}</button>'
        for role in roles
    )
    tabs = "".join(
        f'<button class="tab" role="tab" data-tab="{slug}" aria-selected="{str(slug == "heroes").lower()}">{label}</button>'
        for slug, label in (("heroes", "Helden"), ("modes", "Modi"), ("maps", "Maps"))
    )

    return (
        TEMPLATE.replace("__TITLE__", game["name"])
        .replace("__DATAVERSION__", game["data_version"])
        .replace("__CHECKED__", game["updated_at"])
        .replace(
            "__LEAD__",
            f"{game['genre']} von {game['developer']}. "
            f"Soft Launch seit {game['soft_launch']['started']} in "
            f"{', '.join(game['soft_launch']['regions'])}.",
        )
        .replace("__STATS__", stats)
        .replace("__CHIPS__", chips)
        .replace("__TABS__", tabs)
        .replace("__DATA__", json.dumps(dataset, ensure_ascii=False, separators=(",", ":")))
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if docs/index.html is stale")
    args = parser.parse_args(argv)

    html = build()
    if args.check:
        if not OUT.is_file() or OUT.read_text(encoding="utf-8") != html:
            print(
                "docs/index.html is out of date; run: python scripts/build_static.py",
                file=sys.stderr,
            )
            return 1
        print("docs/index.html is up to date")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(html):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
