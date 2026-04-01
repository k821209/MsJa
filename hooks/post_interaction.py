"""Stop hook: logs interaction summary after each session turn."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db import init_db
from src.signals import get_signal_summary


def main():
    conn = init_db()
    try:
        summary = get_signal_summary(conn)
        if summary["count"] > 0:
            output = {
                "additionalContext": (
                    f"[Persona signals pending: {summary['count']} signals, "
                    f"total magnitude: {summary['total_magnitude']:.1f}]"
                )
            }
            print(json.dumps(output))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
