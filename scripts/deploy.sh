#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="/home/alex/kids_controller"
TARGET_DIR="/opt/kids_controller"
SERVICE_NAME="kids-controller"
VENV_DIR="$TARGET_DIR/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "source directory missing: $SOURCE_DIR" >&2
  exit 1
fi

mkdir -p "$TARGET_DIR"

echo "syncing source to target..."
rsync -a --delete \
  --exclude ".git/" \
  --exclude ".venv/" \
  --exclude ".pytest_cache/" \
  --exclude "__pycache__/" \
  --exclude "*.pyc" \
  --exclude "kids_controller.egg-info/" \
  --exclude "frontend/node_modules/" \
  --exclude ".env" \
  "$SOURCE_DIR/" "$TARGET_DIR/"

if [[ -f "$TARGET_DIR/frontend/package.json" ]]; then
  echo "installing frontend dependencies..."
  if [[ -f "$TARGET_DIR/frontend/package-lock.json" ]]; then
    npm ci --prefix "$TARGET_DIR/frontend"
  else
    npm install --prefix "$TARGET_DIR/frontend"
  fi

  echo "building frontend..."
  npm run build --prefix "$TARGET_DIR/frontend"
fi

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  echo "creating virtualenv in $VENV_DIR ..."
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

echo "installing application into virtualenv..."
"$VENV_DIR/bin/pip" install -e "$TARGET_DIR"

echo "restarting service..."
systemctl restart "$SERVICE_NAME"
sleep 2
systemctl --no-pager --full status "$SERVICE_NAME"
