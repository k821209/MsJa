#!/usr/bin/env bash
# Restart the Deevo web dashboard server
set -e

cd "$(dirname "$0")/.."

# Kill existing server
PID=$(lsof -ti tcp:3000 2>/dev/null || true)
if [ -n "$PID" ]; then
  echo "Stopping existing server (PID: $PID)..."
  kill "$PID" 2>/dev/null || true
  sleep 1
fi

# Start server
echo "Starting web server on http://localhost:3000 ..."
exec .venv/bin/python web/app.py
