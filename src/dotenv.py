"""Simple .env file reader/writer — no external dependencies."""

from __future__ import annotations

from pathlib import Path

ENV_PATH = Path(__file__).parent.parent / ".env"


def load_env() -> dict[str, str]:
    """Load key=value pairs from .env file."""
    env: dict[str, str] = {}
    if not ENV_PATH.exists():
        return env
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        # Strip surrounding quotes
        value = value.strip().strip("'\"")
        env[key.strip()] = value
    return env


def save_env_key(key: str, value: str) -> None:
    """Set a single key in the .env file, preserving other entries."""
    env = load_env()
    if value:
        env[key] = value
    else:
        env.pop(key, None)

    lines = []
    for k, v in sorted(env.items()):
        lines.append(f"{k}={v}")
    ENV_PATH.write_text("\n".join(lines) + "\n" if lines else "")


def get_env_keys() -> dict[str, str]:
    """Return all keys from .env."""
    return load_env()
