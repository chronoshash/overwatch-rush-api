#!/usr/bin/env python3
"""Build a self-contained explorer from data/*.json into a single HTML file.

The output (docs/index.html) has zero external dependencies: the dataset is
embedded as JSON, CSS and vanilla JS are inline. No build step, no framework,
no CDN, no server. It works from `file://`, in the Arena viewer and on
GitHub Pages.

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

TEMPLATE = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark light">
<meta name="description" content="Overwatch Rush – Helden, Subklassen, Modi und Maps als quellenbasiertes Datenset. Standalone, ohne Server.">
<title>__TITLE__ — Explorer</title>
<style>
  :root {
    color-scheme: dark;
    --bg-0:#070b12; --bg-1:#0b1220; --bg-2:#101a2b;
    --line:#22314a; --line-soft:#1a2740;
    --text:#e6edf7; --muted:#8fa1b8; --dim:#6f819a;
    --accent:#8fd3ff; --accent-2:#3d6ea0;
    --live:#83d9a8; --live-bg:#0f2a1e; --live-line:#24523a;
    --soon:#e3c07b; --soon-bg:#2a2110; --soon-line:#7a5a1f;
    --radius:14px;
    --shadow:0 18px 50px rgba(0,0,0,.45);
  }
  * { box-sizing:border-box; }
  html, body { height:100%; }
  body {
    margin:0; color:var(--text);
    font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    background:
      radial-gradient(1100px 520px at 15% -12%, #1d3a5e 0%, transparent 60%),
      radial-gradient(900px 500px at 95% 0%, #172a44 0%, transparent 55%),
      linear-gradient(180deg, var(--bg-1), var(--bg-0));
    background-attachment: fixed;
    -webkit-font-smoothing: antialiased;
  }
  a { color:var(--accent); text-decoration:none; }
  a:hover { text-decoration:underline; }
  .wrap { width:min(1180px,100%); margin:0 auto; padding:28px 20px 72px; }

  /* ---------- header ---------- */
  header.top { display:flex; flex-wrap:wrap; gap:18px; align-items:flex-end; justify-content:space-between; }
  .badge {
    display:inline-flex; align-items:center; gap:8px;
    font-size:11px; letter-spacing:.14em; text-transform:uppercase;
    color:var(--accent); border:1px solid #2b4a6b; border-radius:999px; padding:5px 12px;
    background:rgba(143,211,255,.06);
  }
  .badge .dot { width:6px; height:6px; border-radius:50%; background:var(--live); box-shadow:0 0 8px var(--live); }
  h1 { font-size:clamp(28px,4.6vw,42px); line-height:1.1; margin:14px 0 6px; letter-spacing:-.02em; }
  .lead { color:var(--muted); max-width:66ch; line-height:1.6; margin:0; font-size:15px; }
  .lead strong { color:var(--text); font-weight:600; }

  .stats { display:flex; flex-wrap:wrap; gap:10px; }
  .stat {
    background:rgba(255,255,255,.04); border:1px solid var(--line); border-radius:12px;
    padding:10px 16px; min-width:104px;
  }
  .stat b { display:block; font-size:21px; line-height:1.2; }
  .stat span { font-size:11.5px; color:var(--muted); }

  /* ---------- toolbar ---------- */
  .toolbar {
    position:sticky; top:0; z-index:20; margin:26px 0 14px; padding:12px;
    background:rgba(9,15,25,.82); backdrop-filter:blur(12px);
    border:1px solid var(--line-soft); border-radius:16px;
    display:flex; flex-wrap:wrap; gap:10px; align-items:center;
  }
  .search { position:relative; flex:1 1 260px; min-width:200px; }
  .search svg { position:absolute; left:12px; top:50%; transform:translateY(-50%); opacity:.55; }
  input[type=search] {
    width:100%; padding:11px 12px 11px 38px; font-size:14px; font-family:inherit;
    color:var(--text); background:rgba(255,255,255,.05);
    border:1px solid var(--line); border-radius:11px;
  }
  input[type=search]::placeholder { color:var(--dim); }
  input[type=search]:focus-visible { outline:2px solid var(--accent-2); outline-offset:1px; }
  kbd {
    font:inherit; font-size:11px; color:var(--muted);
    border:1px solid var(--line); border-bottom-width:2px; border-radius:6px;
    padding:1px 6px; background:rgba(255,255,255,.05);
  }
  .chips { display:flex; flex-wrap:wrap; gap:6px; }
  .chip {
    font:inherit; font-size:12.5px; cursor:pointer; color:var(--muted);
    border:1px solid var(--line); background:rgba(255,255,255,.03);
    border-radius:999px; padding:6px 12px; transition:border-color .15s, color .15s, background .15s;
  }
  .chip:hover { color:var(--text); border-color:#31517a; }
  .chip[aria-pressed=true] { color:#08111d; background:var(--accent); border-color:var(--accent); font-weight:600; }
  .chip:focus-visible, .tab:focus-visible, .card:focus-visible, .icon-btn:focus-visible {
    outline:2px solid var(--accent); outline-offset:2px;
  }
  .spacer { flex:1; }
  .icon-btn {
    font:inherit; font-size:13px; color:var(--muted); cursor:pointer;
    background:rgba(255,255,255,.03); border:1px solid var(--line);
    border-radius:10px; padding:8px 12px;
  }
  .icon-btn:hover { color:var(--text); border-color:#31517a; }
  .icon-btn[aria-pressed=true] { color:var(--accent); border-color:var(--accent-2); }

  /* ---------- tabs ---------- */
  .tabs { display:flex; gap:2px; margin:22px 0 18px; border-bottom:1px solid var(--line); overflow-x:auto; }
  .tab {
    font:inherit; font-size:14px; color:var(--muted); background:none; border:none;
    padding:11px 16px; cursor:pointer; white-space:nowrap;
    border-bottom:2px solid transparent; margin-bottom:-1px;
  }
  .tab:hover { color:var(--text); }
  .tab[aria-selected=true] { color:var(--text); border-bottom-color:var(--accent); font-weight:600; }
  .tab .count { color:var(--dim); font-size:12px; margin-left:6px; }

  /* ---------- cards ---------- */
  .grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(258px,1fr)); gap:12px; }
  .card {
    position:relative; text-align:left; font:inherit; color:inherit; cursor:pointer;
    background:linear-gradient(180deg, rgba(255,255,255,.05), rgba(255,255,255,.025));
    border:1px solid var(--line); border-radius:var(--radius); padding:16px 18px;
    transition:transform .15s, border-color .15s, box-shadow .15s;
  }
  .card:hover { transform:translateY(-2px); border-color:#3a5f8f; box-shadow:0 10px 26px rgba(0,0,0,.32); }
  .card .kicker { font-size:11px; letter-spacing:.11em; text-transform:uppercase; color:var(--accent); }
  .card h3 { margin:5px 0 0; font-size:17px; line-height:1.25; }
  .card .body { margin:9px 0 0; font-size:13px; color:var(--muted); line-height:1.55; }
  .meta-row { display:flex; flex-wrap:wrap; gap:6px; margin-top:12px; }
  .tag {
    font-size:11px; border:1px solid var(--line-soft); border-radius:6px;
    padding:2px 7px; color:var(--muted); background:rgba(255,255,255,.02);
  }
  .tag.live { color:var(--live); border-color:var(--live-line); background:var(--live-bg); }
  .tag.upcoming { color:var(--soon); border-color:var(--soon-line); background:var(--soon-bg); }
  .card .chev { position:absolute; right:14px; bottom:12px; color:var(--dim); font-size:16px; }

  /* ---------- table ---------- */
  .table-wrap { overflow-x:auto; border:1px solid var(--line); border-radius:var(--radius); }
  table { width:100%; border-collapse:collapse; font-size:13.5px; }
  th, td { text-align:left; padding:11px 14px; border-bottom:1px solid var(--line-soft); white-space:nowrap; }
  th { position:sticky; top:0; background:#0d1626; color:var(--muted); font-weight:600; font-size:12px;
       letter-spacing:.06em; text-transform:uppercase; cursor:pointer; user-select:none; }
  th:hover { color:var(--text); }
  th .arrow { opacity:.45; margin-left:5px; font-size:10px; }
  tbody tr:hover { background:rgba(255,255,255,.03); }
  tbody tr:last-child td { border-bottom:none; }

  /* ---------- drawer ---------- */
  .scrim {
    position:fixed; inset:0; background:rgba(3,7,12,.66); backdrop-filter:blur(3px);
    opacity:0; pointer-events:none; transition:opacity .2s; z-index:40;
  }
  .scrim.open { opacity:1; pointer-events:auto; }
  .drawer {
    position:fixed; top:0; right:0; height:100%; width:min(520px,100%);
    background:linear-gradient(180deg,#0d1727,#080e17);
    border-left:1px solid var(--line); box-shadow:var(--shadow);
    transform:translateX(102%); transition:transform .24s cubic-bezier(.22,.9,.3,1);
    z-index:50; display:flex; flex-direction:column;
  }
  .drawer.open { transform:none; }
  .drawer header { padding:20px 22px 14px; border-bottom:1px solid var(--line-soft); }
  .drawer .close {
    position:absolute; top:14px; right:14px; width:34px; height:34px; border-radius:9px;
    display:grid; place-items:center; cursor:pointer; font-size:18px; line-height:1;
    color:var(--muted); background:rgba(255,255,255,.05); border:1px solid var(--line);
  }
  .drawer .close:hover { color:var(--text); }
  .drawer .content { padding:18px 22px 32px; overflow-y:auto; }
  .drawer h2 { margin:6px 0 2px; font-size:24px; }
  .drawer .sub { color:var(--accent); font-size:12px; letter-spacing:.1em; text-transform:uppercase; }
  .section { margin-top:22px; }
  .section h4 {
    margin:0 0 8px; font-size:11.5px; letter-spacing:.12em; text-transform:uppercase; color:var(--dim);
  }
  .section p { margin:0; font-size:13.5px; line-height:1.65; color:var(--muted); }
  .kv { display:grid; grid-template-columns:130px 1fr; gap:7px 12px; font-size:13.5px; }
  .kv dt { color:var(--dim); }
  .kv dd { margin:0; color:var(--text); }
  ul.plain { margin:0; padding-left:18px; color:var(--muted); font-size:13.5px; line-height:1.7; }
  .src-list { list-style:none; margin:0; padding:0; display:grid; gap:7px; }
  .src-list li { font-size:12.5px; overflow-wrap:anywhere; }
  .src-list a { color:#9cc9ee; }

  /* ---------- misc ---------- */
  .empty { text-align:center; color:var(--muted); padding:64px 12px; }
  .empty b { display:block; color:var(--text); margin-bottom:6px; font-size:15px; }
  footer.foot {
    margin-top:38px; padding-top:18px; border-top:1px solid var(--line-soft);
    font-size:12px; color:var(--dim); line-height:1.75;
  }
  .sr-only {
    position:absolute; width:1px; height:1px; padding:0; margin:-1px;
    overflow:hidden; clip:rect(0 0 0 0); white-space:nowrap; border:0;
  }
  .toast {
    position:fixed; left:50%; bottom:24px; transform:translate(-50%, 20px);
    background:#13233a; border:1px solid var(--line); color:var(--text);
    padding:10px 16px; border-radius:10px; font-size:13px; opacity:0;
    transition:opacity .2s, transform .2s; pointer-events:none; z-index:60;
  }
  .toast.show { opacity:1; transform:translate(-50%, 0); }
  pre.json {
    margin:0; padding:16px; overflow:auto; max-height:60vh; font-size:12px; line-height:1.55;
    background:#0a1320; border:1px solid var(--line); border-radius:var(--radius);
    color:#b7c9de;
  }
  @media (max-width:640px) {
    .wrap { padding:20px 14px 56px; }
    .stats { width:100%; }
    .stat { flex:1 1 88px; min-width:88px; padding:9px 12px; }
    .kv { grid-template-columns:1fr; gap:2px 0; }
    .kv dd { margin-bottom:8px; }
  }
  @media (prefers-reduced-motion: reduce) {
    * { transition:none !important; animation:none !important; }
  }
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <div>
      <span class="badge"><span class="dot"></span> data __DATAVERSION__ · geprüft __CHECKED__</span>
      <h1>__TITLE__</h1>
      <p class="lead">__LEAD__</p>
    </div>
    <div class="stats" id="stats">__STATS__</div>
  </header>

  <div class="toolbar" role="search">
    <label class="search">
      <span class="sr-only">Suche</span>
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
        <circle cx="11" cy="11" r="7"></circle><path d="m20 20-3.5-3.5"></path>
      </svg>
      <input id="q" type="search" placeholder="Held, Modus, Map, Rolle …  ( / )" autocomplete="off" spellcheck="false">
    </label>
    <div class="chips" id="role-chips" aria-label="Nach Subklasse filtern">__CHIPS__</div>
    <div class="chips" aria-label="Nach Status filtern">
      <button class="chip" data-status="all" aria-pressed="true">Alle</button>
      <button class="chip" data-status="live" aria-pressed="false">Spielbar</button>
      <button class="chip" data-status="upcoming" aria-pressed="false">Angekündigt</button>
    </div>
    <span class="spacer"></span>
    <button class="icon-btn" id="view-toggle" aria-pressed="false" title="Zwischen Karten und Tabelle wechseln">Tabelle</button>
    <button class="icon-btn" id="copy-link" title="Link zur aktuellen Ansicht kopieren">Link kopieren</button>
  </div>

  <div class="tabs" role="tablist" aria-label="Bereiche">__TABS__</div>

  <main id="view" aria-live="polite"></main>

  <footer class="foot">
    <div>Quellen je Eintrag unter „Quellen“ in der Detailansicht. Overwatch ist eine Marke von
      Blizzard Entertainment; dieses Projekt steht in keiner Verbindung zu Blizzard und verteilt
      keine Spieldateien.</div>
    <div>Standalone-Build: eine HTML-Datei, kein Server, keine externen Requests.
      Dieselben Daten liefert die API unter <code>/v1/heroes</code>, <code>/v1/maps</code>, <code>/v1/modes</code>.</div>
  </footer>
</div>

<div class="scrim" id="scrim" hidden></div>
<aside class="drawer" id="drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title" aria-hidden="true">
  <header>
    <span class="sub" id="drawer-kicker"></span>
    <h2 id="drawer-title"></h2>
    <button class="close" id="drawer-close" aria-label="Schließen (Esc)">×</button>
  </header>
  <div class="content" id="drawer-body"></div>
</aside>
<div class="toast" id="toast" role="status" aria-live="polite"></div>

<script>
const DATA = __DATA__;

const ROLE = Object.fromEntries(DATA.roles.map(r => [r.slug, r]));
const HERO = Object.fromEntries(DATA.heroes.map(h => [h.slug, h]));
const MODE = Object.fromEntries(DATA.modes.map(m => [m.slug, m]));
const MAP  = Object.fromEntries(DATA.maps.map(m => [m.slug, m]));

const state = { tab: "heroes", q: "", role: "all", status: "all", view: "cards", sort: "name", dir: 1 };

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, c => (
  { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
));
const pct = (value) => (value === null || value === undefined) ? "—" : Math.round(value * 100) + " %";

/* ---------------- filtering ---------------- */
function heroList() {
  const q = state.q;
  let rows = DATA.heroes.filter(hero => {
    if (state.role !== "all" && hero.subclass !== state.role) return false;
    if (state.status !== "all" && hero.status !== state.status) return false;
    if (!q) return true;
    const haystack = [hero.name, hero.slug, hero.notes, ROLE[hero.subclass]?.name,
      ...(hero.aliases || []), ...hero.abilities.map(a => a.name)].join(" ").toLowerCase();
    return haystack.includes(q);
  });
  if (state.tab === "heroes") rows = sortHeroes(rows);
  return rows;
}

function sortHeroes(rows) {
  const value = (hero) => {
    switch (state.sort) {
      case "role": return ROLE[hero.subclass]?.name || hero.subclass;
      case "status": return hero.status === "live" ? "0" : "1";
      case "abilities": return String(hero.abilities.length).padStart(3, "0");
      default: return hero.name;
    }
  };
  return rows.slice().sort((a, b) => {
    const av = value(a), bv = value(b);
    const cmp = av.localeCompare(bv, "de", { sensitivity: "base" });
    return (cmp || a.name.localeCompare(b.name, "de")) * state.dir;
  });
}

function modeList() {
  return DATA.modes.filter(mode => {
    if (!state.q) return true;
    return [mode.name, mode.slug, mode.description, mode.objective].join(" ").toLowerCase().includes(state.q);
  }).sort((a, b) => a.name.localeCompare(b.name, "de"));
}

function mapList() {
  return DATA.maps.filter(item => {
    if (!state.q) return true;
    return [item.name, item.slug, item.inspired_by || "", item.setting || ""].join(" ").toLowerCase().includes(state.q);
  }).sort((a, b) => a.name.localeCompare(b.name, "de"));
}

function roleList() {
  return DATA.roles.filter(role => {
    if (!state.q) return true;
    return [role.name, role.slug, role.description, role.playstyle].join(" ").toLowerCase().includes(state.q);
  }).sort((a, b) => a.name.localeCompare(b.name, "de"));
}

/* ---------------- rendering ---------------- */
function heroCard(hero) {
  const role = ROLE[hero.subclass];
  return `<article class="card" tabindex="0" role="button" data-hero="${esc(hero.slug)}"
      aria-label="${esc(hero.name)} — Details öffnen">
    <div class="kicker">${esc(role ? role.name : hero.subclass)}</div>
    <h3>${esc(hero.name)}</h3>
    <p class="body">${esc(hero.notes || role?.description || "")}</p>
    <div class="meta-row">
      <span class="tag ${hero.status}">${hero.status === "live" ? "spielbar" : "angekündigt"}</span>
      <span class="tag">${esc(hero.overwatch_class)}</span>
      ${hero.abilities.length ? `<span class="tag">${hero.abilities.length} Fähigkeiten</span>` : ""}
    </div>
    <span class="chev" aria-hidden="true">›</span>
  </article>`;
}

function modeCard(mode) {
  const teams = mode.teams ? mode.teams + " Teams" : "offene Lobby";
  return `<article class="card" tabindex="0" role="button" data-mode="${esc(mode.slug)}"
      aria-label="${esc(mode.name)} — Details öffnen">
    <div class="kicker">${esc(teams)}</div>
    <h3>${esc(mode.name)}</h3>
    <p class="body">${esc(mode.description)}</p>
    <div class="meta-row">
      <span class="tag">${mode.team_size} pro Team</span>
      <span class="tag">${esc(mode.objective)}</span>
    </div>
    <span class="chev" aria-hidden="true">›</span>
  </article>`;
}

function mapCard(item) {
  return `<article class="card" tabindex="0" role="button" data-map="${esc(item.slug)}"
      aria-label="${esc(item.name)} — Details öffnen">
    <div class="kicker">Vorlage: ${esc(item.inspired_by || "—")}</div>
    <h3>${esc(item.name)}</h3>
    <p class="body">${esc(item.setting || "")}</p>
    <div class="meta-row">
      <span class="tag">${item.built_from_scratch ? "neu gebaut" : "Port"}</span>
    </div>
    <span class="chev" aria-hidden="true">›</span>
  </article>`;
}

function roleCard(role) {
  const count = DATA.heroes.filter(h => h.subclass === role.slug).length;
  const upcoming = DATA.heroes.filter(h => h.subclass === role.slug && h.status === "upcoming").length;
  return `<article class="card" tabindex="0" role="button" data-role="${esc(role.slug)}"
      aria-label="${esc(role.name)} — Details öffnen">
    <div class="kicker">${count} Held${count === 1 ? "" : "en"}${upcoming ? ` · ${upcoming} angekündigt` : ""}</div>
    <h3>${esc(role.name)}</h3>
    <p class="body">${esc(role.description)}</p>
    <div class="meta-row"><span class="tag">${esc(role.playstyle)}</span></div>
    <span class="chev" aria-hidden="true">›</span>
  </article>`;
}

function heroTable(rows) {
  const arrow = (key) => state.sort === key ? `<span class="arrow">${state.dir === 1 ? "▲" : "▼"}</span>` : "";
  return `<div class="table-wrap"><table>
    <thead><tr>
      <th data-sort="name" scope="col">Held${arrow("name")}</th>
      <th data-sort="role" scope="col">Subklasse${arrow("role")}</th>
      <th scope="col">Klasse</th>
      <th data-sort="status" scope="col">Status${arrow("status")}</th>
      <th data-sort="abilities" scope="col">Fähigkeiten${arrow("abilities")}</th>
    </tr></thead>
    <tbody>${rows.map(hero => `<tr data-hero="${esc(hero.slug)}" tabindex="0">
      <td><strong>${esc(hero.name)}</strong></td>
      <td>${esc(ROLE[hero.subclass]?.name || hero.subclass)}</td>
      <td>${esc(hero.overwatch_class)}</td>
      <td><span class="tag ${hero.status}">${hero.status === "live" ? "spielbar" : "angekündigt"}</span></td>
      <td>${hero.abilities.length ? esc(hero.abilities.map(a => a.name).join(", ")) : "—"}</td>
    </tr>`).join("")}</tbody>
  </table></div>`;
}

function jsonView() {
  return `<pre class="json" id="json-pre">${esc(JSON.stringify(DATA, null, 2))}</pre>`;
}

function render() {
  const view = $("#view");
  let rows;

  if (state.tab === "heroes") {
    rows = heroList();
    view.innerHTML = rows.length
      ? (state.view === "table" ? heroTable(rows) : `<div class="grid">${rows.map(heroCard).join("")}</div>`)
      : emptyState();
  } else if (state.tab === "modes") {
    rows = modeList();
    view.innerHTML = rows.length ? `<div class="grid">${rows.map(modeCard).join("")}</div>` : emptyState();
  } else if (state.tab === "maps") {
    rows = mapList();
    view.innerHTML = rows.length ? `<div class="grid">${rows.map(mapCard).join("")}</div>` : emptyState();
  } else if (state.tab === "roles") {
    rows = roleList();
    view.innerHTML = rows.length ? `<div class="grid">${rows.map(roleCard).join("")}</div>` : emptyState();
  } else {
    view.innerHTML = jsonView();
  }

  $("#view-toggle").hidden = state.tab !== "heroes";
  $("#view-toggle").textContent = state.view === "table" ? "Karten" : "Tabelle";
  $("#view-toggle").setAttribute("aria-pressed", String(state.view === "table"));
  updateHash();
}

function emptyState() {
  return `<div class="empty"><b>Keine Treffer</b>
    Für „${esc(state.q || state.role)}“ gibt es in diesem Bereich nichts.
    <button class="icon-btn" style="margin-top:14px" onclick="resetFilters()">Filter zurücksetzen</button></div>`;
}

/* ---------------- drawer ---------------- */
let lastFocus = null;

function openDrawer({ kicker, title, body }) {
  lastFocus = document.activeElement;
  $("#drawer-kicker").textContent = kicker;
  $("#drawer-title").textContent = title;
  $("#drawer-body").innerHTML = body;
  const scrim = $("#scrim");
  const drawer = $("#drawer");
  scrim.hidden = false;
  void scrim.offsetWidth;  // flush layout so the transition runs
  scrim.classList.add("open");
  drawer.classList.add("open");
  drawer.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
  requestAnimationFrame(() => $("#drawer-close").focus());
}

function closeDrawer() {
  $("#scrim").classList.remove("open");
  $("#drawer").classList.remove("open");
  $("#drawer").setAttribute("aria-hidden", "true");
  document.body.style.overflow = "";
  setTimeout(() => { $("#scrim").hidden = true; }, 220);
  if (lastFocus && lastFocus.focus) lastFocus.focus();
  history.replaceState(null, "", location.pathname + location.search);
}

function sourcesBlock(item) {
  if (!item.sources || !item.sources.length) return "";
  return `<div class="section"><h4>Quellen</h4><ul class="src-list">
    ${item.sources.map(url => `<li><a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(url)}</a></li>`).join("")}
  </ul></div>`;
}

function confidenceBlock(item) {
  const bits = [];
  if (item.confidence) bits.push(`Konfidenz: <strong>${esc(item.confidence)}</strong>`);
  if (item.verified_at) bits.push(`geprüft: ${esc(item.verified_at)}`);
  return bits.length ? `<div class="section"><h4>Datenqualität</h4><p>${bits.join(" · ")}</p></div>` : "";
}

function heroDrawer(slug) {
  const hero = HERO[slug];
  if (!hero) return;
  const role = ROLE[hero.subclass];
  const abilities = hero.abilities.length
    ? `<ul class="plain">${hero.abilities.map(a => `<li><strong>${esc(a.name)}</strong> · ${esc(a.kind)}</li>`).join("")}</ul>`
    : `<p>Keine Fähigkeitsnamen öffentlich belegt. Das Feld bleibt bewusst leer, statt Werte zu erfinden.</p>`;
  const body = `
    <div class="section"><h4>Einordnung</h4>
      <dl class="kv">
        <dt>Subklasse</dt><dd>${esc(role?.name || hero.subclass)}</dd>
        <dt>Overwatch-Klasse</dt><dd>${esc(hero.overwatch_class)}</dd>
        <dt>Status</dt><dd>${hero.status === "live" ? "spielbar" : "angekündigt"}</dd>
        <dt>Seit</dt><dd>${esc(hero.first_playable || "—")}</dd>
        ${hero.aliases.length ? `<dt>Aliase</dt><dd>${esc(hero.aliases.join(", "))}</dd>` : ""}
      </dl>
    </div>
    <div class="section"><h4>Notiz</h4><p>${esc(hero.notes || "—")}</p></div>
    <div class="section"><h4>Fähigkeiten</h4>${abilities}</div>
    ${confidenceBlock(hero)}
    ${sourcesBlock(hero)}`;
  openDrawer({ kicker: role?.name || hero.subclass, title: hero.name, body });
  history.replaceState(null, "", "#hero/" + hero.slug);
}

function modeDrawer(slug) {
  const mode = MODE[slug];
  if (!mode) return;
  const body = `
    <div class="section"><h4>Ablauf</h4><p>${esc(mode.objective)}</p></div>
    <div class="section"><h4>Format</h4>
      <dl class="kv">
        <dt>Teamgröße</dt><dd>${mode.team_size} pro Team</dd>
        <dt>Teams</dt><dd>${mode.teams ?? "offen"}</dd>
      </dl>
    </div>
    <div class="section"><h4>Beschreibung</h4><p>${esc(mode.description)}</p></div>
    ${confidenceBlock(mode)}${sourcesBlock(mode)}`;
  openDrawer({ kicker: mode.teams ? `${mode.teams} Teams` : "Modus", title: mode.name, body });
  history.replaceState(null, "", "#mode/" + mode.slug);
}

function mapDrawer(slug) {
  const item = MAP[slug];
  if (!item) return;
  const body = `
    <div class="section"><h4>Herkunft</h4>
      <dl class="kv">
        <dt>Overwatch-Vorlage</dt><dd>${esc(item.inspired_by || "—")}</dd>
        <dt>Bauweise</dt><dd>${item.built_from_scratch ? "neu für Rush gebaut" : "Port"}</dd>
        <dt>Setting</dt><dd>${esc(item.setting || "—")}</dd>
      </dl>
    </div>
    ${confidenceBlock(item)}${sourcesBlock(item)}`;
  openDrawer({ kicker: "Map", title: item.name, body });
  history.replaceState(null, "", "#map/" + item.slug);
}

function roleDrawer(slug) {
  const role = ROLE[slug];
  if (!role) return;
  const heroes = DATA.heroes.filter(h => h.subclass === slug);
  const body = `
    <div class="section"><h4>Spielweise</h4><p>${esc(role.playstyle)}</p></div>
    <div class="section"><h4>Beschreibung</h4><p>${esc(role.description)}</p></div>
    <div class="section"><h4>Helden in dieser Rolle</h4>
      <ul class="plain">${heroes.map(h => `<li>${esc(h.name)} <span class="tag ${h.status}">${h.status === "live" ? "spielbar" : "angekündigt"}</span></li>`).join("") || "<li>—</li>"}</ul>
    </div>
    ${confidenceBlock(role)}${sourcesBlock(role)}`;
  openDrawer({ kicker: "Subklasse", title: role.name, body });
  history.replaceState(null, "", "#role/" + role.slug);
}

/* ---------------- navigation ---------------- */
function setTab(name, { scroll = false } = {}) {
  if (!["heroes", "modes", "maps", "roles", "data"].includes(name)) name = "heroes";
  state.tab = name;
  $$(".tab").forEach(tab => tab.setAttribute("aria-selected", String(tab.dataset.tab === name)));
  if (scroll) $("#view").scrollIntoView({ behavior: "smooth", block: "start" });
  render();
}

function resetFilters() {
  state.q = ""; state.role = "all"; state.status = "all";
  $("#q").value = "";
  $$("[data-role], [data-status]").forEach(chip => {
    const own = chip.dataset.role ?? chip.dataset.status;
    chip.setAttribute("aria-pressed", String(own === "all"));
  });
  render();
}

function updateHash() {
  if ($("#drawer").classList.contains("open")) return;
  const params = new URLSearchParams();
  if (state.q) params.set("q", state.q);
  if (state.role !== "all") params.set("role", state.role);
  if (state.status !== "all") params.set("status", state.status);
  if (state.view !== "cards") params.set("view", state.view);
  const query = params.toString();
  history.replaceState(null, "", "#" + state.tab + (query ? "?" + query : ""));
}

function applyHash() {
  const raw = location.hash.replace(/^#/, "");
  if (!raw) return;
  const [path, query] = raw.split("?");
  const parts = path.split("/");
  const params = new URLSearchParams(query || "");

  if (parts[0] === "hero" && HERO[parts[1]]) { setTab("heroes"); heroDrawer(parts[1]); return; }
  if (parts[0] === "mode" && MODE[parts[1]]) { setTab("modes"); modeDrawer(parts[1]); return; }
  if (parts[0] === "map" && MAP[parts[1]]) { setTab("maps"); mapDrawer(parts[1]); return; }
  if (parts[0] === "role" && ROLE[parts[1]]) { setTab("roles"); roleDrawer(parts[1]); return; }
  if (["heroes", "modes", "maps", "roles", "data"].includes(parts[0])) {
    state.q = params.get("q") || "";
    state.role = params.get("role") || "all";
    state.status = params.get("status") || "all";
    state.view = params.get("view") === "table" ? "table" : "cards";
    $("#q").value = state.q;
    $$("[data-role], [data-status]").forEach(chip => {
      const own = chip.dataset.role ?? chip.dataset.status;
      const wanted = chip.dataset.role ? state.role : state.status;
      chip.setAttribute("aria-pressed", String(own === wanted || (own === "all" && wanted === "all")));
    });
    setTab(parts[0]);
  }
}

/* ---------------- events ---------------- */
$("#q").addEventListener("input", event => {
  state.q = event.target.value.trim().toLowerCase();
  render();
});

$$(".tab").forEach(tab => tab.addEventListener("click", () => setTab(tab.dataset.tab)));

$("#role-chips").addEventListener("click", event => {
  const chip = event.target.closest("[data-role]");
  if (!chip) return;
  state.role = chip.dataset.role;
  $$("[data-role]").forEach(el => el.setAttribute("aria-pressed", String(el === chip)));
  render();
});

$$("[data-status]").forEach(chip => chip.addEventListener("click", () => {
  state.status = chip.dataset.status;
  $$("[data-status]").forEach(el => el.setAttribute("aria-pressed", String(el === chip)));
  render();
}));

$("#view-toggle").addEventListener("click", () => {
  state.view = state.view === "table" ? "cards" : "table";
  render();
});

$("#copy-link").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(location.href);
    toast("Link kopiert");
  } catch {
    toast("Kopieren nicht erlaubt — URL aus der Adresszeile nehmen");
  }
});

function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.remove("show"), 1800);
}

document.addEventListener("click", event => {
  const heroEl = event.target.closest("[data-hero]");
  if (heroEl) { heroDrawer(heroEl.dataset.hero); return; }
  const modeEl = event.target.closest("[data-mode]");
  if (modeEl) { modeDrawer(modeEl.dataset.mode); return; }
  const mapEl = event.target.closest("[data-map]");
  if (mapEl) { mapDrawer(mapEl.dataset.map); return; }
  const roleEl = event.target.closest("[data-role]");
  if (roleEl) { roleDrawer(roleEl.dataset.role); return; }
  const sortEl = event.target.closest("[data-sort]");
  if (sortEl) {
    const key = sortEl.dataset.sort;
    state.dir = state.sort === key ? -state.dir : 1;
    state.sort = key;
    render();
  }
});

document.addEventListener("keydown", event => {
  if (event.key === "Escape" && $("#drawer").classList.contains("open")) { closeDrawer(); return; }
  if (event.key === "/" && document.activeElement !== $("#q")) {
    event.preventDefault();
    $("#q").focus();
    $("#q").select();
  }
  if ((event.key === "Enter" || event.key === " ") && document.activeElement?.dataset) {
    const el = document.activeElement;
    if (el.dataset.hero) { event.preventDefault(); heroDrawer(el.dataset.hero); }
    else if (el.dataset.mode) { event.preventDefault(); modeDrawer(el.dataset.mode); }
    else if (el.dataset.map) { event.preventDefault(); mapDrawer(el.dataset.map); }
    else if (el.dataset.role) { event.preventDefault(); roleDrawer(el.dataset.role); }
  }
  if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
    const tabs = $$(".tab");
    const index = tabs.indexOf(document.activeElement);
    if (index === -1) return;
    const next = tabs[(index + (event.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length];
    next.focus();
    setTab(next.dataset.tab);
  }
});

$("#drawer-close").addEventListener("click", closeDrawer);
$("#scrim").addEventListener("click", closeDrawer);
window.addEventListener("hashchange", applyHash);

/* ---------------- boot ---------------- */
applyHash();
if (!location.hash) setTab("heroes");
</script>
</body>
</html>
"""


