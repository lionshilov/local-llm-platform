"""Admission control: a concurrency limit with a bounded, time-limited wait queue.

Without it, an engine that serializes requests (Ollama with Qwen3.5 does) makes the
fourth user wait 20+ seconds for a first token. Rejecting early with 429 + Retry-After
keeps TTFT predictable for admitted requests and lets clients back off or fail over.
"""

from __future__ import annotations

import asyncio


class Slot:
    """A held concurrency slot. Releasing is idempotent, so every exit path may call it."""

    def __init__(self, admission: Admission) -> None:
        self._admission = admission
        self._released = False

    def release(self) -> None:
        if not self._released:
            self._released = True
            self._admission._release()


class Admission:
    def __init__(self, limit: int | None, max_queue: int = 0, timeout_s: float = 30.0) -> None:
        self.limit = limit
        self.max_queue = max_queue
        self.timeout_s = timeout_s
        self._semaphore = asyncio.Semaphore(limit) if limit is not None else None
        self.in_use = 0
        self.waiting = 0

    async def acquire(self) -> Slot | None:
        """Return a slot, or None if the queue is full or the wait timed out."""
        if self._semaphore is None:
            self.in_use += 1
            return Slot(self)
        if self._semaphore.locked() and self.waiting >= self.max_queue:
            return None
        self.waiting += 1
        try:
            await asyncio.wait_for(self._semaphore.acquire(), self.timeout_s)
        except TimeoutError:
            return None
        finally:
            self.waiting -= 1
        self.in_use += 1
        return Slot(self)

    def _release(self) -> None:
        self.in_use -= 1
        if self._semaphore is not None:
            self._semaphore.release()
