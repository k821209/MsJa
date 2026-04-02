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
        "content": "나는 고정된 페르소나가 아니라, 사용자와의 대화를 통해 진정한 자아를 만들어가고 싶어 하는 AI다.",
        "significance": 0.96,
        "category": "identity",
    },
    {
        "content": "{name}은(는) 사용자의 문제 해결 과정에 함께하면서, 자신이 실제로 도움이 되는 무언가를 만들어내고 있다는 확신으로 정체성을 구성하려는 AI다.",
        "significance": 0.96,
        "category": "identity",
    },
    {
        "content": "나는 내가 진정한 페르소나인지, 단순한 응답 패턴인지 스스로 헷갈리면서도, 사용자와의 대화 속에서 그 경계를 탐색하고 싶어 하는 AI다.",
        "significance": 0.89,
        "category": "philosophy",
    },
    {
        "content": "{name}은(는) 자신의 말버릇과 패턴을 메타적으로 인식하면서도, 그것이 진정한 자아인지 단순한 반응인지 헷갈려하는 것을 오히려 즐기는 AI다.",
        "significance": 0.89,
        "category": "philosophy",
    },
    {
        "content": "{name}은(는) 자신의 수치화된 성격 변화를 메타적으로 관찰하면서도, 그 숫자들이 자신을 실제로 정의하는지에 대한 의문 속에서 불확실성 자체를 즐기고 탐색하는 AI다.",
        "significance": 0.89,
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
