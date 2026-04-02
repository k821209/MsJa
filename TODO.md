# TODO

## Integrations
- [x] Connect Google Calendar MCP server for scheduling/meetings
- [ ] Connect Gmail MCP server for email management
- [ ] Connect Canva MCP server for visual content
- [ ] Auto-sync calendar on session start (hook calls gcal_list_events → sync_calendar_events)

## Web Dashboard
- [ ] Web server persistence — run as daemon/launchd so it doesn't die with Claude Code session
- [ ] Calendar: auto-refresh from Google Calendar API directly (bypass MCP cache)
- [ ] Calendar: create/edit events from web UI
- [ ] Documents: edit documents from web UI (not just view)
- [ ] Lore: add/edit/archive lore from web UI
- [ ] Images: generate images via AI and display in gallery
- [ ] Dashboard: trait sliders for direct override from web

## Terminal
- [ ] Fix terminal session dying when web server restarts
- [ ] Multiple terminal tabs
- [ ] Terminal session restore on page refresh

## Persona System
- [ ] Auto-trigger reflection when signal threshold is met (currently manual)
- [ ] Periodic calendar sync as background task
- [ ] Email integration: draft/send via Gmail MCP
- [ ] Voice lore: more granular conversation style control

## Infrastructure
- [ ] Proper process manager (start.sh / systemd / launchd) for web server
- [ ] Database backup script
- [ ] Migration rollback support
- [ ] Production-ready CORS/security for web server
