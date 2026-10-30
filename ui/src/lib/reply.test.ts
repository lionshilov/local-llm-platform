import { describe, expect, it } from "vitest";
import { liveStats, toApiMessages } from "./reply";
import { DEFAULT_SETTINGS } from "./storage";

describe("liveStats", () => {
  it("reports elapsed time before the first token", () => {
    expect(liveStats(1000, null, 0, 1800)).toEqual({
      elapsedMs: 800,
      ttftMs: null,
      tokens: 0,
      tokensPerSecond: null,
    });
  });

  it("computes decode speed after the first token", () => {
    const live = liveStats(1000, 1200, 41, 2200);
    expect(live.ttftMs).toBe(200);
    expect(live.tokensPerSecond).toBeCloseTo(40);
  });

  it("waits for a stable window before showing a speed", () => {
    expect(liveStats(1000, 1200, 3, 1300).tokensPerSecond).toBeNull();
  });
});

describe("toApiMessages", () => {
  it("prepends the system prompt and drops failed replies", () => {
    const messages = toApiMessages({ ...DEFAULT_SETTINGS, systemPrompt: "  Be brief. " }, [
      { id: "1", role: "user", content: "hi" },
      { id: "2", role: "assistant", content: "", status: "error", error: "boom" },
      { id: "3", role: "user", content: "again" },
    ]);
    expect(messages).toEqual([
      { role: "system", content: "Be brief." },
      { role: "user", content: "hi" },
      { role: "user", content: "again" },
    ]);
  });
});
