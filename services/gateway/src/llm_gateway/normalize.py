"""Hide engine quirks behind one OpenAI-style contract.

Inbound: clients use the standard ``reasoning_effort`` field; we translate it to the
switch each engine actually understands. Outbound: reasoning text arrives as
``reasoning`` (Ollama, MLX) or ``reasoning_content`` (llama.cpp); clients always get
``reasoning_content``.
"""

from __future__ import annotations

from typing import Any

from llm_gateway.config import EngineKind

Json = dict[str, Any]


def apply_reasoning_effort(body: Json, engine: EngineKind) -> Json:
    """Return a copy of ``body`` with ``reasoning_effort`` mapped for ``engine``."""
    body = dict(body)
    effort = body.pop("reasoning_effort", None)
    if effort is None:
        return body
    match engine:
        case EngineKind.LLAMACPP | EngineKind.MLX:
            template_kwargs = dict(body.get("chat_template_kwargs") or {})
            template_kwargs["enable_thinking"] = effort != "none"
            body["chat_template_kwargs"] = template_kwargs
        case EngineKind.OLLAMA | EngineKind.OPENAI:
            body["reasoning_effort"] = effort
    return body


def normalize_payload(payload: Json, model_id: str) -> Json:
    """Rewrite a completion or stream chunk in place to the gateway's contract."""
    payload["model"] = model_id
    for choice in payload.get("choices") or []:
        for key in ("delta", "message"):
            part = choice.get(key)
            if isinstance(part, dict) and "reasoning" in part:
                reasoning = part.pop("reasoning")
                if reasoning and not part.get("reasoning_content"):
                    part["reasoning_content"] = reasoning
    return payload


def has_generated_text(chunk: Json) -> bool:
    for choice in chunk.get("choices") or []:
        delta = choice.get("delta") or {}
        if delta.get("content") or delta.get("reasoning_content"):
            return True
    return False
