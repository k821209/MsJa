"""SessionStart hook: injects current persona state into Claude's context."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db import init_db
from src.persona import get_persona_state


def main():
    conn = init_db()
    try:
        state = get_persona_state(conn)
        traits = state["traits"]
        rules = state["rules"]

        lines = [
            f"[Persona: {state['persona_name']}]",
            "",
            "Current trait values:",
        ]
        for key, value in sorted(traits.items()):
            bar = "█" * int(value * 10) + "░" * (10 - int(value * 10))
            lines.append(f"  {key}: {bar} {value:.2f}")

        lines.append("")
        lines.append(f"Active rules ({len(rules)}):")
        for rule in rules[:10]:
            lock = "🔒" if rule.get("is_locked") else "  "
            lines.append(f"  {lock} [{rule['priority']:3d}] {rule['rule_text']}")

        output = {
            "additionalContext": "\n".join(lines)
        }
        print(json.dumps(output))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