def _fmt(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def build() -> str:
    game = json.loads((DATA / "game.json").read_text(encoding="utf-8"))
    heroes = json.loads((DATA / "heroes.json").read_text(encoding="utf-8"))
    roles = json.loads((DATA / "roles.json").read_text(encoding="utf-8"))
    modes = json.loads((DATA / "modes.json").read_text(encoding="utf-8"))
    maps = json.loads((DATA / "maps.json").read_text(encoding="utf-8"))

    dataset = {"game": game, "heroes": heroes, "roles": roles, "modes": modes, "maps": maps}
    live = sum(1 for hero in heroes if hero["status"] == "live")
    upcoming = len(heroes) - live

    stats = "".join(
        f'<div class="stat"><b>{value}</b><span>{label}</span></div>'
        for value, label in (
            (live, "spielbar"),
            (upcoming, "angekündigt"),
            (len(modes), "Spielmodi"),
            (len(maps), "Maps"),
            (len(roles), "Subklassen"),
        )
    )
    chips = (
        '<button class="chip" data-role="all" aria-pressed="true">Alle Rollen</button>'
        + "".join(
            f'<button class="chip" data-role="{role["slug"]}" aria-pressed="false">{role["name"]}</button>'
            for role in roles
        )
    )
    tabs = "".join(
        f'<button class="tab" role="tab" data-tab="{slug}" aria-selected="'
        f'{"true" if slug == "heroes" else "false"}">{label}'
        f'<span class="count">{count}</span></button>'
        for slug, label, count in (
            ("heroes", "Helden", len(heroes)),
            ("modes", "Modi", len(modes)),
            ("maps", "Maps", len(maps)),
            ("roles", "Subklassen", len(roles)),
            ("data", "Daten", "JSON"),
        )
    )

    lead = (
        f"{game['genre']} von {game['developer']}, "
        f"{game['perspective']}-Perspektive, {game['price_model']}. "
        f"Soft Launch seit {game['soft_launch']['started']} in "
        f"{', '.join(game['soft_launch']['regions'])}. "
        "<strong>Alle Angaben mit Quelle</strong> – Felder ohne Belege bleiben leer."
    )

    return (
        TEMPLATE.replace("__TITLE__", game["name"])
        .replace("__DATAVERSION__", game["data_version"])
        .replace("__CHECKED__", game["updated_at"])
        .replace("__LEAD__", lead)
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
