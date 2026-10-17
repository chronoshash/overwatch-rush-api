#!/usr/bin/env bash
# Canonical way to run the API. Used by the live preview and by humans.
#
# Usage:
#   bash scripts/serve.sh              # 0.0.0.0:8000
#   PORT=8080 bash scripts/serve.sh    # alternative port
#
# Design notes:
#   * Binds 0.0.0.0 (not 127.0.0.1) so the preview proxy can reach the port.
#   * --proxy-headers + --forwarded-allow-ips='*' so the preview host/scheme
#     from X-Forwarded-* are honoured instead of the container-local ones.
#   * exec: uvicorn replaces the shell, so signals and exit codes propagate.
#   * Fails loudly with an actionable message instead of a cryptic ImportError.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
elif [[ -x "/home/user/.venv/bin/python" ]]; then
  PY="/home/user/.venv/bin/python"
else
  PY="$(command -v python3)"
fi

if ! "$PY" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
  echo "error: fastapi/uvicorn missing for $PY" >&2
  echo "fix:   $PY -m pip install -r requirements.txt" >&2
  exit 1
fi

echo "serving $ROOT on http://$HOST:$PORT (python: $("$PY" -V 2>&1))"
exec "$PY" -m uvicorn app.main:app \
  --host "$HOST" \
  --port "$PORT" \
  --proxy-headers \
  --forwarded-allow-ips='*' \
  --timeout-keep-alive 65 \
  --log-level info
