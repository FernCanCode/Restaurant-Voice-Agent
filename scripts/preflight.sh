#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "${PYTHON_BIN}" ]]; then
  if [[ -x ".venv/bin/python" ]]; then
    PYTHON_BIN=".venv/bin/python"
  else
    PYTHON_BIN="python"
  fi
fi

PYTEST_BIN="${PYTEST_BIN:-}"
if [[ -z "${PYTEST_BIN}" ]]; then
  if [[ -x ".venv/bin/pytest" ]]; then
    PYTEST_BIN=".venv/bin/pytest"
  else
    PYTEST_BIN="pytest"
  fi
fi

RUFF_BIN="${RUFF_BIN:-}"
if [[ -z "${RUFF_BIN}" ]]; then
  if [[ -x ".venv/bin/ruff" ]]; then
    RUFF_BIN=".venv/bin/ruff"
  else
    RUFF_BIN="ruff"
  fi
fi

BLACK_BIN="${BLACK_BIN:-}"
if [[ -z "${BLACK_BIN}" ]]; then
  if [[ -x ".venv/bin/black" ]]; then
    BLACK_BIN=".venv/bin/black"
  else
    BLACK_BIN="black"
  fi
fi

MYPY_BIN="${MYPY_BIN:-}"
if [[ -z "${MYPY_BIN}" ]]; then
  if [[ -x ".venv/bin/mypy" ]]; then
    MYPY_BIN=".venv/bin/mypy"
  else
    MYPY_BIN="mypy"
  fi
fi

echo "Running compileall..."
PYTHONPATH=src "${PYTHON_BIN}" -m compileall src

echo "Running pytest..."
PYTHONPATH=src "${PYTEST_BIN}" -q

echo "Running ruff..."
"${RUFF_BIN}" check src tests

echo "Running black --check..."
"${BLACK_BIN}" --check src tests

echo "Running mypy..."
PYTHONPATH=src "${MYPY_BIN}" src

if [[ -x ".venv/bin/pip-audit" ]]; then
  echo "Running pip-audit..."
  mkdir -p reports
  set +e
  .venv/bin/pip-audit > reports/security.txt 2>&1
  audit_status=$?
  set -e
  if [[ ${audit_status} -ne 0 ]]; then
    echo "pip-audit reported issues or could not complete. See reports/security.txt"
  fi
fi
