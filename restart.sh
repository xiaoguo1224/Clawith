#!/bin/bash
# Clawith 一键重启脚本
# Usage: ./restart.sh

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
BACKEND_LOG="/tmp/clawith_backend.log"
FRONTEND_LOG="/tmp/clawith_frontend.log"
BACKEND_PID="/tmp/clawith_backend.pid"
FRONTEND_PID="/tmp/clawith_frontend.pid"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; NC='\033[0m'

cleanup() {
    echo -e "${YELLOW}🔄 Stopping existing services...${NC}"
    # Kill by PID file first
    for pidfile in "$BACKEND_PID" "$FRONTEND_PID"; do
        if [ -f "$pidfile" ]; then
            kill -9 "$(cat "$pidfile")" 2>/dev/null || true
            rm -f "$pidfile"
        fi
    done
    # Kill by port as fallback
    lsof -ti:8008 | xargs kill -9 2>/dev/null || true
    lsof -ti:3008 | xargs kill -9 2>/dev/null || true
    sleep 1
}

wait_for_port() {
    local port=$1 name=$2 max=$3
    for i in $(seq 1 "$max"); do
        if curl -s -o /dev/null -m 1 "http://localhost:$port" 2>/dev/null; then
            echo -e "  ${GREEN}✅ $name ready (${i}s)${NC}"
            return 0
        fi
        sleep 1
    done
    echo -e "  ${RED}❌ $name failed to start in ${max}s${NC}"
    return 1
}

cleanup

# Ensure PostgreSQL is running
if ! pg_isready -h localhost -p 5432 -q 2>/dev/null; then
    echo -e "${YELLOW}🐘 Starting PostgreSQL...${NC}"
    brew services start postgresql@15 2>/dev/null || brew services start postgresql 2>/dev/null || true
    for i in $(seq 1 10); do
        if pg_isready -h localhost -p 5432 -q 2>/dev/null; then
            echo -e "  ${GREEN}✅ PostgreSQL ready (${i}s)${NC}"
            break
        fi
        sleep 1
        if [ "$i" -eq 10 ]; then
            echo -e "  ${RED}❌ PostgreSQL failed to start${NC}"
            exit 1
        fi
    done
else
    echo -e "${GREEN}🐘 PostgreSQL already running${NC}"
fi

# Start backend
echo -e "${YELLOW}🚀 Starting backend...${NC}"
cd "$BACKEND_DIR"
nohup env PYTHONUNBUFFERED=1 \
    PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-}" \
    DATABASE_URL="postgresql+asyncpg://clawith:clawith@localhost:5432/clawith?ssl=disable" \
    .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8008 \
    > "$BACKEND_LOG" 2>&1 &
echo $! > "$BACKEND_PID"
wait_for_port 8008 "Backend" 10

# Start frontend (call vite directly, not npm run dev)
echo -e "${YELLOW}🚀 Starting frontend...${NC}"
cd "$FRONTEND_DIR"
nohup node_modules/.bin/vite --port 3008 \
    > "$FRONTEND_LOG" 2>&1 &
echo $! > "$FRONTEND_PID"
wait_for_port 3008 "Frontend" 8

# Verify proxy
echo -e "${YELLOW}🔍 Verifying API proxy...${NC}"
HEALTH=$(curl -s -m 3 http://localhost:3008/api/health 2>/dev/null || echo "FAIL")
if echo "$HEALTH" | grep -q "ok"; then
    echo -e "  ${GREEN}✅ Proxy working${NC}"
else
    echo -e "  ${YELLOW}⚠️  Proxy may need a moment, backend direct check:${NC}"
    curl -s http://localhost:8008/api/health && echo ""
fi

echo ""
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo -e "${GREEN}  Clawith running!${NC}"
echo -e "${GREEN}  Frontend: http://localhost:3008${NC}"
echo -e "${GREEN}  Backend:  http://localhost:8008${NC}"
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo -e "  Backend log:  tail -f $BACKEND_LOG"
echo -e "  Frontend log: tail -f $FRONTEND_LOG"
