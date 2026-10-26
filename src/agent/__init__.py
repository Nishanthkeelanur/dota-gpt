"""Ollama client, tool registration and the CLI loop."""

from .client import DEFAULT_MODEL, ask
from .tools_spec import REGISTRY, TOOL_SCHEMAS, execute

__all__ = ["ask", "DEFAULT_MODEL", "TOOL_SCHEMAS", "REGISTRY", "execute"]
