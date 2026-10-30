import { describe, expect, it } from "vitest";
import { type ArenaRound, scoreFor } from "./useArena";

function round(
  models: [string, string],
  ttftMs: [number, number],
  tps: [number, number],
  vote: ArenaRound["vote"],
): ArenaRound {
  return {
    id: Math.random().toString(36),
    at: 0,
    models,
    ttftMs,
    tokensPerSecond: tps,
    fairTiming: true,
    vote,
  };
}

describe("scoreFor", () => {
  const rounds = [
    round(["cpp", "mlx"], [170, 270], [41, 54], "a"),
    round(["cpp", "mlx"], [180, 260], [40, 52], "tie"),
    // Same pair with the columns swapped: must count for the same models.
    round(["mlx", "cpp"], [250, 175], [53, 41], "a"),
    round(["cpp", "ollama"], [170, 300], [41, 38], "b"),
  ];

  it("tallies votes and speed wins for a pair in either column order", () => {
    expect(scoreFor(rounds, "cpp", "mlx")).toEqual({
      wins: [1, 1],
      ties: 1,
      fasterFirstToken: [3, 0],
      fasterDecode: [0, 3],
      rounds: 3,
    });
  });

  it("orients the score to the requested column order", () => {
    const score = scoreFor(rounds, "mlx", "cpp");
    expect(score.fasterFirstToken).toEqual([0, 3]);
    expect(score.fasterDecode).toEqual([3, 0]);
  });

  it("is empty for unknown or unset pairs", () => {
    expect(scoreFor(rounds, "cpp", null).rounds).toBe(0);
    expect(scoreFor(rounds, "a", "b").rounds).toBe(0);
  });
});
