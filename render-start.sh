#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8000}"
exec python3 -m uvicorn aci_inventory_api:app --host 0.0.0.0 --port "$PORT"

