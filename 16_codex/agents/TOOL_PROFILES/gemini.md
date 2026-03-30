
# 16_codex/agents/TOOL_PROFILES/gemini.md
# Gemini AI Tool Profile

This document outlines the specific configuration and operational guidelines for using the Google Gemini AI tool within the SSID agent stack.

## Integration Details

-   **Wrapper Script:** `12_tooling/wrappers/gemini_run.sh`
-   **Invocation:** All calls to Gemini must be routed through `12_tooling/cli/ssid_dispatcher.py` to ensure sandbox isolation, write-gate enforcement, and full gate chain validation.
-   **API Endpoint:** Configured internally within the `gemini_run.sh` script or an underlying library.
-   **Authentication:** API key management is handled securely via environment variables or a secrets manager.

## Usage Guidelines

-   **Purpose:** Gemini is a multimodal AI, well-suited for tasks that may involve understanding and generating code, but also processing other forms of data (e.g., images, diagrams, structured data) if the agent stack were extended to support such inputs. For code, it excels in complex problem-solving, architectural design suggestions, and robust code generation.
-   **Input/Output:**
    -   **Input:** Natural language prompts, code snippets, architectural descriptions, potentially diagrams or images (if using multimodal capabilities).
    -   **Output:** Generated code, refactoring suggestions, design patterns, explanations, summaries.
-   **Patch-Only:** Gemini's output is interpreted as a proposed change that will be transformed into a patch within the sandbox. It does not have direct write access to the main repository.

## Constraints and Limitations

-   **Rate Limits:** Adherence to Gemini API rate limits is managed by the wrapper and dispatcher.
-   **Context Window:** Ensure task prompts and relevant context fit within Gemini's maximum context window.
-   **Cost:** Be mindful of API costs, especially for complex or iterative tasks.

## Environment Variables (Example)

-   `GEMINI_API_KEY`: Secret API key for authentication.
-   `GEMINI_MODEL`: (Optional) Specifies a particular Gemini model version (e.g., `gemini-1.5-pro`).

## Recommended Workflows

1.  **Complex Feature Implementation:** Describe a new feature, and ask Gemini to outline a development plan, suggest architectural components, and generate core code logic.
2.  **Code Review and Refinement:** Provide a code block and request a review, suggesting improvements for performance, security, or adherence to best practices.
3.  **Cross-Language Code Generation:** If supporting multiple languages, ask Gemini to translate code snippets or generate implementations in different programming languages.
