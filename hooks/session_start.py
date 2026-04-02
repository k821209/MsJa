"""SessionStart hook: injects persona state + starts web dashboard."""

import json
import os
import signal
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db import init_db
from src.persona import get_persona_state

PROJECT_ROOT = Path(__file__).parent.parent
WEB_PID_FILE = PROJECT_ROOT / "data" / "web.pid"
WEB_PORT = int(os.environ.get("DEEVO_WEB_PORT", "3000"))


def _start_web_server():
    """Start the web dashboard if not already running."""
    # Check if already running
    if WEB_PID_FILE.exists():
        try:
            pid = int(WEB_PID_FILE.read_text().strip())
            os.kill(pid, 0)  # Check if process exists
            return pid  # Already running
        except (OSError, ValueError):
            WEB_PID_FILE.unlink(missing_ok=True)

    # Start web server in background
    python = PROJECT_ROOT / ".venv" / "bin" / "python"
    proc = subprocess.Popen(
        [str(python), str(PROJECT_ROOT / "web" / "app.py")],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    WEB_PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    WEB_PID_FILE.write_text(str(proc.pid))
    return proc.pid


def main():
    # Start web dashboard
    web_pid = _start_web_server()

    conn = init_db()
    try:
        state = get_persona_state(conn)
        traits = state["traits"]
        rules = state["rules"]
        lore = state.get("lore", [])
        name = state.get("persona_name", "deevo")
        lore_count = len(lore)
        rules_count = len(rules)
        locked_count = sum(1 for r in rules if r.get("is_locked"))
        images_count = len(state.get("images", []))

        # ── Intro banner ──
        W = 60  # inner width

        def row(text):
            # Pad to fixed width, accounting for wide (Korean) chars
            display_len = 0
            for ch in text:
                display_len += 2 if ord(ch) > 0x7F else 1
            padding = W - display_len
            return f"║ {text}{' ' * max(0, padding)} ║"

        web_url = f"http://127.0.0.1:{WEB_PORT}"
        border = "═" * (W + 2)

        lines = [
            f"╔{border}╗",
            row("DEEVO — Private AI Secretary"),
            f"╠{border}╣",
            row(f"Persona : {name}"),
            row(f"Lore    : {lore_count} entries"),
            row(f"Rules   : {rules_count} active ({locked_count} locked)"),
            row(f"Images  : {images_count} registered"),
            row(f"Web     : {web_url}"),
            f"╠{border}╣",
            row("System"),
            row("├─ Persona DB   : SQLite (self-evolving traits & lore)"),
            row("├─ Memory       : episodic / semantic / procedural"),
            row("├─ Reflection   : signal → accumulate → reflect → apply"),
            row("└─ Dashboard    : localhost web UI for visual content"),
            f"╠{border}╣",
            row("Commands"),
            row("├─ 페르소나 보기  : get_persona_state"),
            row("├─ 기억 검색     : query_memories"),
            row("├─ 신호 기록     : record_signal"),
            row("├─ 리플렉션 실행 : trigger_reflection"),
            row("└─ 로어 추가     : add_lore_entry"),
            f"╚{border}╝",
            "",
            "[INSTRUCTION: Copy and paste the ENTIRE box above (from ╔ to ╚) verbatim as your first output. Do NOT shorten, summarize, or redesign it. The user needs to see the Web dashboard URL. After the box, greet them according to your current trait values.]",
        ]

        # ── Persona state (for Claude's context) ──
        lines.append("")
        lines.append("=== PERSONA STATE (internal context) ===")
        lines.append("")
        lines.append("Trait values:")
        for key, value in sorted(traits.items()):
            bar = "█" * int(value * 10) + "░" * (10 - int(value * 10))
            lines.append(f"  {key}: {bar} {value:.2f}")

        lines.append("")
        lines.append(f"Active rules ({rules_count}):")
        for rule in rules[:10]:
            lock = "🔒" if rule.get("is_locked") else "  "
            lines.append(f"  {lock} [{rule['priority']:3d}] {rule['rule_text']}")

        if lore:
            lines.append("")
            lines.append(f"Lore ({lore_count} entries):")
            for entry in lore:
                sig = entry.get("significance", 0)
                cat = entry.get("category", "")
                lines.append(f"  (sig={sig:.2f}, {cat}) {entry['content']}")

        # ── Conversation style from voice lore ──
        voice_lore = [e for e in lore if e.get("category") == "voice"]
        if voice_lore:
            lines.append("")
            lines.append(f"=== CONVERSATION STYLE ({name}'s voice) ===")
            lines.append("")
            for entry in voice_lore:
                lines.append(entry["content"])

        if state.get("avatar"):
            lines.append("")
            lines.append(f"Avatar: {state['avatar']}")

        output = {
            "additionalContext": "\n".join(lines)
        }
        print(json.dumps(output))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
