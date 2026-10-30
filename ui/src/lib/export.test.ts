import { describe, expect, it } from "vitest";
import { conversationToMarkdown, slugify } from "./export";
import type { Conversation } from "./types";

const conversation: Conversation = {
  id: "c1",
  title: "KV cache",
  model: "llamacpp",
  createdAt: 0,
  updatedAt: 0,
  messages: [
    { id: "1", role: "user", content: "What is a KV cache?" },
    {
      id: "2",
      role: "assistant",
      content: "It stores keys and values.",
      reasoning: "Think about attention.",
      model: "llamacpp",
      status: "done",
      stats: {
        ttftMs: 212.4,
        tokensPerSecond: 41.23,
        completionTokens: 120,
        promptTokens: 30,
        thinkingMs: null,
        durationMs: 3000,
        finishReason: "stop",
        servedBy: "llamacpp",
      },
    },
  ],
};

describe("conversationToMarkdown", () => {
  it("includes turns, reasoning and per-reply metrics", () => {
    const md = conversationToMarkdown(conversation, () => "Qwen3.5 4B · llama.cpp");
    expect(md).toContain("# KV cache");
    expect(md).toContain("## You\n\nWhat is a KV cache?");
    expect(md).toContain("_Qwen3.5 4B · llama.cpp · TTFT 212 ms · 41.2 tok/s · 120 tokens_");
    expect(md).toContain("<details><summary>Reasoning</summary>");
    expect(md).toContain("It stores keys and values.");
  });
});

describe("slugify", () => {
  it("keeps letters in any script", () => {
    expect(slugify("Расскажи сказку: Колобок!")).toBe("расскажи-сказку-колобок");
    expect(slugify("???")).toBe("chat");
  });
});
