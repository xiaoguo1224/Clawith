#!/usr/bin/env bash
# ────────────────────────────────────────────────
# Clawith — First-time Setup Script
# Sets up backend, frontend, database, and seed data.
# ────────────────────────────────────────────────
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; CYAN='\033[0;36m'; NC='\033[0m'
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo -e "${CYAN}═══════════════════════════════════════${NC}"
echo -e "${CYAN}  🦞 Clawith — First-time Setup${NC}"
echo -e "${CYAN}═══════════════════════════════════════${NC}"
echo ""

# ── 1. Environment file ──────────────────────────
echo -e "${YELLOW}[1/5]${NC} Checking environment file..."
if [ ! -f "$ROOT/.env" ]; then
    cp "$ROOT/.env.example" "$ROOT/.env"
    echo -e "  ${GREEN}✓${NC} Created .env from .env.example"
    echo -e "  ${YELLOW}⚠${NC}  Please edit .env to set SECRET_KEY and JWT_SECRET_KEY before production use."
else
    echo -e "  ${GREEN}✓${NC} .env already exists"
fi

# ── 2. PostgreSQL setup ──────────────────────────
echo ""
echo -e "${YELLOW}[2/6]${NC} Setting up PostgreSQL..."

if command -v psql &>/dev/null; then
    # Create role if it doesn't exist
    if ! psql -U "$USER" -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='clawith'" 2>/dev/null | grep -q 1; then
        createuser clawith 2>/dev/null && echo -e "  ${GREEN}✓${NC} Created PostgreSQL role: clawith" || true
        psql -U "$USER" -d postgres -c "ALTER ROLE clawith WITH LOGIN PASSWORD 'clawith';" &>/dev/null
    else
        echo -e "  ${GREEN}✓${NC} Role 'clawith' already exists"
    fi

    # Create database if it doesn't exist
    if ! psql -U "$USER" -lqt 2>/dev/null | cut -d\| -f1 | grep -qw clawith; then
        createdb -O clawith clawith 2>/dev/null && echo -e "  ${GREEN}✓${NC} Created database: clawith"
    else
        echo -e "  ${GREEN}✓${NC} Database 'clawith' already exists"
    fi

    # Ensure DATABASE_URL is set with ssl=disable for local dev
    if grep -q "^DATABASE_URL=.*localhost.*" "$ROOT/.env" 2>/dev/null; then
        if ! grep -q "ssl=disable" "$ROOT/.env" 2>/dev/null; then
            sed -i '' 's|^\(DATABASE_URL=.*localhost[^?]*\)$|\1?ssl=disable|' "$ROOT/.env" 2>/dev/null
            echo -e "  ${GREEN}✓${NC} Added ssl=disable to DATABASE_URL for local dev"
        fi
    fi
    # If no DATABASE_URL is active, add one
    if ! grep -q "^DATABASE_URL=" "$ROOT/.env" 2>/dev/null; then
        echo "DATABASE_URL=postgresql+asyncpg://clawith:clawith@localhost:5432/clawith?ssl=disable" >> "$ROOT/.env"
        echo -e "  ${GREEN}✓${NC} Added DATABASE_URL to .env"
    fi
else
    echo -e "  ${YELLOW}⚠${NC}  psql not found — skipping PostgreSQL auto-setup."
    echo "    Please create the database manually. See README for details."
fi

# ── 3. Backend setup ─────────────────────────────
echo ""
echo -e "${YELLOW}[3/6]${NC} Setting up backend..."
cd "$ROOT/backend"

if [ ! -d ".venv" ]; then
    echo "  Creating Python virtual environment..."
    python3 -m venv .venv
    echo -e "  ${GREEN}✓${NC} Virtual environment created"
fi

echo "  Installing dependencies..."
.venv/bin/pip install -e ".[dev]" -q 2>&1 | tail -1
echo -e "  ${GREEN}✓${NC} Backend dependencies installed"

# ── 3. Frontend setup ────────────────────────────
echo ""
echo -e "${YELLOW}[4/6]${NC} Setting up frontend..."
cd "$ROOT/frontend"

if [ ! -d "node_modules" ]; then
    echo "  Installing npm packages..."
    npm install --silent 2>&1 | tail -1
fi
echo -e "  ${GREEN}✓${NC} Frontend dependencies installed"

# ── 4. Database setup ────────────────────────────
echo ""
echo -e "${YELLOW}[5/6]${NC} Setting up database..."
cd "$ROOT/backend"

# Source .env for DATABASE_URL
if [ -f "$ROOT/.env" ]; then
    set -a
    source "$ROOT/.env"
    set +a
fi

# ── 5. Seed data ─────────────────────────────────
echo ""
echo -e "${YELLOW}[6/6]${NC} Running database seed..."

if .venv/bin/python seed.py 2>&1 | while IFS= read -r line; do echo "  $line"; done; then
    echo ""
else
    echo ""
    echo -e "  ${RED}✗ Seed failed.${NC}"
    echo "  Common fixes:"
    echo "    1. Make sure PostgreSQL is running"
    echo "    2. Set DATABASE_URL in .env, e.g.:"
    echo "       DATABASE_URL=postgresql+asyncpg://clawith:clawith@localhost:5432/clawith"
    echo "    3. Create the database first:"
    echo "       createdb clawith"
    echo ""
    echo "  After fixing, re-run: bash setup.sh"
    exit 1
fi

# ── Summary ──────────────────────────────────────
echo ""
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo -e "${GREEN}  🎉 Setup complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo ""
echo "  To start the application:"
echo ""
echo -e "  ${CYAN}Option A: One-command start${NC}"
echo "    bash restart.sh"
echo ""
echo -e "  ${CYAN}Option B: Manual start${NC}"
echo "    # Terminal 1 — Backend"
echo "    cd backend && .venv/bin/uvicorn app.main:app --reload --port 8008"
echo ""
echo "    # Terminal 2 — Frontend"
echo "    cd frontend && npm run dev -- --port 3008"
echo ""
echo -e "  ${CYAN}Option C: Docker${NC}"
echo "    docker compose up -d"
echo ""
echo "  The first user to register becomes the platform admin."
echo ""
