#!/bin/sh
set -e
# Ensure JSONL roots exist on the mounted volume
mkdir -p "${DATA_DIR:-/data}/replay" "${DATA_DIR:-/data}/learning" "${DATA_DIR:-/data}/research"
# Phase 1: single worker — TradePlan/OrderEngine are in-process memory (not shared).
exec gunicorn --bind "0.0.0.0:${PORT:-8080}" --workers 1 --threads 8 --timeout 120 app:app
