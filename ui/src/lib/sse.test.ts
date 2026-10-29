import { describe, expect, it } from "vitest";
import { computeStats, createSseParser } from "./sse";

describe("createSseParser", () => {
  it("returns complete data payloads and buffers partial lines", () => {
    const parser = createSseParser();
    expect(parser.push(': keep-alive\n\ndata: {"a":')).toEqual([]);
    expect(parser.push("1}\n\nevent: x\ndata: [DONE]\n")).toEqual(['{"a":1}', "[DONE]"]);
  });

  it("handles CRLF line endings and missing space after the colon", () => {
    const parser = createSseParser();
    expect(parser.push('data:{"b":2}\r\n\r\n')).toEqual(['{"b":2}']);
  });
});

describe("computeStats", () => {
  const base = {
    startedAt: 1000,
    firstTokenAt: 1200,
    firstContentAt: 1200,
    lastTokenAt: 3200,
    endedAt: 3250,
    completionTokens: 101,
    promptTokens: 20,
    finishReason: "stop",
    servedBy: "llamacpp",
  };

  it("computes TTFT and decode speed like llm-bench", () => {
    const stats = computeStats(base);
    expect(stats.ttftMs).toBe(200);
    expect(stats.tokensPerSecond).toBeCloseTo(50);
    expect(stats.durationMs).toBe(2250);
    expect(stats.thinkingMs).toBeNull();
  });

  it("measures thinking time until the first answer token", () => {
    expect(computeStats({ ...base, firstContentAt: 2700 }).thinkingMs).toBe(1500);
  });

  it("returns nulls when nothing was generated", () => {
    const stats = computeStats({
      ...base,
      firstTokenAt: null,
      firstContentAt: null,
      lastTokenAt: null,
      completionTokens: null,
    });
    expect(stats.ttftMs).toBeNull();
    expect(stats.tokensPerSecond).toBeNull();
  });
});
