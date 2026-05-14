#!/usr/bin/env bash
set -euo pipefail

echo "Running compileall..."
python -m compileall src

echo "Running pytest..."
pytest -q

echo "Running ruff..."
ruff check src tests

echo "Running black --check..."
black --check src tests

echo "Running mypy..."
mypy src

if command -v pip-audit >/dev/null 2>&1; then
  echo "Running pip-audit..."
  mkdir -p reports
  set +e
  pip-audit > reports/security.txt 2>&1
  audit_status=$?
  set -e
  if [ "${audit_status}" -ne 0 ]; then
    if grep -Eiq "(critical|high)" reports/security.txt; then
      echo "pip-audit found Critical/High issues. See reports/security.txt"
      exit 1
    fi
    echo "pip-audit reported non-blocking issues or could not complete. See reports/security.txt"
  fi
fi
