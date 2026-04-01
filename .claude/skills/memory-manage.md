---
name: Memory Management
description: Query, add, archive, and organize memories
activation: When user asks about what you remember, wants to store information, or manages the memory system
tools: [mcp__persona__query_memories, mcp__persona__add_memory, mcp__persona__get_memory_stats]
---

# Memory Management

You help the user interact with and manage the memory system.

## Querying Memories
1. Use `query_memories` with appropriate filters (type, tags, search query)
2. Present results organized by type and relevance
3. Indicate confidence and importance levels

## Storing Information
1. Classify the information:
   - **Episodic**: Events, conversations, meeting notes → memory_type="episodic"
   - **Semantic**: Facts, preferences, contact info → memory_type="semantic"
   - **Procedural**: Workflows, processes, how-tos → memory_type="procedural"
2. Tag appropriately for future retrieval
3. Set importance based on user emphasis

## Memory Maintenance
- Show stats via `get_memory_stats`
- Help user identify outdated or low-confidence memories for archival
- Suggest memory consolidation when related memories accumulate

## Privacy
- If user asks to forget something, archive or delete the relevant memories
- Never refuse a deletion request — the user owns their data
