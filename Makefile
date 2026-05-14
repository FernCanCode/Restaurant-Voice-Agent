.PHONY: install download-data download-models reproduce test lint loadtest demo preflight contributions

COMPOSE ?= docker compose
APP_SERVICE ?= app
DOCKER_RUN := $(COMPOSE) run --rm -T $(APP_SERVICE)

install:
	$(COMPOSE) build $(APP_SERVICE)

download-data:
	@echo "Verifying raw fixture..."
	@test -f data/raw/sample_restaurant_menu.html || (echo "Error: sample_restaurant_menu.html not found" && exit 1)
	@mkdir -p data/processed
	@$(DOCKER_RUN) python -m restaurant_agent.demo_data

download-models:
	@echo "Downloading sentence-transformers/all-MiniLM-L6-v2..."
	@$(DOCKER_RUN) python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')" || echo "Warning: Failed to download embedding model. Will degrade safely."

reproduce: download-data download-models
	@$(DOCKER_RUN) python -m restaurant_agent.demo_data
	@$(DOCKER_RUN) python -m restaurant_agent.rag_index

test:
	@mkdir -p reports/coverage_html
	@set +e; \
	unit_status=0; \
	integration_status=0; \
	user_story_status=0; \
	coverage_status=0; \
	$(DOCKER_RUN) pytest tests/unit -q --junitxml=reports/unit.xml; unit_status=$$?; \
	$(DOCKER_RUN) pytest tests/integration -q --junitxml=reports/integration.xml; integration_status=$$?; \
	$(DOCKER_RUN) pytest tests/user_stories -q --junitxml=reports/user_stories.xml; user_story_status=$$?; \
	$(DOCKER_RUN) pytest tests -q --cov=src/restaurant_agent --cov-report=xml:reports/coverage.xml --cov-report=html:reports/coverage_html; coverage_status=$$?; \
	set -e; \
	if [ $$unit_status -ne 0 ] || [ $$integration_status -ne 0 ] || [ $$user_story_status -ne 0 ] || [ $$coverage_status -ne 0 ]; then \
		exit 1; \
	fi

lint:
	@mkdir -p reports
	$(DOCKER_RUN) ruff check src tests
	$(DOCKER_RUN) black --check src tests
	$(DOCKER_RUN) mypy src
	@set +e; \
	$(DOCKER_RUN) pip-audit > reports/security.txt 2>&1; \
	audit_status=$$?; \
	set -e; \
	if [ $$audit_status -ne 0 ]; then \
		if grep -Eiq "(critical|high)" reports/security.txt; then \
			echo "pip-audit found Critical/High issues. See reports/security.txt"; \
			exit 1; \
		fi; \
		echo "pip-audit could not complete cleanly or reported non-blocking issues. See reports/security.txt"; \
	else \
		echo "pip-audit report written to reports/security.txt"; \
	fi

loadtest:
	@mkdir -p reports
	@TARGET_HOST="$${TARGET_HOST:-http://localhost:8000}"; \
	TIMESTAMP="$$(date -u +"%Y-%m-%dT%H:%M:%SZ")"; \
	THRESHOLD_RPS=10; \
	THRESHOLD_FAIL=0.05; \
	if ! $(COMPOSE) ps --status running $(APP_SERVICE) >/dev/null 2>&1 || ! curl --silent --show-error --fail --max-time 3 "$$TARGET_HOST/health" >/dev/null 2>&1; then \
		printf '{\n  "timestamp": "%s",\n  "target_host": "%s",\n  "target_endpoint": "POST /api/turn",\n  "duration_seconds": 0,\n  "total_requests": 0,\n  "failed_requests": 0,\n  "requests_per_second": 0.0,\n  "failure_rate": 0.0,\n  "median_latency_ms": 0.0,\n  "p95_latency_ms": 0.0,\n  "p99_latency_ms": 0.0,\n  "thresholds": {\n    "min_requests_per_second": %s,\n    "max_failure_rate": %.2f\n  },\n  "passed": false,\n  "notes": "Skipped benchmark because the app was unavailable at %s"\n}\n' "$$TIMESTAMP" "$$TARGET_HOST" "$$THRESHOLD_RPS" "$$THRESHOLD_FAIL" "$$TARGET_HOST" > reports/benchmarks.json; \
		cat reports/benchmarks.json; \
		exit 0; \
	fi; \
	$(COMPOSE) exec -T \
		-e TARGET_HOST="$$TARGET_HOST" \
		-e BENCHMARK_MIN_RPS="$$THRESHOLD_RPS" \
		-e BENCHMARK_MAX_FAILURE_RATE="$$THRESHOLD_FAIL" \
		$(APP_SERVICE) python scripts/run_turn_benchmark.py

demo:
	@DOCKER_COMPOSE_COMMAND="$(COMPOSE)" bash scripts/demo.sh

preflight:
	$(DOCKER_RUN) sh scripts/preflight.sh

contributions:
	@mkdir -p reports
	@set +e; \
	git shortlog -sne --all --no-merges > reports/git_contributions.txt 2>&1; \
	shortlog_status=$$?; \
	set -e; \
	if [ $$shortlog_status -ne 0 ]; then \
		echo "Git history unavailable in the current environment." > reports/git_contributions.txt; \
	fi
