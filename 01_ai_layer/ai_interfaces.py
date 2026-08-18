"""OpenCore public SDK — AI layer interfaces."""
from __future__ import annotations
from typing import Any, Dict, List, Optional


class AIEvaluationStub:
    """Public AI evaluation stub — reference implementation only."""

    def __init__(self, model_name: str = "public-stub") -> None:
        self.model_name = model_name

    def evaluate(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "model": self.model_name,
            "input": prompt,
            "output": f"[public-stub response to: {prompt}]",
            "tokens_used": len(prompt.split()) * 2,
            "latency_ms": 0.5,
            "synthetic": True,
        }

    def list_metrics(self) -> List[str]:
        return ["accuracy", "latency", "cost_per_token", "safety_score"]


class ProviderNeutralInterface:
    """Provider-neutral AI interface for external integrations."""

    def __init__(self) -> None:
        self.supported_providers = ["openai", "anthropic", "mistral", "local"]

    def format_prompt(self, system: str, user: str) -> dict:
        return {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "model": "public-stub",
        }

    def parse_response(self, raw: dict) -> dict:
        return {
            "content": raw.get("choices", [{}])[0].get("message", {}).get("content", ""),
            "model": raw.get("model", "unknown"),
            "synthetic": True,
        }
