import { computeStats, createSseParser, type StreamTiming } from "./sse";
import type { MessageStats, ModelInfo } from "./types";

export interface ModelList {
  models: ModelInfo[];
  defaultModel: string | null;
}

export async function listModels(signal?: AbortSignal): Promise<ModelList> {
  const response = await fetch("/v1/models", { signal });
  if (!response.ok) throw new Error(`Gateway returned HTTP ${response.status}`);
  const body = (await response.json()) as { data: ModelInfo[]; default?: string | null };
  return { models: body.data, defaultModel: body.default ?? null };
}

export interface ApiMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface ChatRequest {
  model: string;
  messages: ApiMessage[];
  temperature: number;
  max_tokens: number;
  reasoning_effort: "none" | "medium";
}

export interface StreamHandlers {
  onContent: (text: string) => void;
  onReasoning: (text: string) => void;
}

interface Delta {
  content?: string | null;
  reasoning_content?: string | null;
}

interface Chunk {
  model?: string;
  choices?: { delta?: Delta; finish_reason?: string | null }[];
  usage?: { prompt_tokens?: number; completion_tokens?: number } | null;
  error?: { message?: string };
}

async function errorMessage(response: Response): Promise<string> {
  const text = await response.text();
  try {
    const parsed = JSON.parse(text) as { error?: { message?: string } | string };
    if (typeof parsed.error === "string") return parsed.error;
    if (parsed.error?.message) return parsed.error.message;
  } catch {
    // not JSON; fall through
  }
  return text || `HTTP ${response.status}`;
}

/**
 * Stream a chat completion through the gateway, timing it the same way llm-bench does.
 * Resolves with stats when the stream ends; rejects with an AbortError if `signal` fires.
 */
export async function streamChat(
  request: ChatRequest,
  handlers: StreamHandlers,
  signal: AbortSignal,
): Promise<MessageStats> {
  const timing: StreamTiming = {
    startedAt: performance.now(),
    firstTokenAt: null,
    firstContentAt: null,
    lastTokenAt: null,
    endedAt: 0,
    completionTokens: null,
    promptTokens: null,
    finishReason: null,
    servedBy: null,
  };

  const response = await fetch("/v1/chat/completions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...request, stream: true, stream_options: { include_usage: true } }),
    signal,
  });
  if (!response.ok || !response.body) throw new Error(await errorMessage(response));

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  const parser = createSseParser();
  let textChunks = 0;

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    for (const data of parser.push(value)) {
      if (data === "[DONE]") continue;
      const chunk = JSON.parse(data) as Chunk;
      if (chunk.error) throw new Error(chunk.error.message ?? "Upstream error");
      timing.servedBy ??= chunk.model ?? null;
      const now = performance.now();
      for (const choice of chunk.choices ?? []) {
        const { content, reasoning_content: reasoning } = choice.delta ?? {};
        if (reasoning) handlers.onReasoning(reasoning);
        if (content) {
          handlers.onContent(content);
          timing.firstContentAt ??= now;
        }
        if (content || reasoning) {
          timing.firstTokenAt ??= now;
          timing.lastTokenAt = now;
          textChunks += 1;
        }
        timing.finishReason = choice.finish_reason ?? timing.finishReason;
      }
      if (chunk.usage) {
        timing.completionTokens = chunk.usage.completion_tokens ?? null;
        timing.promptTokens = chunk.usage.prompt_tokens ?? null;
      }
    }
  }

  timing.endedAt = performance.now();
  timing.completionTokens ??= textChunks || null;
  return computeStats(timing);
}
