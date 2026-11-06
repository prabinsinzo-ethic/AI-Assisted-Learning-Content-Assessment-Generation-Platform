#!/usr/bin/env bash
set -e
PORT=8001
ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
PIDFILE="$ROOT/server.pid"

stop_server() {
  if [ -f "$PIDFILE" ]; then
    kill "$(cat "$PIDFILE")" 2>/dev/null || true
    rm -f "$PIDFILE"
  fi
  # fallback: kill anything listening on PORT
  if command -v lsof >/dev/null 2>&1; then
    lsof -ti tcp:$PORT | xargs -r kill 2>/dev/null || true
  fi
  echo "Server stopped."
}

start_server() {
  cd "$BACKEND"
  nohup python -m uvicorn app.main:app --reload --port $PORT > "$ROOT/server.log" 2>&1 &
  echo $! > "$PIDFILE"
  echo "Server started on http://127.0.0.1:$PORT (PID $(cat $PIDFILE))"
}

case "${1:-start}" in
  start)
    start_server
    ;;
  stop)
    stop_server
    ;;
  restart)
    stop_server
    sleep 2
    start_server
    ;;
  status)
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      echo "Server is running (PID $(cat $PIDFILE))."
    else
      echo "Server is NOT running."
    fi
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status}"
    exit 1
    ;;
esac