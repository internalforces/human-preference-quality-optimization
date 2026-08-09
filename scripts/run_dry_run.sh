#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
PYTHONPATH=src python3 -m stringartio_preference_lab pipeline --dry-run --limit-runs=3
