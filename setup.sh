#!/usr/bin/env bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
PYTHON="$VENV_DIR/bin/python"

echo ""
echo "╔═══════════════════════════════════════╗"
echo "║  Deevo AI Secretary — Setup           ║"
echo "╚═══════════════════════════════════════╝"
echo ""
echo "Project: $PROJECT_DIR"
echo ""

# ── 1. Python check ──
if ! command -v python3 &>/dev/null; then
    echo "❌ python3 not found. Please install Python 3.11+."
    exit 1
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✓ Python $PY_VER detected"

# ── 2. Virtual environment ──
if [ ! -d "$VENV_DIR" ]; then
    echo "→ Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
else
    echo "✓ Virtual environment exists"
fi

# ── 3. Install dependencies ──
echo "→ Installing dependencies..."
"$VENV_DIR/bin/pip" install -q --upgrade pip
"$VENV_DIR/bin/pip" install -q -e ".[dev]"
echo "✓ Dependencies installed"

# ── 4. Initialize database ──
echo "→ Initializing database..."
"$PYTHON" -c "from src.db import init_db; init_db()"
echo "✓ Database ready (data/persona.db)"

# ── 5. Seed lore ──
echo "→ Seeding initial lore..."
"$PYTHON" scripts/seed_lore.py
echo "✓ Lore seeded"

# ── 6. Generate .mcp.json ──
echo "→ Generating .mcp.json..."
cat > "$PROJECT_DIR/.mcp.json" <<EOF
{
  "mcpServers": {
    "persona": {
      "type": "stdio",
      "command": "$PYTHON",
      "args": ["run_mcp.py"],
      "cwd": "$PROJECT_DIR"
    }
  }
}
EOF
echo "✓ MCP config generated"

# ── 7. Create directories ──
mkdir -p "$PROJECT_DIR/data"
mkdir -p "$PROJECT_DIR/persona/avatar"
mkdir -p "$PROJECT_DIR/web/static/uploads"

# ── 8. Verify ──
echo ""
echo "── Verification ──"
FAIL=0

"$PYTHON" -c "from src.db import init_db; conn = init_db(); conn.close()" 2>/dev/null \
    && echo "✓ DB connection OK" || { echo "❌ DB connection failed"; FAIL=1; }

"$PYTHON" -c "from src.mcp_server import mcp" 2>/dev/null \
    && echo "✓ MCP server import OK" || { echo "❌ MCP server import failed"; FAIL=1; }

"$PYTHON" -c "from web.app import app" 2>/dev/null \
    && echo "✓ Web app import OK" || { echo "❌ Web app import failed"; FAIL=1; }

[ -f "$PROJECT_DIR/.mcp.json" ] \
    && echo "✓ .mcp.json exists" || { echo "❌ .mcp.json missing"; FAIL=1; }

[ -f "$PROJECT_DIR/.claude/settings.json" ] \
    && echo "✓ Claude hooks configured" || { echo "❌ .claude/settings.json missing"; FAIL=1; }

echo ""
if [ $FAIL -eq 0 ]; then
    echo "══════════════════════════════════════════"
    echo "  ✅ Setup complete! All checks passed."
    echo ""
    echo "  Start MsJa:"
    echo "    cd $PROJECT_DIR"
    echo "    claude"
    echo ""
    echo "  (Web dashboard starts automatically"
    echo "   on first claude session)"
    echo "══════════════════════════════════════════"
else
    echo "⚠️  Setup finished with errors. Check above."
fi
echo ""
