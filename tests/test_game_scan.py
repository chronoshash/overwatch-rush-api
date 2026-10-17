from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from scripts.scan_game_data import classify, main, name_hits, scan

HERO_JSON = json.dumps(
    {
        "heroes": [
            {"id": "tracer", "name": "Tracer", "hp": 150, "dps": 240},
            {"id": "reinhardt", "name": "Reinhardt", "hp": 550, "dps": 85},
        ]
    }
).encode()


def build_xapk(path: Path, *, with_unity: bool = True) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "manifest.json", json.dumps({"package_name": "com.blizzard.overwatch.rush"})
        )
        archive.writestr("com.blizzard.overwatch.rush.apk", b"PK\x03\x04base")
        if with_unity:
            archive.writestr(
                "assets/bin/Data/globalgamemanagers",
                b"\x00\x00\x00\x0019Unity 6000.3.0f1\x00" + b"\x00" * 64,
            )
            archive.writestr(
                "assets/bin/Data/sharedassets0.assets", b"\x00" * 128 + b"Tracer" + b"\x00" * 128
            )
            archive.writestr(
                "assets/AssetBundles/heroes_balance.bundle",
                b"Reinhardt" + b"\x00" * 256 + b"Tracer",
            )
            archive.writestr("assets/StreamingAssets/hero_config.json", HERO_JSON)
            archive.writestr("assets/StreamingAssets/notes.txt", b"no hero data here")
            archive.writestr("lib/arm64-v8a/libil2cpp.so", b"\x7fELF" + b"\x00" * 64)
    return path


@pytest.fixture()
def report(tmp_path: Path) -> dict:
    package = build_xapk(tmp_path / "game.xapk")
    return scan(package, tmp_path / "out")


def test_classification() -> None:
    assert classify("assets/bin/Data/sharedassets0.assets") == "unity_assets"
    assert classify("assets/AssetBundles/heroes.bundle") == "asset_bundle"
    assert classify("assets/StreamingAssets/x.json") == "streaming_assets"
    assert classify("lib/arm64-v8a/libil2cpp.so") == "il2cpp_binary"
    assert classify("manifest.json") == "other"


def test_detects_unity_version(report: dict) -> None:
    assert report["unity_version"] == "6000.3.0f1"


def test_counts_and_categories(report: dict) -> None:
    assert report["counts"]["unity_assets"] >= 1
    assert report["counts"]["asset_bundle"] == 1
    assert report["counts"]["il2cpp_binary"] == 1


def test_finds_hero_names_in_blobs(report: dict) -> None:
    hits = report["blob_name_hits"]
    assert "assets/bin/Data/sharedassets0.assets" in hits
    assert "Tracer" in hits["assets/bin/Data/sharedassets0.assets"]
    assert "assets/AssetBundles/heroes_balance.bundle" in hits


def test_extracts_text_configs_with_hits(report: dict, tmp_path: Path) -> None:
    extracted = {item["name"]: item for item in report["extracted"]}
    config = extracted["assets/StreamingAssets/hero_config.json"]
    assert set(config["hero_names_found"]) == {"Tracer", "Reinhardt"}
    saved = tmp_path / "out" / config["path"]
    assert json.loads(saved.read_text())["heroes"][0]["name"] == "Tracer"
    assert "assets/StreamingAssets/notes.txt" not in extracted


def test_next_steps_mention_tools(report: dict) -> None:
    joined = " ".join(report["next_steps"])
    assert "AssetRipper" in joined
    assert "Il2CppDumper" in joined


def test_no_player_data_claim(report: dict) -> None:
    """The report must never pretend player stats are obtainable from the client."""
    assert (
        "player" not in json.dumps(report).lower()
        or "no player data" in " ".join(report["next_steps"]).lower()
    )


def test_path_traversal_entry_is_skipped(tmp_path: Path) -> None:
    package = tmp_path / "evil.xapk"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("assets/StreamingAssets/../../../escape.json", HERO_JSON)
    report = scan(package, tmp_path / "out")
    assert not (tmp_path / "escape.json").exists()
    assert any("unsafe path" in note for note in report["notes"])


def test_name_hits_helper() -> None:
    payload = b"prefix-Tracer-suffix"
    assert name_hits(payload, ["Tracer", "Mercy"]) == ["Tracer"]
    assert name_hits(b"nothing", ["Tracer"]) == []


def test_cli_writes_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    package = build_xapk(tmp_path / "game.xapk")
    out = tmp_path / "scan"
    code = main([str(package), "--out", str(out), "--no-scan-blobs"])
    assert code == 0
    payload = json.loads((out / "report.json").read_text())
    assert payload["unity_version"] == "6000.3.0f1"
    assert "static data only" in capsys.readouterr().out


def test_missing_file_and_non_zip(tmp_path: Path) -> None:
    assert main([str(tmp_path / "nope.xapk"), "--out", str(tmp_path / "o")]) == 2
    bogus = tmp_path / "bogus.apk"
    bogus.write_text("not a zip")
    assert main([str(bogus), "--out", str(tmp_path / "o")]) == 3
