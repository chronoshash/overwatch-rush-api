from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.build_static import DATA, OUT, build

ROOT = Path(__file__).resolve().parent.parent


def test_static_page_is_up_to_date() -> None:
    """docs/index.html must be regenerated whenever data/*.json changes."""
    assert OUT.is_file(), "docs/index.html is missing; run: python scripts/build_static.py"
    assert OUT.read_text(encoding="utf-8") == build(), (
        "docs/index.html is stale; run: python scripts/build_static.py"
    )


def test_static_page_is_a_single_self_contained_file() -> None:
    html = OUT.read_text(encoding="utf-8")
    assert "<script src" not in html
    assert '<link rel="stylesheet"' not in html
    assert "http://" not in html
    assert not re.search(r"https?://[^\"'\s]+\.(?:js|css|woff2?|png|svg)", html)
    assert "const DATA = {" in html


def test_metadata_and_accessibility_basics() -> None:
    html = OUT.read_text(encoding="utf-8")
    assert '<meta name="viewport"' in html
    assert '<meta name="description"' in html
    assert 'role="tablist"' in html
    assert 'role="dialog"' in html
    assert 'aria-modal="true"' in html
    assert 'aria-live="polite"' in html
    assert "prefers-reduced-motion" in html
    assert html.count("<h1>") == 1


def test_embedded_dataset_matches_data_files() -> None:
    html = OUT.read_text(encoding="utf-8")
    blob = re.search(r"const DATA = (\{.*?\});\n", html, re.S)
    assert blob, "embedded DATA object not found"
    embedded = json.loads(blob.group(1))

    for key, filename in (
        ("heroes", "heroes.json"),
        ("roles", "roles.json"),
        ("modes", "modes.json"),
        ("maps", "maps.json"),
    ):
        expected = json.loads((DATA / filename).read_text(encoding="utf-8"))
        assert embedded[key] == expected, f"{key} diverges from {filename}"

    assert embedded["game"]["package_id"] == "com.blizzard.overwatch.rush"


def test_all_content_is_reachable() -> None:
    html = OUT.read_text(encoding="utf-8")
    for slug in (
        "brigitte",
        "soldier-76",
        "mansion-portero",
        "duo-free-for-all",
        "vanguard",
        "long_ranger",
    ):
        assert slug in html, slug


def test_no_inline_event_handlers_except_reset() -> None:
    """Keeps the page free of scattered onclick= handlers (CSP friendly)."""
    html = OUT.read_text(encoding="utf-8")
    handlers = re.findall(r'on(?:click|change|input)="([^"]*)"', html)
    assert handlers == ["resetFilters()"], handlers


def test_check_mode_detects_stale(tmp_path: Path) -> None:
    import scripts.build_static as mod

    original = mod.OUT
    try:
        mod.OUT = tmp_path / "missing.html"
        assert mod.main(["--check"]) == 1
    finally:
        mod.OUT = original


def test_dom_test_harness_is_present() -> None:
    """The jsdom harness must ship with the repo so the UI stays verifiable."""
    harness = ROOT / "tests" / "dom" / "check.mjs"
    package = ROOT / "tests" / "dom" / "package.json"
    assert harness.is_file()
    assert package.is_file()
    text = harness.read_text(encoding="utf-8")
    for scenario in ("Drawer", "Deep-Link", "Sortierung", "Empty-State", "Tabs"):
        assert scenario in text, scenario
