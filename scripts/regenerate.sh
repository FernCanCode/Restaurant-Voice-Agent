#!/usr/bin/env bash
set -euo pipefail

echo "Regenerating project data and retrieval artifacts from the committed raw menu fixture..."
echo "Using Docker Compose-backed Makefile targets from the repository root."

echo "Step 1: Preparing data..."
make download-data

echo "Step 2: Preparing local model dependencies..."
make download-models

echo "Step 3: Running full reproduction pipeline..."
make reproduce

echo "Step 4: Verifying expected generated artifacts..."

required_files=(
  "data/processed/menu.json"
  "data/index/menu_chunks.json"
  "data/index/menu_metadata.json"
  "data/index/embeddings.npy"
)

missing=0

for file in "${required_files[@]}"; do
  if [[ ! -f "$file" ]]; then
    echo "ERROR: Expected artifact missing: $file" >&2
    missing=1
  else
    echo "OK: $file"
  fi
done

if [[ "$missing" -ne 0 ]]; then
  echo "Regeneration failed because one or more expected artifacts are missing." >&2
  exit 1
fi

echo "Regeneration completed successfully."
