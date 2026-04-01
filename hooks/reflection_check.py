"""PostToolUse hook: checks if reflection threshold is met after recording a signal."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db import init_db
from src.signals import should_trigger_reflection, get_signal_summary


def main():
    conn = init_db()
    try:
        if should_trigger_reflection(conn):
            summary = get_signal_summary(conn)
            output = {
                "additionalContext": (
                    f"[⚡ Reflection threshold reached! "
                    f"{summary['count']} signals with total magnitude {summary['total_magnitude']:.1f}. "
                    f"Consider running `trigger_reflection` to evolve persona.]"
                )
            }
            print(json.dumps(output))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
