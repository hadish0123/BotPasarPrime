#!/bin/sh
set -eu

python run_central_bot.py &
BOT_PID=$!

cleanup() {
  kill "$BOT_PID" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
