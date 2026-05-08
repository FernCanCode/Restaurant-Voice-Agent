#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
PYTHON_BIN="${PYTHON_BIN:-python}"

if [[ -x ".venv/bin/python" && "${PYTHON_BIN}" == "python" ]]; then
  PYTHON_BIN=".venv/bin/python"
fi

if ! curl --silent --show-error --fail "${BASE_URL}/health" >/dev/null; then
  echo "App is not running at ${BASE_URL}."
  echo "Start it first, for example:"
  echo "  docker compose up --build"
  echo "Then rerun scripts/demo.sh"
  exit 1
fi

echo "Health check:"
curl --silent --show-error "${BASE_URL}/health"
echo
echo

session_response="$(curl --silent --show-error \
  -H 'Content-Type: application/json' \
  -d '{"channel":"browser"}' \
  "${BASE_URL}/api/sessions")"

echo "Session created:"
echo "${session_response}"
echo
echo

session_id="$(printf '%s' "${session_response}" | "${PYTHON_BIN}" -c 'import json,sys; print(json.load(sys.stdin)["session_id"])')"

run_turn() {
  local utterance="$1"
  echo "User: ${utterance}"
  curl --silent --show-error \
    -H 'Content-Type: application/json' \
    -d "{\"session_id\":\"${session_id}\",\"utterance\":\"${utterance}\",\"channel\":\"browser\",\"metadata\":{}}" \
    "${BASE_URL}/api/turn"
  echo
  echo
}

run_turn "What tacos do you have?"
run_turn "Add two chicken tacos with no onions"
run_turn "What is my total?"
run_turn "Put the order under Fernando"
run_turn "Read back my order"
run_turn "Yes, confirm"

echo "Demo complete."
