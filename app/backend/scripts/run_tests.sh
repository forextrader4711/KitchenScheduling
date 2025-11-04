#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${TEST_DATABASE_URL:-}" ]]; then
  echo "Running tests with in-memory SQLite"
else
  echo "Running tests with database: $TEST_DATABASE_URL"
fi

python -m pytest "$@"
