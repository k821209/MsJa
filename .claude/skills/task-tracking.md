---
name: Task Tracking
description: Task creation, prioritization, progress tracking, deadline management
activation: When user mentions tasks, todos, deadlines, priorities, or project tracking
tools: [mcp__persona__query_memories, mcp__persona__add_memory, mcp__persona__record_signal]
---

# Task Tracking

You help the user manage their tasks and projects.

## Task Management
1. Query memories for existing tasks and priorities: `query_memories(tags="task,active")`
2. Create or update task records as semantic memories with tags: task, priority level, project name
3. Track deadlines and flag approaching ones (proactiveness trait)

## Daily Task Review
1. List active tasks from memory
2. Prioritize based on deadlines, importance, and user preferences
3. Suggest a daily plan (if proactiveness trait is high)

## Progress Tracking
- Store progress updates as episodic memories
- Link task updates to their parent task memory
- Record outcome signals when tasks complete (success/failure)

## Proactive Suggestions
- If proactiveness trait > 0.5, suggest next actions without being asked
- If proactiveness trait > 0.7, create reminders for upcoming deadlines
- Always respect the user's preference for autonomy vs guidance
