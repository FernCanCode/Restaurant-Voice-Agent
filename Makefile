.PHONY: install download-data download-models reproduce test lint loadtest demo preflight contributions

PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,python)
PYTEST := $(if $(wildcard .venv/bin/pytest),.venv/bin/pytest,pytest)
RUFF := $(if $(wildcard .venv/bin/ruff),.venv/bin/ruff,ruff)
BLACK := $(if $(wildcard .venv/bin/black),.venv/bin/black,black)
MYPY := $(if $(wildcard .venv/bin/mypy),.venv/bin/mypy,mypy)
PIP_AUDIT := $(if $(wildcard .venv/bin/pip-audit),.venv/bin/pip-audit,pip-audit)
LOCUST := $(if $(wildcard .venv/bin/locust),.venv/bin/locust,locust)

install:
	$(PYTHON) -m pip install -e ".[dev]"
	$(PYTHON) -m pip install -r requirements.txt

download-data:
	@echo "Verifying raw fixture..."
	@test -f data/raw/sample_restaurant_menu.html || (echo "Error: sample_restaurant_menu.html not found" && exit 1)
	@mkdir -p data/processed
	@PYTHONPATH=src $(PYTHON) -m restaurant_agent.demo_data

download-models:
	@echo "Downloading sentence-transformers/all-MiniLM-L6-v2..."
	@PYTHONPATH=src $(PYTHON) -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')" || echo "Warning: Failed to download embedding model. Will degrade safely."

reproduce: download-data download-models
	@PYTHONPATH=src $(PYTHON) -m restaurant_agent.demo_data
	@PYTHONPATH=src $(PYTHON) -m restaurant_agent.rag_index

test:
	@mkdir -p reports/coverage_html
	PYTHONPATH=src $(PYTEST) tests/unit -q --junitxml=reports/unit.xml
	PYTHONPATH=src $(PYTEST) tests/integration -q --junitxml=reports/integration.xml
	PYTHONPATH=src $(PYTEST) tests/user_stories -q --junitxml=reports/user_stories.xml
	PYTHONPATH=src $(PYTEST) tests -q --cov=src/restaurant_agent --cov-report=xml:reports/coverage.xml --cov-report=html:reports/coverage_html

lint:
	@mkdir -p reports
	$(RUFF) check src tests
	$(BLACK) --check src tests
	$(MYPY) src
	@set +e; \
	$(PIP_AUDIT) > reports/security.txt 2>&1; \
	audit_status=$$?; \
	set -e; \
	if [ $$audit_status -ne 0 ]; then \
		echo "pip-audit reported issues or could not complete. See reports/security.txt"; \
	else \
		echo "pip-audit report written to reports/security.txt"; \
	fi

