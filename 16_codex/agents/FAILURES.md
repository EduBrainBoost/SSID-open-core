
# FAILURES.md
# Agent Stack Failure Log (Append-Only)

This document serves as an append-only log for significant failures encountered by the agent stack, including instances where agents failed to produce a valid patch, introduced critical bugs, or violated core governance rules.

Each entry should provide a concise summary of the failure, its detected cause, and any remedial actions taken or lessons learned. This log aids in improving agent reliability, refining policies, and enhancing the overall robustness of the system.

---

**Failure Log Entries:**

## [YYYY-MM-DD] - [Brief Title of Failure]

**Task ID:** `[If applicable, e.g., task-uuid-xxxx]`
**Agent/Tool Involved:** `[e.g., Gemini CLI, Claude, Human-in-the-Loop]`
**Failure Type:** `[e.g., Policy Violation, SoT Violation, Runtime Error, Incorrect Patch]`
**Description:**
`[Detailed description of what went wrong, including observed behavior and deviations from expected outcome. Mention the specific gate that failed if applicable (e.g., "Write-Gate failed: attempted to modify disallowed_path").]`

**Root Cause Analysis:**
`[Explain why the failure occurred. Was it an agent misinterpretation? A bug in the agent's code? An incomplete task specification? A flaw in a policy?]`

**Impact:**
`[What was the consequence of this failure? (e.g., "Blocked deployment of feature X", "Required manual rollback", "Caused a build break").]`

**Remedial Actions / Lessons Learned:**
`[What was done to address this specific failure? What changes were made to agents, policies, tools, or workflows to prevent recurrence?]`

---
