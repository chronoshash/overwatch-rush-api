from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from scripts.ingest_local import build_report, main

MANIFEST = {
    "package_name": "com.blizzard.overwatch.rush",
    "version_name": "1.3.0",
    "version_code": 1300,
    "min_sdk_version": 26,
    "target_sdk_version": 35,
    "split_apks": [
        {"file": "com.blizzard.overwatch.rush.apk"},
        {"file": "config.arm64_v8a.apk"},
    ],
    "permissions": ["android.permission.INTERNET"],
}


def make_xapk(path: Path, manifest: dict | None = MANIFEST) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        if manifest is not None:
            archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("com.blizzard.overwatch.rush.apk", b"PK\x03\x04fake-base")
        archive.writestr("config.arm64_v8a.apk", b"PK\x03\x04fake-split")
        archive.writestr("icon.png", b"\x89PNG fake")
    return path


def test_report_reads_xapk_manifest(tmp_path: Path) -> None:
    archive = make_xapk(tmp_path / "game.xapk")
    report = build_report(archive, compute_hash=True)

    assert report["container"] == "xapk"
    assert report["manifest"]["package_name"] == "com.blizzard.overwatch.rush"
    assert report["manifest"]["version_name"] == "1.3.0"
    assert report["manifest"]["version_code"] == 1300
    assert report["manifest"]["split_count"] == 2
    assert len(report["apk_entries"]) == 2
    assert len(report["sha256"]) == 64
    assert report["extracted_to"] is None
    assert "not copied" in " ".join(report["notes"]) or report["notes"] == []


def test_plain_apk_without_manifest_is_flagged(tmp_path: Path) -> None:
    archive = make_xapk(tmp_path / "game.apk", manifest=None)
    report = build_report(archive, compute_hash=False)
    assert report["container"] == "apk"
    assert report["manifest"] is None
    assert report["sha256"] is None
    assert any("aapt2" in note for note in report["notes"])


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        build_report(tmp_path / "nope.xapk")


def test_non_zip_is_rejected(tmp_path: Path) -> None:
    bogus = tmp_path / "bogus.apk"
    bogus.write_text("not a zip")
    with pytest.raises(ValueError, match="not a ZIP"):
        build_report(bogus)


def test_cli_writes_report_and_never_copies_package(tmp_path: Path) -> None:
    archive = make_xapk(tmp_path / "game.xapk")
    out = tmp_path / "report.json"

    assert main([str(archive), "--json-out", str(out), "--no-hash"]) == 0
    assert out.is_file()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["manifest"]["package_name"] == "com.blizzard.overwatch.rush"
    assert list(tmp_path.glob("*.xapk")) == [archive]  # no extra copies


def test_cli_returns_code_2_for_missing_file(tmp_path: Path) -> None:
    assert main([str(tmp_path / "missing.xapk"), "--json-out", str(tmp_path / "r.json")]) == 2


def test_extraction_blocks_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "evil.xapk"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("manifest.json", json.dumps(MANIFEST))
        zf.writestr("base.apk", b"fake")
        zf.writestr("../escape.txt", b"evil")

    extract_dir = tmp_path / "extracted"
    report = build_report(archive, compute_hash=False, extract_to=extract_dir)

    assert not (tmp_path / "escape.txt").exists()
    assert any("skipped unsafe path" in note for note in report["notes"])
    assert (extract_dir / "base.apk").is_file()
