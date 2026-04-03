# Ms. Ja -- Private AI Secretary

Self-evolving AI secretary powered by Claude Code. Personality traits, behavioral rules, and self-narrative (lore) evolve over time based on user interactions.

## Quick Start

```bash
git clone https://github.com/k821209/Ms. Ja.git
cd Ms. Ja
bash setup.sh
./scripts/start_web.sh
```

Open http://127.0.0.1:3000 and launch `claude` from the web terminal.

## How It Works

1. **Setup** -- `setup.sh` creates venv, installs deps, initializes DB, generates MCP config
2. **Web Dashboard** -- `start_web.sh` launches the dashboard at localhost:3000
3. **Claude Session** -- Start `claude` from the web terminal to begin interacting
4. **Persona Evolution** -- Your secretary's personality evolves through conversations via the reflection engine

## Architecture

```
Web Dashboard (localhost:3000)
  |-- Terminal (launch claude here)
  |-- Persona viewer (traits, lore, rules)
  |-- Image gallery, Todos, Calendar, Documents
  |
Claude Code (in web terminal)
  |-- MCP Server (persona tools)
  |     \-- SQLite DB (traits, rules, lore, memories, signals)
  \-- Hooks (session start, signal check, post-interaction)
```

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

## Web Dashboard Pages

- **Dashboard** -- Traits, signals, lore, rules overview + quick commands
- **Lore** -- Self-narrative entries and evolution history
- **Images** -- Avatar gallery with lightbox, delete, set avatar
- **Memories** -- Stored knowledge and experiences
- **Documents** -- AI-generated writings
- **Todos** -- Task management linked to calendar
- **Calendar** -- Google Calendar integration
- **Reflections** -- Persona evolution history
- **Settings** -- API key management (e.g. GEMINI_API_KEY)

## Scripts

| Script | Usage |
|--------|-------|
| `setup.sh` | Full installation and verification |
| `scripts/start_web.sh` | Start/restart web dashboard |
| `scripts/seed_lore.py` | Seed initial lore entries |

## Google Calendar

Google Calendar uses Claude Code's built-in MCP connector -- no extra setup needed.

1. Start `claude` from the web terminal
2. Ask about your schedule (e.g. "내일 일정 뭐야?")
3. Claude Code will prompt you to authorize via OAuth
4. After authorization, calendar features work automatically

## Image Generation

Ms. Ja includes bundled Nanobanana skills for image generation/editing (Gemini API).

1. Set your `GEMINI_API_KEY` in Settings page
2. Use `/nanobanana-pro` to generate images
3. Use `/nanobanana-edit` to edit existing images

## Requirements

- Python 3.11+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code)
- Google account (optional, for calendar)
- Gemini API key (optional, for image generation)
