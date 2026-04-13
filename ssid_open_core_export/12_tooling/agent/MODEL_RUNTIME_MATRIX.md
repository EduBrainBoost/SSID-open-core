# Model Runtime Matrix

Supported models for the SSID Local LLM Agent Stack.

| Model | Size | CPU-Suitable | Quality | Use Case |
|---|---|---|---|---|
| qwen2.5-coder:7b | 7B | Yes (slow) | Good | Primary — general coding tasks, code review, analysis |
| Qwen3-4B (Claude distill) | 4B | Yes | Experimental | Experimental — smaller footprint, faster inference |
| deepseek-coder:6.7b | 6.7B | Yes (slow) | Good | Alternative — strong on code completion |

## Runtime Modes

- **Standalone (Primary)**: Ollama runs directly. `ollama run qwen2.5-coder:7b "prompt"`
- **Docker / LiteLLM (Secondary)**: LiteLLM proxy on `localhost:4000`, routes to Ollama or other backends.

## Selection

Set the model via environment variable:

```bash
export SSID_LLM_MODEL="qwen2.5-coder:7b"
```

The agent CLI tries LiteLLM first (`localhost:4000`), then falls back to direct `ollama run`.
