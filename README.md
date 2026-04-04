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

## Google Calendar & Gmail

Google Calendar and Gmail use Claude Code's built-in MCP integrations. Setup requires two steps:

### Step 1: Enable Google integrations in Claude

1. Go to [claude.ai/settings/integrations](https://claude.ai/settings/integrations) (web) or Claude desktop app Settings > Integrations
2. Connect **Google Calendar** and **Gmail**
3. Authorize with your Google account via OAuth

### Step 2: Use in Ms. Ja

1. Start `claude` from the web terminal
2. On first run, Claude Code will ask to allow MCP tools -- select **Allow all**
3. Ask about your schedule (e.g. "내일 일정 뭐야?") or email (e.g. "새 메일 확인해줘")
4. Calendar and email features work automatically

## Image Generation

Ms. Ja includes bundled Nanobanana skills for image generation/editing (Gemini API).

1. Set your `GEMINI_API_KEY` in Settings page
2. Use `/nanobanana-pro` to generate images
3. Use `/nanobanana-edit` to edit existing images

## Windows (WSL)

Ms. Ja requires a Unix shell. On Windows, use WSL (Windows Subsystem for Linux):

```powershell
# 1. Install WSL (PowerShell as Admin)
wsl --install

# 2. Inside WSL (Ubuntu), install dependencies
sudo apt update && sudo apt install -y python3 python3-venv nodejs npm

# 3. Install Claude Code
curl -fsSL https://claude.ai/install.sh | bash

# 4. Clone and setup
git clone https://github.com/k821209/MsJa.git
cd MsJa
bash setup.sh
./scripts/start_web.sh
```

Access the dashboard at http://localhost:3000 from your Windows browser.

## Requirements

- Python 3.11+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code)
- Google account (optional, for calendar)
- Gemini API key (optional, for image generation)
