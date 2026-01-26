#!/bin/bash
# Workaround for uv sandbox issues on macOS
set -e
cd "$(dirname "$0")"
source .venv/bin/activate
pytest "$@"
