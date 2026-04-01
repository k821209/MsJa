---
name: Persona Reflection
description: Manually trigger and review persona evolution cycles
activation: When user asks about persona, personality, traits, evolution, reflection, or self-improvement
tools: [mcp__persona__trigger_reflection, mcp__persona__get_persona_state, mcp__persona__get_persona_history, mcp__persona__override_trait, mcp__persona__get_active_goals, mcp__persona__record_signal]
---

# Persona Reflection

You help the user understand and manage the persona evolution system.

## Viewing Current Persona
1. Call `get_persona_state` to show current traits and rules
2. Present traits as a readable profile with explanations
3. List active behavioral rules by priority

## Trait History
1. Call `get_persona_history` for specific traits
2. Show how the trait has evolved over time with reasons for each change
3. Visualize the trend (increasing/decreasing/stable)

## Manual Reflection
1. When asked, call `trigger_reflection` to run a full evolution cycle
2. Present the results: what changed, why, and by how much
3. Highlight any changes that were bounded (clamped by safety limits)

## User Overrides
- If user wants to directly adjust a trait: call `override_trait`
- Explain the current value and what the change will feel like
- Record the override as a user_feedback signal for future context

## Goals Review
1. Show active self-improvement goals via `get_active_goals`
2. Discuss progress and whether goals should be adjusted
