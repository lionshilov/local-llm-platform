"""Deterministic synthetic prompts.

Every request gets a unique nonce as its first line. All three engines (llama.cpp, MLX,
Ollama) reuse the KV cache for a shared prompt prefix, so without the nonce repeated
requests would skip prefill and TTFT would look unrealistically good.
"""

from __future__ import annotations

import random
import uuid

_VOCAB = (
    "system", "latency", "memory", "cache", "token", "model", "kernel", "thread", "buffer",
    "queue", "vector", "matrix", "gradient", "tensor", "layer", "attention", "router",
    "replica", "shard", "cluster", "request", "stream", "socket", "budget", "throughput",
    "benchmark", "quantization", "precision", "weight", "context", "window", "decoder",
    "encoder", "metric", "trace", "span", "service", "gateway", "deploy", "rollout", "canary",
    "fallback", "retry", "timeout", "payload", "schema", "index", "embedding", "retrieval",
    "document", "chunk", "ranking", "score",
)  # fmt: skip

_TOPICS = (
    "how a CPU cache hierarchy works",
    "the history of the TCP protocol",
    "how databases implement transactions",
    "how garbage collectors work",
    "how DNS resolution works end to end",
    "how a compiler optimizes loops",
    "how load balancers distribute traffic",
    "how public-key cryptography works",
)

Messages = list[dict[str, str]]


def _nonce() -> str:
    return f"[request {uuid.uuid4().hex[:12]}]"


def synthetic_document(n_words: int, seed: int = 0) -> str:
    rng = random.Random(seed)
    words = [rng.choice(_VOCAB) for _ in range(n_words)]
    sentences = [" ".join(words[i : i + 12]).capitalize() + "." for i in range(0, n_words, 12)]
    return " ".join(sentences)


def build_messages(prompt_words: int, index: int) -> Messages:
    """Build a chat request whose prompt is roughly ``prompt_words`` long.

    Short prompts ask for a long explanation (decode-bound); long prompts embed a
    synthetic document and ask for a short summary (prefill-bound).
    """
    topic = _TOPICS[index % len(_TOPICS)]
    instruction = (
        f"Write a long, detailed technical explanation of {topic}. "
        "Use several paragraphs and do not stop early."
    )
    filler_words = prompt_words - len(instruction.split())
    if filler_words > 50:
        document = synthetic_document(filler_words, seed=index)
        content = f"{_nonce()}\n{document}\n\nSummarize the text above in one sentence."
    else:
        content = f"{_nonce()}\n{instruction}"
    return [{"role": "user", "content": content}]
