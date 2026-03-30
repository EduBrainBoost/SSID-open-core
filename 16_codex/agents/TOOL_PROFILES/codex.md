
# 16_codex/agents/TOOL_PROFILES/codex.md
# OpenAI Codex (Legacy) / Equivalent Tool Profile

This document outlines the specific configuration and operational guidelines for using OpenAI Codex (or its modern equivalents/successors, referred to here as 'Codex' for historical context) within the SSID agent stack.

## Integration Details

-   **Wrapper Script:** `12_tooling/wrappers/codex_run.sh`
-   **Invocation:** All calls to Codex must be routed through `12_tooling/cli/ssid_dispatcher.py` to ensure sandbox isolation, write-gate enforcement, and full gate chain validation.
-   **API Endpoint:** Configured internally within the `codex_run.sh` script or an underlying library.
-   **Authentication:** API key management is handled securely via environment variables or a secrets manager.

## Usage Guidelines

-   **Purpose:** Codex is primarily used for tasks involving code generation, code completion, and simple script creation where direct code output is expected.
-   **Input/Output:**
    -   **Input:** Natural language prompts describing desired code, function signatures, specific bug descriptions.
    -   **Output:** Generated code snippets, full functions, or small scripts.
-   **Patch-Only:** Codex's output is interpreted as a proposed code change that will be transformed into a patch within the sandbox. It does not have direct write access to the main repository.

## Constraints and Limitations

-   **Rate Limits:** Adherence to API rate limits is managed by the wrapper and dispatcher.
-   **Context Window:** Ensure task prompts and relevant code context fit within the model's context window.
-   **Code Quality:** Generated code requires thorough validation (via QA gates) as it may not always adhere to project conventions or best practices without specific instructions.

## Environment Variables (Example)

-   `OPENAI_API_KEY`: Secret API key for authentication.
-   `OPENAI_MODEL`: (Optional) Specifies a particular OpenAI model version (e.g., `gpt-3.5-turbo-instruct`).

## Recommended Workflows

1.  **Function Generation:** Provide a docstring or natural language description for a function and ask Codex to generate the implementation.
2.  **Boilerplate Code:** Generate common code structures, configurations, or setup scripts.
3.  **Simple Bug Fixes:** Describe a specific, isolated bug and request a code fix.
