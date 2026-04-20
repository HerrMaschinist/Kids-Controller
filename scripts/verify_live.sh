#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8001}"

echo "health:"
curl -fsS --max-time 5 "$BASE_URL/api/v1/health"
printf '\n\nstatus:\n'
curl -fsS --max-time 5 "$BASE_URL/api/v1/status"
printf '\n'
