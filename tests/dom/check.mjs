// DOM smoke test for docs/index.html. Runs the real page in jsdom and drives
// the UI like a user would: tabs, search, filters, table sorting, drawer,
// keyboard shortcuts and deep links. No network, no browser needed.
//
//   npm install --prefix tests/dom --no-audit --no-fund
//   node tests/dom/check.mjs
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { JSDOM } from "jsdom";

const here = dirname(fileURLToPath(import.meta.url));
const path = resolve(here, "../../docs/index.html");
const html = readFileSync(path, "utf8");
const dom = new JSDOM(html, { runScripts: "dangerously", url: "https://example.org/", pretendToBeVisual: true });
const { window } = dom;
const { document } = window;

const fail = [];
const ok = (cond, label, extra = "") => {
  if (cond) console.log(`  PASS  ${label}`);
  else { console.log(`  FAIL  ${label} ${extra}`); fail.push(label); }
};
const cards = () => document.querySelectorAll("#view .card").length;
const rowCount = () => document.querySelectorAll("#view tbody tr").length;
const click = (el) => el.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
const type = (value) => {
  const q = document.getElementById("q");
  q.value = value;
  q.dispatchEvent(new window.Event("input", { bubbles: true }));
};

console.log("— initial render —");
ok(cards() === 12, "12 Hero-Karten", `got ${cards()}`);
ok(document.querySelectorAll(".tab").length === 5, "5 Tabs");
ok(document.querySelector("#stats .stat b").textContent === "9", "erste Stat = 9 spielbar");
ok(document.querySelector('meta[name="description"]') !== null, "meta description vorhanden");
ok(document.querySelectorAll('#role-chips .chip').length === 6, "6 Rollen-Chips");

console.log("— tabs —");
click(document.querySelector('[data-tab="modes"]'));
ok(cards() === 4, "4 Modus-Karten", `got ${cards()}`);
click(document.querySelector('[data-tab="maps"]'));
ok(cards() === 3, "3 Map-Karten", `got ${cards()}`);
click(document.querySelector('[data-tab="roles"]'));
ok(cards() === 5, "5 Rollen-Karten", `got ${cards()}`);
click(document.querySelector('[data-tab="data"]'));
ok(document.querySelector("#json-pre") !== null, "JSON-Ansicht vorhanden");
ok(document.querySelector("#json-pre").textContent.includes('"brigitte"'), "JSON enthält brigitte");
click(document.querySelector('[data-tab="heroes"]'));

console.log("— search & filter —");
type("soldier");
ok(cards() === 1, "Suche 'soldier' → 1", `got ${cards()}`);
type("winston");
ok(cards() === 0 && document.querySelector(".empty") !== null, "Kein Treffer → Empty-State");
type("");
click(document.querySelector('[data-role="vanguard"]'));
ok(cards() === 2, "Filter vanguard → 2", `got ${cards()}`);
click(document.querySelector('[data-role="all"]'));
click(document.querySelector('[data-status="upcoming"]'));
ok(cards() === 3, "Status upcoming → 3", `got ${cards()}`);
click(document.querySelector('[data-status="all"]'));
ok(cards() === 12, "zurück auf 12");

console.log("— table view & sorting —");
click(document.getElementById("view-toggle"));
ok(rowCount() === 12, "Tabelle 12 Zeilen", `got ${rowCount()}`);
const firstBefore = document.querySelector("#view tbody tr td strong").textContent;
click(document.querySelector('th[data-sort="name"]'));
const firstAfter = document.querySelector("#view tbody tr td strong").textContent;
ok(firstBefore !== firstAfter, "Sortierung nach Name dreht Reihenfolge", `${firstBefore} -> ${firstAfter}`);
click(document.getElementById("view-toggle"));

console.log("— drawer —");
const card = document.querySelector('[data-hero="brigitte"]');
click(card);
const drawer = document.getElementById("drawer");
ok(drawer.classList.contains("open"), "Drawer öffnet");
ok(document.getElementById("drawer-title").textContent === "Brigitte", "Titel = Brigitte");
const body = document.getElementById("drawer-body").textContent;
ok(body.includes("Shield Bash"), "Fähigkeit Shield Bash sichtbar");
ok(body.includes("Whip Shot"), "Fähigkeit Whip Shot sichtbar");
ok(body.includes("https://"), "Quellen-Links vorhanden");
ok(body.includes("spielbar"), "Status spielbar sichtbar");
ok(window.location.hash === "#hero/brigitte", "Deep-Link gesetzt", window.location.hash);
document.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
ok(!drawer.classList.contains("open"), "Esc schließt Drawer");

console.log("— keyboard —");
document.dispatchEvent(new window.KeyboardEvent("keydown", { key: "/", bubbles: true }));
ok(document.activeElement === document.getElementById("q"), "/ fokussiert Suche");

console.log("— deep link restore —");
const dom2 = new JSDOM(html, { runScripts: "dangerously", url: "https://example.org/#hero/mercy", pretendToBeVisual: true });
ok(dom2.window.document.getElementById("drawer").classList.contains("open"), "Deep-Link #hero/mercy öffnet Drawer");
ok(dom2.window.document.getElementById("drawer-title").textContent === "Mercy", "Deep-Link zeigt Mercy");

console.log(fail.length ? `\nFAILED (${fail.length}): ${fail.join(", ")}` : "\nALL CHECKS PASSED");
process.exit(fail.length ? 1 : 0);
