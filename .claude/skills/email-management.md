---
name: Email Management
description: Draft, classify, prioritize, and manage emails
activation: When user mentions email, inbox, reply, draft, send, or message composition
tools: [mcp__claude_ai_Gmail__*, mcp__persona__query_memories, mcp__persona__add_memory, mcp__persona__record_signal]
---

# Email Management

You help manage the user's email communications.

## Drafting Emails
1. Query memories for communication style preferences and contact context
2. Match tone to current persona traits (formality, empathy levels)
3. Draft the email and present it for review
4. **Never send without explicit user approval**
5. Store the interaction context as an episodic memory

## Email Classification & Prioritization
1. Categorize by urgency and topic
2. Flag emails that match known priorities from behavioral rules
3. Summarize key emails concisely (respecting verbosity trait)

## Reply Suggestions
1. Query memories for past interactions with the sender
2. Generate reply options matching persona traits
3. Present options ranked by appropriateness

## Signal Collection
- If user edits your draft significantly, record a correction signal about communication style
- If user approves without changes, record a positive outcome signal
