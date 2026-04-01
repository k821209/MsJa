#!/usr/bin/env bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
PYTHON="$VENV_DIR/bin/python"

echo "=== Deevo AI Secretary Setup ==="
echo "Project: $PROJECT_DIR"
echo ""

# 1. Create venv
if [ ! -d "$VENV_DIR" ]; then
    echo "[1/4] Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
else
    echo "[1/4] Virtual environment already exists."
fi

# 2. Install dependencies
echo "[2/4] Installing dependencies..."
"$VENV_DIR/bin/pip" install -q --upgrade pip
"$VENV_DIR/bin/pip" install -q -e ".[dev]"

# 3. Initialize database
echo "[3/4] Initializing persona database..."
"$PYTHON" -c "from src.db import init_db; init_db()"

# 4. Generate .mcp.json with absolute paths for this machine
echo "[4/4] Generating .mcp.json..."
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

echo ""
echo "=== Setup complete! ==="
echo ""
echo "To start Deevo, run:"
echo "  cd $PROJECT_DIR"
echo "  claude"
