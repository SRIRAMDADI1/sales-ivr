#!/usr/bin/env bash
# Firstpass Quotes / Azure App Service startup
#
# Root cause this script guards against:
# 1) Oryx extracts the built app to /tmp/<id> and only puts antenv on PYTHONPATH.
# 2) /home/site/wwwroot can still contain an empty/broken sales_ivr/ directory.
#    Never trust "-d sales_ivr" under wwwroot — it caused ModuleNotFoundError loops.
# 3) Derive APP_ROOT from the live antenv path on sys.path (always correct).

set -uo pipefail

PORT="${PORT:-8000}"

APP_ROOT="$(
  python - <<'PY'
import sys
from pathlib import Path

for entry in sys.path:
    p = Path(entry)
    # .../antenv/lib/python3.x/site-packages
    if p.name == "site-packages" and "antenv" in p.parts:
        # site-packages -> python3.x -> lib -> antenv -> app root
        print(p.resolve().parents[3])
        break
else:
    print("")
PY
)"

if [ -z "${APP_ROOT}" ] || [ ! -d "${APP_ROOT}" ]; then
  APP_ROOT="${APP_PATH:-${PWD:-/home/site/wwwroot}}"
fi

cd "${APP_ROOT}" || exit 1
export PYTHONPATH="${APP_ROOT}:${PYTHONPATH:-}"

if [ -f "${APP_ROOT}/config.yaml" ]; then
  export SALES_IVR_CONFIG_PATH="${APP_ROOT}/config.yaml"
fi

echo "Firstpass startup: APP_ROOT=${APP_ROOT}"
echo "Firstpass startup: listing APP_ROOT (first 40):"
ls -la "${APP_ROOT}" | head -n 40 || true

if [ ! -f "${APP_ROOT}/app.py" ]; then
  echo "Firstpass startup: FATAL — ${APP_ROOT}/app.py missing" >&2
  exit 1
fi

if ! python -c "import app; import sales_ivr" 2>/dev/null; then
  echo "Firstpass startup: FATAL — cannot import app/sales_ivr from ${APP_ROOT}" >&2
  python -c "import sys; print('sys.path=', sys.path)" >&2 || true
  ls -la "${APP_ROOT}/sales_ivr" 2>&1 | head -n 20 >&2 || true
  exit 1
fi

exec gunicorn \
  -w 2 \
  -k uvicorn.workers.UvicornWorker \
  --chdir "${APP_ROOT}" \
  --pythonpath "${APP_ROOT}" \
  app:app \
  --bind=0.0.0.0:"${PORT}"
