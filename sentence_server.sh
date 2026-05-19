#!/usr/bin/env bash
# Sentence Server wrapper - starts the web API for mined sentences
set -e
cd "$(dirname "$0")"
PORT="${1:-5002}"
PID_FILE="/tmp/miner-v2-server.pid"

# Kill existing server if running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE" 2>/dev/null)
    if kill -0 "$OLD_PID" 2>/dev/null; then
        kill "$OLD_PID" 2>/dev/null || true
        sleep 0.5
    fi
    rm -f "$PID_FILE"
fi

# Start server in background
python3 sentence_server.py --port "$PORT" &
SERVER_PID=$!
echo "$SERVER_PID" > "$PID_FILE"

echo "Sentence Server started on http://localhost:$PORT (PID: $SERVER_PID)"
echo "API endpoints:"
echo "  GET  /api/sentences       - List all sentences"
echo "  GET  /api/sentences/<id>  - Get single sentence"
echo "  POST /api/add             - Add sentence"
echo "  GET  /api/stats           - Statistics"
echo "  POST /api/yomitan/find    - Yomitan: find sentences with term"
echo "  POST /api/yomitan/term    - Yomitan: get term definitions"
echo "  GET  /api/yomitan/recent  - Yomitan: recent sentences"
echo ""
echo "Web viewer: http://localhost:$PORT"

wait "$SERVER_PID"
