#!/usr/bin/env bash
# Download an APK/XAPK **for local inspection only** into git-ignored tmp/.
#
# Why this is a separate, manual script:
#   * Blizzard's package is proprietary; redistributing it is not allowed.
#   * CI and the API must never depend on, or ship, the binary.
#   * This sandbox is network-restricted, so the download runs on your machine.
#
# The URL is intentionally NOT hardcoded: pass whatever build you are allowed
# to inspect. Nothing is committed; tmp/ is in .gitignore.
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <url-to-xapk-or-apk> [output-name]" >&2
  echo "example: $0 'https://example.invalid/overwatch-rush.xapk' overwatch-rush.xapk" >&2
  exit 64
fi

url="$1"
name="${2:-overwatch-rush.xapk}"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
out_dir="$root/tmp"
out="$out_dir/$name"

mkdir -p "$out_dir"

case "$name" in
  *.apk|*.xapk|*.apks) ;;
  *) echo "refusing: output name must end in .apk/.xapk/.apks" >&2; exit 65 ;;
esac

echo "downloading to $out"
curl --fail --location --retry 3 --progress-bar -o "$out.part" "$url"
mv "$out.part" "$out"

echo
echo "done: $(du -h "$out" | cut -f1) -> $out"
echo "next: python scripts/ingest_local.py '$out'"
echo "note: $out is git-ignored; never commit or redistribute it."
