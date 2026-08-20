#!/bin/sh
set -e
# Ensure JSONL roots exist on the mounted volume
mkdir -p "${DATA_DIR:-/data}/replay" "${DATA_DIR:-/data}/learning" "${DATA_DIR:-/data}/research"
exec gunicorn --bind "0.0.0.0:${PORT:-8080}" --workers 2 --threads 4 --timeout 120 app:app
