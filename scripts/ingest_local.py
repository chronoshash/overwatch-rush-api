#!/usr/bin/env python3
"""Inspect a locally downloaded Overwatch Rush XAPK/APK and emit a metadata report.

Design rules (see SPEC.md):
  * the game package is never copied into the repository or uploaded anywhere;
  * only *metadata* (package id, version, sizes, permissions) is reported;
  * no assets, code or obb contents are extracted by default;
  * the script is stdlib-only so it runs on a plain Python 3.11 install.

Usage:
    python scripts/ingest_local.py ~/Downloads/overwatch-rush.xapk
    python scripts/ingest_local.py game.apk --no-hash --json-out data/incoming/report.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

MAX_MANIFEST_BYTES = 1_048_576  # refuse to read absurdly large manifest files
MANIFEST_NAMES = ("manifest.json", "xapk.json", "info.json")
PACKAGE_SUFFIXES = {".apk", ".xapk", ".apks", ".aab"}


def sha256_of(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_manifest(archive: zipfile.ZipFile) -> dict | None:
    """Return the XAPK manifest payload, if this archive is an XAPK."""
    names = set(archive.namelist())
    for candidate in MANIFEST_NAMES:
        if candidate not in names:
            continue
        info = archive.getinfo(candidate)
        if info.file_size > MAX_MANIFEST_BYTES:
            raise ValueError(f"{candidate} is too large ({info.file_size} bytes)")
        try:
            payload = json.loads(archive.read(candidate).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"{candidate} is not valid UTF-8 JSON: {exc}") from exc
        if isinstance(payload, dict):
            return payload
    return None


def first(mapping: dict, *keys: str) -> object | None:
    for key in keys:
        if key in mapping and mapping[key] not in (None, "", []):
            return mapping[key]
    return None


def aapt2_permissions(apk_path: Path) -> dict | None:
    """Use aapt2 when available; never required for the report to succeed."""
    binary = shutil.which("aapt2") or shutil.which("aapt")
    if binary is None:
        return None
    try:
        result = subprocess.run(
            [binary, "dump", "badging", str(apk_path)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    permissions = re.findall(r"uses-permission: name='([^']+)'", result.stdout)
    version = re.search(r"versionName='([^']+)'", result.stdout)
    return {
        "tool": Path(binary).name,
        "permissions": permissions,
        "versionName": version.group(1) if version else None,
    }


def build_report(
    path: Path,
    *,
    compute_hash: bool = True,
    extract_to: Path | None = None,
) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() not in PACKAGE_SUFFIXES:
        raise ValueError(f"unexpected file type {path.suffix!r}")

    report: dict = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "file_name": path.name,
        "file_size_bytes": path.stat().st_size,
        "sha256": sha256_of(path) if compute_hash else None,
        "container": None,
        "manifest": None,
        "apk_entries": [],
        "aapt2": None,
        "extracted_to": None,
        "notes": [],
    }

    if not zipfile.is_zipfile(path):
        raise ValueError("file is not a ZIP container (corrupt or not an APK/XAPK)")

    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        report["container"] = "xapk" if any(n in names for n in MANIFEST_NAMES) else "apk"
        apk_entries = [
            {"name": info.filename, "size_bytes": info.file_size}
            for info in archive.infolist()
            if info.filename.lower().endswith(".apk")
        ]
        report["apk_entries"] = sorted(apk_entries, key=lambda item: item["name"])
        report["entry_count"] = len(names)

        try:
            manifest = read_manifest(archive)
        except ValueError as exc:
            report["notes"].append(str(exc))
            manifest = None

        if manifest:
            report["manifest"] = {
                "package_name": first(manifest, "package_name", "package"),
                "version_name": first(manifest, "version_name", "versionName"),
                "version_code": first(manifest, "version_code", "versionCode"),
                "app_name": first(manifest, "name", "app_name", "label"),
                "min_sdk": first(manifest, "min_sdk_version", "minSdkVersion"),
                "target_sdk": first(manifest, "target_sdk_version", "targetSdkVersion"),
                "split_count": len(first(manifest, "split_apks", "splits") or []),
            }
        else:
            report["notes"].append(
                "No XAPK manifest.json found; install aapt2 to read AndroidManifest.xml."
            )

        if extract_to is not None:
            extract_to.mkdir(parents=True, exist_ok=True)
            base = extract_to.resolve()
            for info in archive.infolist():
                target = (base / info.filename).resolve()
                if not str(target).startswith(str(base)):
                    report["notes"].append(f"skipped unsafe path: {info.filename}")
                    continue
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
            report["extracted_to"] = str(extract_to)
            report["notes"].append(
                "Extracted files stay local and are git-ignored. Do not redistribute them."
            )

    base_apk = next(
        (entry for entry in report["apk_entries"] if entry["name"].lower().endswith("base.apk")),
        None,
    )
    if base_apk and extract_to is not None:
        report["aapt2"] = aapt2_permissions(extract_to / base_apk["name"])
    elif base_apk:
        report["notes"].append(
            "aapt2 inspection skipped (needs --extract); permissions unavailable."
        )

    return report


def summarize(report: dict) -> str:
    manifest = report.get("manifest") or {}
    size_mb = report["file_size_bytes"] / (1024 * 1024)
    lines = [
        f"file        : {report['file_name']} ({size_mb:.1f} MiB)",
        f"container   : {report['container']}",
        f"package     : {manifest.get('package_name')}",
        f"version     : {manifest.get('version_name')} (code {manifest.get('version_code')})",
        f"apk splits  : {len(report['apk_entries'])}",
        f"sha256      : {report['sha256']}",
    ]
    if report.get("aapt2"):
        lines.append(f"permissions : {len(report['aapt2']['permissions'])}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("package", type=Path, help="local .xapk/.apk/.apks file")
    parser.add_argument(
        "--json-out",
        type=Path,
        default=Path("data/incoming/apk-report.json"),
        help="where to write the JSON report (default: data/incoming/apk-report.json)",
    )
    parser.add_argument(
        "--no-hash", action="store_true", help="skip sha256 (faster for huge files)"
    )
    parser.add_argument(
        "--extract",
        nargs="?",
        const="data/incoming/extracted",
        type=Path,
        help="optionally extract into this directory (git-ignored)",
    )
    args = parser.parse_args(argv)

    try:
        report = build_report(args.package, compute_hash=not args.no_hash, extract_to=args.extract)
    except FileNotFoundError:
        print(f"error: file not found: {args.package}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(summarize(report))
    print(f"report      : {args.json_out}")
    print("notice      : metadata only - the package itself was not copied or uploaded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
