
# 16_codex/agents/TOOL_PROFILES/claude.md
# Claude AI Tool Profile

This document outlines the specific configuration and operational guidelines for using the Claude AI tool within the SSID agent stack.

## Integration Details

-   **Wrapper Script:** `12_tooling/wrappers/claude_run.sh`
-   **Invocation:** All calls to Claude must be routed through `12_tooling/cli/ssid_dispatcher.py` to ensure sandbox isolation, write-gate enforcement, and full gate chain validation.
-   **API Endpoint:** Configured internally within the `claude_run.sh` script or an underlying library.
-   **Authentication:** API key management is handled securely via environment variables or a secrets manager, not directly in this profile.

## Usage Guidelines

-   **Purpose:** Claude is primarily used for tasks requiring advanced natural language understanding, creative content generation, and sophisticated code refactoring suggestions.
-   **Input/Output:**
    -   **Input:** Task descriptions, code snippets, documentation requirements.
    -   **Output:** Proposed code changes (as text or structured data), documentation drafts, refactoring plans.
-   **Patch-Only:** Claude's output is interpreted as a proposed change that will be transformed into a patch within the sandbox. It does not have direct write access to the main repository.

## Constraints and Limitations

-   **Rate Limits:** Adherence to Claude API rate limits is managed by the wrapper and dispatcher.
-   **Context Window:** Ensure task prompts and relevant code context fit within Claude's maximum context window. Long inputs may require summarization or iterative processing.
-   **Safety and Bias:** Outputs are subject to post-processing and human review to mitigate potential biases or safety concerns.

## Environment Variables (Example)

-   `CLAUDE_API_KEY`: Secret API key for authentication.
-   `CLAUDE_MODEL`: (Optional) Specifies a particular Claude model version (e.g., `claude-3-opus-20240229`).

## Recommended Workflows

1.  **Code Refactoring:** Feed a code module to Claude with a refactoring goal (e.g., "improve readability," "extract common logic").
2.  **Documentation Generation:** Provide code and ask Claude to generate docstrings, README sections, or high-level architectural descriptions.
3.  **Complex Logic Design:** Outline a feature requirement and request Claude to propose design patterns or pseudo-code.
