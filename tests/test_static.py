from __future__ import annotations

from pathlib import Path

from scripts.build_static import OUT, build


def test_static_page_is_up_to_date() -> None:
    """docs/index.html must be regenerated whenever data/*.json changes."""
    assert OUT.is_file(), "docs/index.html is missing; run: python scripts/build_static.py"
    assert OUT.read_text(encoding="utf-8") == build(), (
        "docs/index.html is stale; run: python scripts/build_static.py"
    )


def test_static_page_is_self_contained() -> None:
    html = OUT.read_text(encoding="utf-8")
    assert "<script src" not in html
    assert "http://" not in html.split("<footer>")[0]  # no external assets in markup
    assert "const DATA = {" in html


def test_static_page_embeds_full_dataset() -> None:
    html = OUT.read_text(encoding="utf-8")
    for slug in ("brigitte", "mansion-portero", "duo-free-for-all", "vanguard"):
        assert slug in html


def test_static_check_mode_detects_stale(tmp_path: Path) -> None:
    import scripts.build_static as mod

    original = mod.OUT
    try:
        mod.OUT = tmp_path / "missing.html"
        assert mod.main(["--check"]) == 1
    finally:
        mod.OUT = original
