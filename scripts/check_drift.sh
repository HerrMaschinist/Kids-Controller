#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="/home/alex/kids_controller"
TARGET_DIR="/opt/kids_controller"

diff -rq \
  --exclude ".github" \
  --exclude ".git" \
  --exclude ".venv" \
  --exclude ".pytest_cache" \
  --exclude "__pycache__" \
  --exclude "*.pyc" \
  --exclude "kids_controller.egg-info" \
  --exclude ".env" \
  "$SOURCE_DIR" "$TARGET_DIR" || true
