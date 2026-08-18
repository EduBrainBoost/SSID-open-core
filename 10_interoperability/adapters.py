"""OpenCore public SDK — interoperability adapters."""
from __future__ import annotations
from .public_interface import AdapterContract


class MCPAdapter(AdapterContract):
    """Model Context Protocol adapter (public reference implementation)."""

    def __init__(self) -> None:
        super().__init__("mcp_adapter", "mock")

    def list_tools(self) -> list:
        return [
            {"name": "example_tool", "description": "Public example tool", "inputSchema": {"type": "object"}},
        ]

    def invoke_tool(self, tool_name: str, arguments: dict) -> dict:
        return {"status": "mock_response", "tool": tool_name}


class A2AAdapter(AdapterContract):
    """Agent-to-Agent protocol adapter (public reference)."""

    def __init__(self) -> None:
        super().__init__("a2a_adapter", "mock")

    def send_task(self, task: dict) -> dict:
        return {
            "task_id": "synthetic-task-001",
            "status": "accepted",
            "estimated_completion": "2026-01-01T00:01:00Z",
        }

    def get_status(self, task_id: str) -> dict:
        return {"task_id": task_id, "status": "completed", "result": {"synthetic": True}}


class OpenAPIContract(AdapterContract):
    """Public OpenAPI specification example."""

    def __init__(self) -> None:
        super().__init__("openapi_contract", "mock")

    def spec(self) -> dict:
        return {
            "openapi": "3.0.3",
            "info": {"title": "SSID OpenCore Public API", "version": "1.0.0"},
            "paths": {
                "/public/schemas": {
                    "get": {
                        "summary": "List public schemas",
                        "responses": {"200": {"description": "Public schemas"}},
                    }
                }
            },
        }
