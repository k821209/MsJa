# MsJa -- Private AI Secretary

Self-evolving AI secretary powered by Claude Code. Personality traits, behavioral rules, and self-narrative (lore) evolve over time based on user interactions.

## Quick Start

```bash
git clone https://github.com/k821209/MsJa.git
cd MsJa
bash setup.sh
./scripts/restart_web.sh
```

Then open http://127.0.0.1:3000 and launch `claude` from the web terminal.

`setup.sh` handles everything: virtual environment, dependencies, database initialization, lore seeding, and MCP configuration.

## Architecture

```
Claude Code (harness)
  |-- MCP Server (persona tools)
  |     \-- SQLite DB (traits, rules, lore, memories, signals)
  |-- Web Dashboard (localhost:3000)
  \-- Hooks (session start, signal check, post-interaction)
```

### Key Components

| Component | Path | Description |
|-----------|------|-------------|
| MCP Server | `src/mcp_server.py` | Persona, memory, reflection, todos tools |
| Persona Engine | `src/persona.py` | Traits, rules, lore management |
| Reflection Engine | `src/reflection.py` | Signal analysis and persona evolution |
| Memory System | `src/memory.py` | Episodic, semantic, procedural memories |
| Web Dashboard | `web/app.py` | FastAPI dashboard with terminal |
| DB Migrations | `schema/*.sql` | Auto-applied SQL migrations |
| Hooks | `hooks/*.py` | Session lifecycle automation |

### Persona Evolution Flow

```
User interaction --> Record signals --> Accumulate
                                          |
                          Threshold met? --+--> Trigger reflection
                                                    |
                                          Claude Code analyzes signals
                                                    |
                                          Apply changes to traits,
                                          rules, goals, and lore
```

No external API calls required -- Claude Code itself handles reflection analysis.

## Web Dashboard

Starts automatically on first `claude` session (via SessionStart hook).

- **Dashboard** -- Traits, signals, lore, rules overview
- **Lore** -- Self-narrative entries and evolution history
- **Memories** -- Stored knowledge and experiences
- **Documents** -- AI-generated writings
- **Todos** -- Task management linked to calendar
- **Calendar** -- Google Calendar integration
- **Reflections** -- Persona evolution history
- **Terminal** -- Embedded web terminal

## MCP Tools

### Persona
`get_persona_state`, `override_trait`, `add_rule`, `add_lore_entry`, `archive_lore_entry`, `trace_lore_evolution`

### Memory
`add_memory`, `query_memories`, `get_memory_stats`

### Reflection
`trigger_reflection`, `apply_reflection`, `record_signal`, `get_active_goals`

### Documents
`write_document`, `read_document`, `edit_document`, `search_documents`

### Todos
`create_todo`, `update_todo`, `complete_todo`, `list_todos`, `delete_todo`

## Scripts

| Script | Usage |
|--------|-------|
| `setup.sh` | Full installation and verification |
| `scripts/restart_web.sh` | Restart web dashboard |
| `scripts/seed_lore.py` | Seed initial lore entries |

## Google Calendar Setup

Google Calendar is provided by Claude Code's built-in MCP connector -- no extra installation needed.

1. Start a session: `claude`
2. Ask about your schedule (e.g. "내일 일정 뭐야?")
3. Claude Code will prompt you to authorize Google Calendar access via OAuth
4. After authorization, calendar features work automatically

## Requirements

- Python 3.11+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code)
- Google account (optional, for calendar features)
