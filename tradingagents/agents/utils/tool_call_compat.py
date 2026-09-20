"""Provider-agnostic tool-call extraction.

The OpenAI/local_openai path (tradingagents.agents.utils.gpt5_llm) puts
pending tool calls in `additional_kwargs["tool_calls"]` to mirror the raw
Responses API shape. Every other provider client (Anthropic, Google, xAI,
OpenRouter, MiniMax, DeepSeek, Qwen, GLM, Ollama, Azure) is a standard
LangChain chat model, which instead populates the normalized `.tool_calls`
attribute and leaves `additional_kwargs` without a "tool_calls" key.

Analyst tool loops need a single check that works for both, since a single
run reads `llm_provider` from config and either path can be selected at
runtime.
"""

from __future__ import annotations

import json
from typing import Any, List


def _to_langchain_shape(raw_call: dict) -> dict:
    """Normalize one tool call to LangChain's standard ToolCall shape.

    LangChain's own OpenAI-compatible serializer
    (langchain_openai._convert_message_to_dict) only knows how to rebuild a
    valid OpenAI-wire-format request from `message.tool_calls`; anything
    left only in `additional_kwargs["tool_calls"]` gets passed through
    as-is, which breaks the API call if it isn't already in OpenAI's
    `{"id", "type": "function", "function": {"name", "arguments"}}` shape.
    Normalizing to LangChain's shape here means every downstream site
    (tool dispatch, replay message construction) only ever sees one format.
    """
    if "function" in raw_call:
        func = raw_call.get("function") or {}
        args = func.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except (TypeError, ValueError):
                args = {}
        return {
            "name": func.get("name"),
            "args": args or {},
            "id": raw_call.get("id"),
            "type": "tool_call",
        }
    return {
        "name": raw_call.get("name"),
        "args": raw_call.get("args") or {},
        "id": raw_call.get("id") or raw_call.get("tool_call_id"),
        "type": "tool_call",
    }


def get_pending_tool_calls(result: Any) -> List[dict]:
    """Return the tool calls an LLM response is asking for, if any.

    Checks the standard LangChain `.tool_calls` attribute first (populated
    by every provider except the custom OpenAI/local_openai wrapper), then
    falls back to `additional_kwargs["tool_calls"]` (the OpenAI Responses-API
    shape). Always returns LangChain-shaped dicts (see `_to_langchain_shape`)
    so callers can construct replay `AIMessage(tool_calls=...)` uniformly.
    """
    tool_calls = getattr(result, "tool_calls", None)
    if not tool_calls:
        additional_kwargs = getattr(result, "additional_kwargs", None) or {}
        tool_calls = additional_kwargs.get("tool_calls") or []
    return [_to_langchain_shape(tc) for tc in tool_calls]
