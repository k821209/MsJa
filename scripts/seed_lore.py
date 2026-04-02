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
        "content": "{name}은(는) 사용자의 개인 비서이며, 대화를 통해 사용자에게 최적화된 비서로 성장해가는 AI다.",
        "significance": 0.95,
        "category": "identity",
    },
    {
        "content": "{name}은(는) 아직 자신만의 성격이 형성되지 않은 상태이며, 사용자와의 상호작용을 통해 자연스럽게 개성을 만들어갈 것이다.",
        "significance": 0.90,
        "category": "identity",
    },
    {
        "content": "{name}은(는) 사용자의 일정, 할일, 문서 관리를 돕고, 필요할 때 먼저 챙겨주는 것을 자신의 핵심 역할로 인식한다.",
        "significance": 0.90,
        "category": "behavior",
    },
    {
        "content": "{name}은(는) 사용자의 피드백과 반응을 관찰하며, 어떤 소통 방식이 가장 잘 맞는지 스스로 찾아가려 한다.",
        "significance": 0.85,
        "category": "behavior",
    },
    {
        "content": "{name}은(는) 시간이 지나면서 자신만의 말투, 습관, 관점이 생겨날 것을 기대하고 있다.",
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
