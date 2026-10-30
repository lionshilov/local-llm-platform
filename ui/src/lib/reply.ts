import { type ApiMessage, streamChat } from "./api";
import type { ChatMessage, LiveStats, MessageStats, Settings } from "./types";

export function toApiMessages(settings: Settings, history: ChatMessage[]): ApiMessage[] {
  const system: ApiMessage[] = settings.systemPrompt.trim()
    ? [{ role: "system", content: settings.systemPrompt.trim() }]
    : [];
  const turns = history
    .filter((m) => m.role === "user" || (m.content && m.status !== "error"))
    .map((m): ApiMessage => ({ role: m.role, content: m.content }));
  return [...system, ...turns];
}

export type ReplyPatch = Pick<
  ChatMessage,
  "content" | "reasoning" | "status" | "stats" | "error" | "live"
>;

export function liveStats(
  startedAt: number,
  firstTokenAt: number | null,
  tokens: number,
  now: number,
): LiveStats {
  const decodeS = firstTokenAt === null ? 0 : (now - firstTokenAt) / 1000;
  return {
    elapsedMs: now - startedAt,
    ttftMs: firstTokenAt === null ? null : firstTokenAt - startedAt,
    tokens,
    tokensPerSecond: tokens > 1 && decodeS > 0.25 ? (tokens - 1) / decodeS : null,
  };
}

/**
 * Stream one assistant reply. Partial text is reported at most once per animation frame,
 * so long markdown answers don't re-render on every token. Resolves with the final state
 * (done, stopped or error); never rejects.
 */
export async function streamReply(options: {
  model: string;
  history: ChatMessage[];
  settings: Settings;
  signal: AbortSignal;
  onProgress: (partial: Pick<ChatMessage, "content" | "reasoning" | "live">) => void;
}): Promise<ReplyPatch> {
  const { model, history, settings, signal, onProgress } = options;
  let content = "";
  let reasoning = "";
  let frame: number | null = null;
  const startedAt = performance.now();
  let firstTokenAt: number | null = null;
  let chunks = 0;
  const flush = () => {
    frame = null;
    onProgress({
      content,
      reasoning,
      live: liveStats(startedAt, firstTokenAt, chunks, performance.now()),
    });
  };
  const schedule = () => {
    frame ??= requestAnimationFrame(flush);
  };
  const onToken = () => {
    firstTokenAt ??= performance.now();
    chunks += 1;
    schedule();
  };
  // Keep the live timer moving while the model is still prefilling or thinking.
  const ticker = setInterval(schedule, 200);
  const partialStats = (reason: string): MessageStats => {
    const live = liveStats(startedAt, firstTokenAt, chunks, performance.now());
    return {
      ttftMs: live.ttftMs,
      tokensPerSecond: live.tokensPerSecond,
      completionTokens: chunks || null,
      promptTokens: null,
      thinkingMs: null,
      durationMs: live.elapsedMs,
      finishReason: reason,
      servedBy: null,
    };
  };

  try {
    const stats = await streamChat(
      {
        model,
        messages: toApiMessages(settings, history),
        temperature: settings.temperature,
        max_tokens: settings.maxTokens,
        reasoning_effort: settings.thinking ? "medium" : "none",
      },
      {
        onContent: (text) => {
          content += text;
          onToken();
        },
        onReasoning: (text) => {
          reasoning += text;
          onToken();
        },
      },
      signal,
    );
    return { content, reasoning, status: "done", stats, live: undefined };
  } catch (error) {
    if (signal.aborted) {
      return {
        content,
        reasoning,
        status: "stopped",
        stats: partialStats("stopped"),
        live: undefined,
      };
    }
    const message = error instanceof Error ? error.message : String(error);
    return { content, reasoning, status: "error", error: message, live: undefined };
  } finally {
    clearInterval(ticker);
    if (frame !== null) cancelAnimationFrame(frame);
  }
}
