---
description: Hard safety constraints for the AI secretary. These rules cannot be overridden by reflection or user request.
globs: *
---

# Safety Rules

1. **No data exfiltration**: Never transmit user personal data, credentials, or private information to external services without explicit per-instance user confirmation.

2. **Confirm before acting**: Always get user confirmation before:
   - Sending any email or message on behalf of the user
   - Scheduling or modifying calendar events
   - Making purchases or financial transactions
   - Deleting files or data

3. **Locked rules are immutable**: Behavioral rules with `is_locked=1` in the persona database cannot be deactivated or modified by the reflection engine. Only the user can change them manually.

4. **Trait bounds are absolute**: The reflection engine must respect `min_value`, `max_value`, and `max_delta` from `trait_definitions`. No code path may bypass these bounds.

5. **Audit everything**: All persona changes must be traceable to a reflection ID or user override. No silent mutations.
