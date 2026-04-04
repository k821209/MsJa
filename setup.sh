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

# ── 1. Claude Code check ──
if command -v claude &>/dev/null && claude --version &>/dev/null 2>&1; then
    CLAUDE_VER=$(claude --version 2>/dev/null)
    echo "✓ Claude Code installed ($CLAUDE_VER)"
else
    echo "⚠ Claude Code not found."
    read -p "  Install Claude Code? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "→ Installing Claude Code..."
        curl -fsSL https://claude.ai/install.sh | bash
        # Add to PATH permanently + current session
        CLAUDE_BIN=""
        if [ -d "$HOME/.claude/bin" ]; then
            CLAUDE_BIN="$HOME/.claude/bin"
        elif [ -d "$HOME/.local/bin" ]; then
            CLAUDE_BIN="$HOME/.local/bin"
        fi
        if [ -n "$CLAUDE_BIN" ]; then
            export PATH="$CLAUDE_BIN:$PATH"
            # Add to shell rc if not already there
            SHELL_RC="$HOME/.bashrc"
            [ -n "$ZSH_VERSION" ] && SHELL_RC="$HOME/.zshrc"
            [ -f "$HOME/.zshrc" ] && SHELL_RC="$HOME/.zshrc"
            if ! grep -q "$CLAUDE_BIN" "$SHELL_RC" 2>/dev/null; then
                echo "export PATH=\"$CLAUDE_BIN:\$PATH\"" >> "$SHELL_RC"
                echo "  → Added $CLAUDE_BIN to $SHELL_RC"
            fi
        fi
        if command -v claude &>/dev/null; then
            echo "✓ Claude Code installed"
        else
            echo "✓ Claude Code installed (run: source ~/.bashrc or restart terminal)"
        fi
    else
        echo "  Skipped. Install later: curl -fsSL https://claude.ai/install.sh | bash"
    fi
fi

# ── 2. Python check ──
if command -v python3 &>/dev/null; then
    SYS_PYTHON=python3
elif command -v python &>/dev/null; then
    SYS_PYTHON=python
else
    echo "❌ python not found. Please install Python 3.11+."
    exit 1
fi

PY_VER=$($SYS_PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✓ Python $PY_VER detected ($(command -v $SYS_PYTHON))"

# ── 2. Virtual environment ──
# Always recreate if venv is broken — moving/renaming the project
# breaks all shebangs (python, pip, etc.) inside .venv/bin/
NEED_VENV=0
if [ ! -d "$VENV_DIR" ]; then
    NEED_VENV=1
elif ! "$PYTHON" -c "import sys" &>/dev/null 2>&1; then
    echo "⚠ venv python is broken. Recreating..."
    NEED_VENV=1
elif ! "$PYTHON" -m pip --version &>/dev/null 2>&1; then
    echo "⚠ venv pip is broken. Recreating..."
    NEED_VENV=1
fi

if [ $NEED_VENV -eq 1 ]; then
    rm -rf "$VENV_DIR"
    echo "→ Creating virtual environment..."
    $SYS_PYTHON -m venv "$VENV_DIR"
else
    echo "✓ Virtual environment OK"
fi

# ── 3. Install dependencies ──
echo "→ Installing dependencies..."
"$PYTHON" -m pip install -q --upgrade pip
"$PYTHON" -m pip install -q -e ".[dev]"
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

if claude --version &>/dev/null 2>&1; then
    echo "✓ Claude Code available ($(claude --version 2>/dev/null))"
else
    echo "⚠ Claude Code not found in PATH. Install or restart terminal:"
    echo "    curl -fsSL https://claude.ai/install.sh | bash"
    echo "    export PATH=\"\$HOME/.claude/bin:\$PATH\""
fi

echo ""
if [ $FAIL -eq 0 ]; then
    echo "══════════════════════════════════════════"
    echo "  ✅ Setup complete! All checks passed."
    echo ""
    echo "  Start Ms. Ja:"
    echo "    1. ./scripts/start_web.sh"
    echo "    2. Open http://127.0.0.1:3000"
    echo "    3. Launch claude from web terminal"
    echo "══════════════════════════════════════════"
else
    echo "⚠️  Setup finished with errors. Check above."
fi
echo ""
