import { type ApiMessage, streamChat } from "./api";
import type { ChatMessage, Settings } from "./types";

export function toApiMessages(settings: Settings, history: ChatMessage[]): ApiMessage[] {
  const system: ApiMessage[] = settings.systemPrompt.trim()
    ? [{ role: "system", content: settings.systemPrompt.trim() }]
    : [];
  const turns = history
    .filter((m) => m.role === "user" || (m.content && m.status !== "error"))
    .map((m): ApiMessage => ({ role: m.role, content: m.content }));
  return [...system, ...turns];
}

export type ReplyPatch = Pick<ChatMessage, "content" | "reasoning" | "status" | "stats" | "error">;

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
  onProgress: (partial: Pick<ChatMessage, "content" | "reasoning">) => void;
}): Promise<ReplyPatch> {
  const { model, history, settings, signal, onProgress } = options;
  let content = "";
  let reasoning = "";
  let frame: number | null = null;
  const flush = () => {
    frame = null;
    onProgress({ content, reasoning });
  };
  const schedule = () => {
    frame ??= requestAnimationFrame(flush);
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
          schedule();
        },
        onReasoning: (text) => {
          reasoning += text;
          schedule();
        },
      },
      signal,
    );
    return { content, reasoning, status: "done", stats };
  } catch (error) {
    if (signal.aborted) return { content, reasoning, status: "stopped" };
    const message = error instanceof Error ? error.message : String(error);
    return { content, reasoning, status: "error", error: message };
  } finally {
    if (frame !== null) cancelAnimationFrame(frame);
  }
}
