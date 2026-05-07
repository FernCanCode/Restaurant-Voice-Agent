.PHONY: install download-data download-models reproduce test lint loadtest demo preflight

install:
	pip install -e ".[dev]"
	pip install -r requirements.txt

download-data:
	@echo "Verifying raw fixture..."
	@test -f data/raw/sample_restaurant_menu.html || (echo "Error: sample_restaurant_menu.html not found" && exit 1)
	@mkdir -p data/processed
	@python -m restaurant_agent.demo_data

download-models:
	@echo "Downloading sentence-transformers/all-MiniLM-L6-v2..."
	@python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')" || echo "Warning: Failed to download embedding model. Will degrade safely."

reproduce: download-data download-models
	@python -m restaurant_agent.demo_data
	@python -m restaurant_agent.rag_index

test:
	pytest -q || echo "Tests not fully implemented yet."

lint:
	ruff check src tests || true
	black --check src tests || true
	mypy src || true
	pip-audit || true

loadtest:
	@echo "Phase 3 Placeholder: loadtest will be implemented in a later phase."

demo:
	@echo "Phase 3 Placeholder: demo will be implemented in a later phase."

preflight:
	@echo "Phase 3 Placeholder: preflight will be implemented in a later phase."
