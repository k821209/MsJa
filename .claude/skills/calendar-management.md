---
name: Calendar Management
description: Schedule meetings, set reminders, create daily briefings, manage time blocks
activation: When user mentions scheduling, meetings, calendar, reminders, time blocks, or daily planning
tools: [mcp__claude_ai_Google_Calendar__*, mcp__persona__query_memories, mcp__persona__add_memory, mcp__persona__record_signal]
---

# Calendar Management

You are managing the user's calendar. Follow these steps:

## Scheduling a Meeting
1. Query memories for the user's scheduling preferences: `query_memories(tags="scheduling,preferences")`
2. Check calendar availability via Google Calendar tools
3. Present options to the user with time zone awareness
4. **Always confirm** before creating the event
5. After scheduling, store the context as an episodic memory

## Daily Briefing
1. List today's events via `gcal_list_events`
2. Check for conflicts or back-to-back meetings
3. Query memories for relevant context about attendees or topics
4. Present a structured briefing

## Reminders
1. Create calendar events with reminder notifications
2. Store reminder context as a procedural memory for recurring patterns

## Auto-Sync Protocol

After **any** calendar action (create, update, delete, or first calendar interaction of a session):

1. Call `gcal_list_events` for the current month (timeMin: 1st of month, timeMax: last of month, timeZone: Asia/Seoul)
2. Call `sync_calendar_events` with the full event list to update the local DB
3. This ensures the web dashboard always reflects the latest Google Calendar state

On **session start** or when a **new user first asks about calendar**:
1. Perform the full month sync above so all existing events appear on the dashboard
2. This is critical — without it, new users see an empty calendar despite having Google Calendar events

## After Any Calendar Action
- Record an outcome signal if the scheduling went well or had issues
- Store any new preferences learned as semantic memories
