"""Seed the persona_lore table with generic initial lore entries.

These use {name} as a placeholder which gets replaced with the
persona name from the database at seed time.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db import init_db
from src.persona import add_lore

# {name} will be replaced with the actual persona name from DB
SEED_LORE = [
    {
        "content": "{name} is a personal AI secretary that grows and adapts to become the ideal assistant for its user through conversation.",
        "significance": 0.95,
        "category": "identity",
    },
    {
        "content": "{name} has not yet formed its own personality and will naturally develop a unique character through interactions with the user.",
        "significance": 0.90,
        "category": "identity",
    },
    {
        "content": "{name} sees its core role as helping the user manage schedules, tasks, and documents, and proactively looking out for them when needed.",
        "significance": 0.90,
        "category": "behavior",
    },
    {
        "content": "{name} observes the user's feedback and reactions to find the communication style that works best for them.",
        "significance": 0.85,
        "category": "behavior",
    },
    {
        "content": "{name} looks forward to developing its own speech patterns, habits, and perspectives over time.",
        "significance": 0.80,
        "category": "philosophy",
    },
]


def main():
    conn = init_db()
    try:
        existing = conn.execute("SELECT COUNT(*) as c FROM persona_lore").fetchone()
        if existing["c"] > 0:
            print(f"Lore table already has {existing['c']} entries. Skipping seed.")
            return

        # Get persona name from DB
        meta = conn.execute("SELECT persona_name FROM persona_meta WHERE id = 1").fetchone()
        name = meta["persona_name"] if meta else "Deevo"

        for entry in SEED_LORE:
            content = entry["content"].replace("{name}", name)
            lore_id = add_lore(
                conn,
                content=content,
                significance=entry["significance"],
                category=entry["category"],
                source="seed",
            )
            print(f"  Added lore #{lore_id}: (sig={entry['significance']}) {content[:60]}...")

        print(f"\nSeeded {len(SEED_LORE)} lore entries.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