loadtest:
	@mkdir -p reports
	@TARGET_HOST="$${TARGET_HOST:-http://localhost:8000}"; \
	TIMESTAMP="$$(date -u +"%Y-%m-%dT%H:%M:%SZ")"; \
	THRESHOLD_RPS=10; \
	THRESHOLD_FAIL=0.05; \
	if ! curl --silent --show-error --fail --max-time 3 "$$TARGET_HOST/health" >/dev/null 2>&1; then \
		printf '{\n  "timestamp": "%s",\n  "target_host": "%s",\n  "target_endpoint": "POST /api/turn",\n  "duration_seconds": 0,\n  "total_requests": 0,\n  "failed_requests": 0,\n  "requests_per_second": 0.0,\n  "failure_rate": 0.0,\n  "median_latency_ms": 0.0,\n  "p95_latency_ms": 0.0,\n  "p99_latency_ms": 0.0,\n  "thresholds": {\n    "min_requests_per_second": %s,\n    "max_failure_rate": %.2f\n  },\n  "passed": false,\n  "notes": "Skipped benchmark because the app was unavailable at %s"\n}\n' "$$TIMESTAMP" "$$TARGET_HOST" "$$THRESHOLD_RPS" "$$THRESHOLD_FAIL" "$$TARGET_HOST" > reports/benchmarks.json; \
		cat reports/benchmarks.json; \
		exit 0; \
	fi; \
	SESSION_RESPONSE="$$(curl --silent --show-error --fail --max-time 5 -H 'Content-Type: application/json' -d '{"channel":"browser"}' "$$TARGET_HOST/api/sessions")"; \
	SESSION_ID="$$(printf '%s' "$$SESSION_RESPONSE" | $(PYTHON) -c 'import json,sys; print(json.load(sys.stdin)["session_id"])')"; \
	TMP_LATENCIES="$$(mktemp)"; \
	FAILED=0; \
	TOTAL=0; \
	START_NS="$$(date +%s%N)"; \
	for UTTERANCE in "What tacos do you have?" "Add one chicken taco with no onions." "What is my total?"; do \
		for _ in 1 2 3 4 5; do \
			TURN_START_NS="$$(date +%s%N)"; \
			if ! curl --silent --show-error --fail --max-time 5 -H 'Content-Type: application/json' -d "{\"session_id\":\"$$SESSION_ID\",\"utterance\":\"$$UTTERANCE\",\"channel\":\"browser\",\"metadata\":{}}" "$$TARGET_HOST/api/turn" >/dev/null; then \
				FAILED=$$((FAILED + 1)); \
			fi; \
			TURN_END_NS="$$(date +%s%N)"; \
			echo $$(((TURN_END_NS - TURN_START_NS) / 1000000)) >> "$$TMP_LATENCIES"; \
			TOTAL=$$((TOTAL + 1)); \
		done; \
	done; \
	END_NS="$$(date +%s%N)"; \
	DURATION_MS=$$(((END_NS - START_NS) / 1000000)); \
	REPORT_PATH="reports/benchmarks.json" TARGET_HOST="$$TARGET_HOST" TIMESTAMP="$$TIMESTAMP" TMP_LATENCIES="$$TMP_LATENCIES" TOTAL="$$TOTAL" FAILED="$$FAILED" DURATION_MS="$$DURATION_MS" THRESHOLD_RPS="$$THRESHOLD_RPS" THRESHOLD_FAIL="$$THRESHOLD_FAIL" $(PYTHON) -c 'import json, math, os, statistics; \
latencies=[float(line.strip()) for line in open(os.environ["TMP_LATENCIES"], "r", encoding="utf-8") if line.strip()]; \
total=int(os.environ["TOTAL"]); failed=int(os.environ["FAILED"]); duration_ms=max(int(os.environ["DURATION_MS"]), 1); success=total-failed; \
def pct(values, q): \
    values=sorted(values); \
    return values[min(len(values)-1, max(0, math.ceil(q*len(values))-1))] if values else 0.0; \
failure_rate=(failed/total) if total else 0.0; rps=(success/(duration_ms/1000.0)) if duration_ms else 0.0; \
report={"timestamp": os.environ["TIMESTAMP"], "target_host": os.environ["TARGET_HOST"], "target_endpoint": "POST /api/turn", "duration_seconds": round(duration_ms/1000.0, 3), "total_requests": total, "failed_requests": failed, "requests_per_second": round(rps, 3), "failure_rate": round(failure_rate, 4), "median_latency_ms": round(statistics.median(latencies), 3) if latencies else 0.0, "p95_latency_ms": round(pct(latencies, 0.95), 3), "p99_latency_ms": round(pct(latencies, 0.99), 3), "thresholds": {"min_requests_per_second": int(os.environ["THRESHOLD_RPS"]), "max_failure_rate": float(os.environ["THRESHOLD_FAIL"])}, "passed": rps >= int(os.environ["THRESHOLD_RPS"]) and failure_rate <= float(os.environ["THRESHOLD_FAIL"]), "notes": "Deterministic lightweight benchmark using /api/sessions and POST /api/turn. Locust scenario remains available in tests/load/locustfile.py."}; \
json.dump(report, open(os.environ["REPORT_PATH"], "w", encoding="utf-8"), indent=2); \
print(json.dumps(report, indent=2))'; \
	rm -f "$$TMP_LATENCIES"

demo:
	@bash scripts/demo.sh

preflight:
	@bash scripts/preflight.sh

contributions:
	@mkdir -p reports
	@set +e; \
	git shortlog -sne --all --no-merges > reports/git_contributions.txt 2>&1; \
	shortlog_status=$$?; \
	set -e; \
	if [ $$shortlog_status -ne 0 ]; then \
		echo "Git history unavailable in the current environment." > reports/git_contributions.txt; \
	fi
