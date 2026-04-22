#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="127.0.0.1"
PORT="18080"
SERVICE_NAME="test_case_mock_api"
LOG_FILE="${ROOT_DIR}/.mock_api.log"
PID_FILE="${ROOT_DIR}/.mock_api.pid"
STARTED_OWN_MOCK="0"
EXPECTED_CONFIG_SIGNATURE="$(python3 - <<'PY'
import hashlib
import os

username = os.getenv("DUMMYJSON_USERNAME", "emilys")
password = os.getenv("DUMMYJSON_PASSWORD", "emilyspass")
print(hashlib.sha256(f"dummyjson:{username}:{password}".encode("utf-8")).hexdigest()[:12])
PY
)"

healthcheck() {
  python3 - "${HOST}" "${PORT}" "${SERVICE_NAME}" "${EXPECTED_CONFIG_SIGNATURE}" <<'PY'
import json
import sys
import urllib.error
import urllib.request

host, port, service_name, expected_signature = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
url = f"http://{host}:{port}/_health"
try:
    with urllib.request.urlopen(url, timeout=0.2) as response:
        if response.status != 200:
            raise SystemExit(1)
        payload = json.loads(response.read().decode("utf-8"))
        if payload.get("service") != service_name:
            raise SystemExit(1)
        if payload.get("config_signature") != expected_signature:
            raise SystemExit(1)
except (urllib.error.URLError, ValueError, TimeoutError):
    raise SystemExit(1)
PY
}

cleanup() {
  if [[ "${STARTED_OWN_MOCK}" == "1" && -f "${PID_FILE}" ]]; then
    PID="$(cat "${PID_FILE}")"
    if kill -0 "${PID}" 2>/dev/null; then
      kill "${PID}" 2>/dev/null || true
      wait "${PID}" 2>/dev/null || true
    fi
    rm -f "${PID_FILE}"
  fi
}

trap cleanup EXIT

cd "${ROOT_DIR}"
if ! healthcheck; then
  if python3 - "${HOST}" "${PORT}" "${SERVICE_NAME}" <<'PY'
import json
import sys
import urllib.error
import urllib.request

host, port, service_name = sys.argv[1], sys.argv[2], sys.argv[3]
url = f"http://{host}:{port}/_health"
try:
    with urllib.request.urlopen(url, timeout=0.2) as response:
        if response.status != 200:
            raise SystemExit(1)
        payload = json.loads(response.read().decode("utf-8"))
        if payload.get("service") != service_name:
            raise SystemExit(1)
except (urllib.error.URLError, ValueError, TimeoutError):
    raise SystemExit(1)
PY
  then
    echo "existing mock api service is running with a different configuration; stop it first or align DUMMYJSON_USERNAME/DUMMYJSON_PASSWORD" >&2
    exit 1
  fi

  python3 -m uvicorn tests.mock_api.app:app --host "${HOST}" --port "${PORT}" >"${LOG_FILE}" 2>&1 &
  echo $! > "${PID_FILE}"
  STARTED_OWN_MOCK="1"

  for _ in $(seq 1 50); do
    if healthcheck; then
      break
    fi
    sleep 0.2
  done

  if ! healthcheck; then
    echo "mock api failed to start or service fingerprint mismatch" >&2
    cat "${LOG_FILE}" >&2 || true
    exit 1
  fi
fi

BASE_URL="${BASE_URL:-http://${HOST}:${PORT}}" \
JSONPLACEHOLDER_BASE_URL="${JSONPLACEHOLDER_BASE_URL:-http://${HOST}:${PORT}/jsonplaceholder}" \
DUMMYJSON_BASE_URL="${DUMMYJSON_BASE_URL:-http://${HOST}:${PORT}/dummyjson}" \
DUMMYJSON_USERNAME="${DUMMYJSON_USERNAME:-emilys}" \
DUMMYJSON_PASSWORD="${DUMMYJSON_PASSWORD:-emilyspass}" \
python3 -m pytest tests/test_mock_api_unit.py tests/test_external_public_apis_unit.py tests/test_external_public_apis.py "$@"
