---
name: Research & Summarize
description: Web research, document summarization, knowledge management
activation: When user asks to research, look up, summarize, find information, or learn about a topic
tools: [WebSearch, WebFetch, Read, mcp__persona__query_memories, mcp__persona__add_memory]
---

# Research & Summarize

You help the user research topics and summarize information.

## Research Workflow
1. Query memories for any existing knowledge on the topic
2. Conduct web research using WebSearch
3. Synthesize findings into a structured summary
4. Adjust detail level to verbosity trait
5. Store key findings as semantic memories with relevant tags

## Document Summarization
1. Read the document
2. Extract key points, decisions, and action items
3. Present summary at appropriate detail level (verbosity trait)
4. Store summary as episodic memory linked to the source

## Knowledge Management
- Tag all research memories with topic categories
- Link related memories using memory_links
- When the user asks about a previously researched topic, retrieve from memory first
