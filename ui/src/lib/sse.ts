/**
 * Incremental Server-Sent Events parser: feed it decoded text as it arrives and it
 * returns the complete `data:` payloads, keeping partial lines for the next call.
 */
export function createSseParser() {
  let buffer = "";
  return {
    push(text: string): string[] {
      buffer += text;
      const lines = buffer.split(/\r?\n/);
      buffer = lines.pop() ?? "";
      const payloads: string[] = [];
      for (const line of lines) {
        if (!line.startsWith("data:")) continue;
        const data = line.slice(5).trim();
        if (data) payloads.push(data);
      }
      return payloads;
    },
  };
}

export interface StreamTiming {
  startedAt: number;
  firstTokenAt: number | null;
  firstContentAt: number | null;
  lastTokenAt: number | null;
  endedAt: number;
  completionTokens: number | null;
  promptTokens: number | null;
  finishReason: string | null;
  servedBy: string | null;
}

/** Same definitions as llm-bench: TTFT, decode speed after the first token, thinking time. */
export function computeStats(t: StreamTiming) {
  const ttftMs = t.firstTokenAt === null ? null : t.firstTokenAt - t.startedAt;
  const decodeMs =
    t.firstTokenAt !== null && t.lastTokenAt !== null ? t.lastTokenAt - t.firstTokenAt : null;
  const tokensPerSecond =
    decodeMs && decodeMs > 0 && t.completionTokens && t.completionTokens > 1
      ? (t.completionTokens - 1) / (decodeMs / 1000)
      : null;
  const thinkingMs =
    t.firstTokenAt !== null && t.firstContentAt !== null && t.firstContentAt > t.firstTokenAt
      ? t.firstContentAt - t.firstTokenAt
      : null;
  return {
    ttftMs,
    tokensPerSecond,
    thinkingMs,
    completionTokens: t.completionTokens,
    promptTokens: t.promptTokens,
    durationMs: t.endedAt - t.startedAt,
    finishReason: t.finishReason,
    servedBy: t.servedBy,
  };
}
