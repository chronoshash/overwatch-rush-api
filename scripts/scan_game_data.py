#!/usr/bin/env python3
"""Scan a locally downloaded APK/XAPK for *static* game data (facts only).

What this does
--------------
Given the package on your own disk, it inventories the container and points at
the files that hold static game data: Unity asset files, AssetBundles,
StreamingAssets configs, il2cpp metadata. It extracts small text configs
(JSON/CSV/TXT/XML) and checks binary blobs for known hero names, so you can see
whether the data is actually there before installing any heavy tooling.

What this does NOT do
---------------------
* no player data: match history and stats are server-side, never in the client
* no asset extraction, no model/texture dumping, no redistribution
* no network access, no upload, no writes outside --out

Run this on your machine; the result (a JSON report plus small text configs)
is what you can hand over. The package itself stays where it is.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

TEXT_EXTENSIONS = {".json", ".csv", ".txt", ".xml", ".yaml", ".yml", ".ini", ".bytes", ".tsv"}
MAX_TEXT_BYTES = 8 * 1024 * 1024  # don't balloon on huge files
MAX_SCAN_BYTES = 64 * 1024 * 1024  # per-file cap for the binary name scan
CONFIG_HINTS = (
    "hero",
    "balance",
    "config",
    "unit",
    "ability",
    "talent",
    "mod",
    "localization",
    "string",
    "gameplay",
    "stat",
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def classify(name: str) -> str:
    lowered = name.lower()
    if lowered.endswith((".so", ".dll")) or "global-metadata.dat" in lowered:
        return "il2cpp_binary"
    if (
        lowered.startswith("assets/bin/data/")
        or "/data/" in lowered
        and lowered.endswith((".assets", ".ress", ".resource"))
    ):
        return "unity_assets"
    if lowered.endswith((".bundle", ".unity3d", ".ab", ".assetbundle")):
        return "asset_bundle"
    if "streamingassets" in lowered:
        return "streaming_assets"
    if lowered.endswith((".apk",)):
        return "split_apk"
    if lowered.endswith((".obb", ".ress")):
        return "obb"
    return "other"


def is_text_candidate(name: str) -> bool:
    return Path(name).suffix.lower() in TEXT_EXTENSIONS


def hint_score(name: str) -> int:
    lowered = name.lower()
    return sum(1 for hint in CONFIG_HINTS if hint in lowered)


def find_hero_names() -> list[str]:
    """Hero names from the curated dataset, used as a presence probe."""
    try:
        heroes = json.loads((DATA_DIR / "heroes.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    names: list[str] = []
    for hero in heroes:
        names.append(hero["name"])
        names.extend(hero.get("aliases", []))
    return sorted({name for name in names if len(name) >= 4})


def name_hits(payload: bytes, names: list[str]) -> list[str]:
    lowered = payload.lower()
    return [name for name in names if name.lower().encode("utf-8") in lowered]


def detect_unity_version(archive: zipfile.ZipFile) -> str | None:
    """Unity stores the editor version as a plain string in globalgamemanagers."""
    for candidate in (
        "assets/bin/Data/globalgamemanagers",
        "assets/bin/Data/globalgamemanagers.assets",
    ):
        try:
            info = archive.getinfo(candidate)
        except KeyError:
            continue
        with archive.open(info) as handle:
            head = handle.read(4096)
        match = re.search(rb"Unity\s+(\d{4}\.\d+\.\d+[abfp]\d+)", head)
        if match is None:
            match = re.search(rb"(\d{4}\.\d+\.\d+[abfp]\d+)", head)
        if match:
            return match.group(1).decode("ascii", "replace")
    return None


def scan(package: Path, out_dir: Path, *, scan_blobs: bool = True) -> dict:
    if not package.is_file():
        raise FileNotFoundError(package)
    if not zipfile.is_zipfile(package):
        raise ValueError("file is not a ZIP container (corrupt or not an APK/XAPK)")

    names = find_hero_names()
    out_dir.mkdir(parents=True, exist_ok=True)

    report: dict = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "package": package.name,
        "package_size_bytes": package.stat().st_size,
        "package_sha256": None,
        "unity_version": None,
        "counts": {},
        "categories": {},
        "text_candidates": [],
        "blob_name_hits": {},
        "extracted": [],
        "next_steps": [],
        "notes": [],
    }

    digest = hashlib.sha256()
    with package.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    report["package_sha256"] = digest.hexdigest()

    with zipfile.ZipFile(package) as archive:
        infos = archive.infolist()
        report["unity_version"] = detect_unity_version(archive)

        categories: dict[str, list[dict]] = {}
        for info in infos:
            if info.is_dir():
                continue
            category = classify(info.filename)
            categories.setdefault(category, []).append(
                {
                    "name": info.filename,
                    "size_bytes": info.file_size,
                    "hint_score": hint_score(info.filename),
                }
            )
        report["categories"] = {
            key: sorted(value, key=lambda item: (-item["hint_score"], -item["size_bytes"]))[:40]
            for key, value in categories.items()
        }
        report["counts"] = {key: len(value) for key, value in categories.items()}

        # 1) small text configs, ranked by how config-like the name looks
        text_candidates = [
            info
            for info in infos
            if not info.is_dir()
            and is_text_candidate(info.filename)
            and 0 < info.file_size <= MAX_TEXT_BYTES
        ]
        text_candidates.sort(key=lambda info: (-hint_score(info.filename), info.file_size))
        report["text_candidates"] = [
            {
                "name": info.filename,
                "size_bytes": info.file_size,
                "hint_score": hint_score(info.filename),
            }
            for info in text_candidates[:60]
        ]

        for info in text_candidates[:60]:
            payload = archive.read(info)
            hits = name_hits(payload, names)
            if not hits and hint_score(info.filename) == 0:
                continue
            target = out_dir / "extracted" / info.filename
            target = target.resolve()
            base = (out_dir / "extracted").resolve()
            if not str(target).startswith(str(base)):
                report["notes"].append(f"skipped unsafe path: {info.filename}")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            report["extracted"].append(
                {
                    "name": info.filename,
                    "path": str(target.relative_to(out_dir)),
                    "size_bytes": info.file_size,
                    "sha256": sha256_bytes(payload),
                    "hero_names_found": hits,
                }
            )

        # 2) probe binaries for hero names (proves where static data lives)
        if scan_blobs:
            for category in ("unity_assets", "asset_bundle", "obb", "streaming_assets"):
                for entry in categories.get(category, [])[:25]:
                    if entry["size_bytes"] > MAX_SCAN_BYTES:
                        report["notes"].append(f"skipped huge blob for name scan: {entry['name']}")
                        continue
                    payload = archive.read(entry["name"])
                    hits = name_hits(payload, names)
                    if hits:
                        report["blob_name_hits"][entry["name"]] = hits

    report["next_steps"] = build_next_steps(report)
    return report


def build_next_steps(report: dict) -> list[str]:
    steps: list[str] = []
    counts = report["counts"]
    if report["blob_name_hits"]:
        steps.append(
            "Hero names appear in binary blobs: open the files listed in 'blob_name_hits' "
            "with AssetRipper (https://github.com/AssetRipper/AssetRipper) to read "
            "ScriptableObjects/TextAssets. Keep the output local."
        )
    if counts.get("asset_bundle"):
        steps.append(
            "AssetBundles found: AssetRipper can open them directly; check for a "
            "MonoBehaviour/ScriptableObject named like Hero*, Balance* or Ability*."
        )
    if counts.get("il2cpp_binary"):
        steps.append(
            "il2cpp build detected: use Il2CppDumper (https://github.com/Perfare/Il2CppDumper) "
            "on libil2cpp.so + global-metadata.dat only if you need class/field names."
        )
    if report["extracted"]:
        steps.append(
            "Plain-text configs were extracted to the output folder. Only the *numbers and names* "
            "from them belong in data/*.json - never the files themselves."
        )
    if report["unity_version"]:
        steps.append(f"Unity {report['unity_version']} confirmed the engine version.")
    if not steps:
        steps.append(
            "Nothing conclusive yet. Re-run with the base APK of the XAPK split, "
            "not only the config splits."
        )
    return steps


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("package", type=Path, help="local .xapk/.apk/.apks file")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("tmp/game_scan"),
        help="output directory (default: tmp/game_scan, git-ignored)",
    )
    parser.add_argument("--no-scan-blobs", action="store_true", help="skip the binary name probe")
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="report path (default: <out>/report.json)",
    )
    args = parser.parse_args(argv)

    try:
        report = scan(args.package, args.out, scan_blobs=not args.no_scan_blobs)
    except FileNotFoundError:
        print(f"error: file not found: {args.package}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3

    json_out = args.json_out or (args.out / "report.json")
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"package      : {report['package']}")
    print(f"unity        : {report['unity_version'] or 'not detected'}")
    print(f"categories   : {report['counts']}")
    print(
        f"text configs : {len(report['text_candidates'])} candidates, {len(report['extracted'])} extracted"
    )
    print(f"hero names   : {len(report['blob_name_hits'])} blobs contain hero names")
    for step in report["next_steps"]:
        print(f"  -> {step}")
    print(f"report       : {json_out}")
    print("notice       : static data only - no player data exists in the client.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
