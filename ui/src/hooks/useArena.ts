import { useCallback, useEffect, useRef, useState } from "react";
import { type ReplyPatch, streamReply } from "../lib/reply";
import { newId } from "../lib/storage";
import type { ChatMessage, Settings } from "../lib/types";

export interface ArenaColumn {
  model: string | null;
  messages: ChatMessage[];
}

export type Vote = "a" | "b" | "tie";

export interface ArenaRound {
  id: string;
  at: number;
  models: [string, string];
  ttftMs: [number | null, number | null];
  tokensPerSecond: [number | null, number | null];
  fairTiming: boolean;
  vote: Vote | null;
}

export interface Score {
  wins: [number, number];
  ties: number;
  fasterFirstToken: [number, number];
  fasterDecode: [number, number];
  rounds: number;
}

const ROUNDS_KEY = "llp.arena.rounds.v1";
const MAX_ROUNDS = 300;

function loadRounds(): ArenaRound[] {
  try {
    return JSON.parse(localStorage.getItem(ROUNDS_KEY) ?? "[]") as ArenaRound[];
  } catch {
    return [];
  }
}

/** Tally rounds between two models, in either column order. */
export function scoreFor(rounds: ArenaRound[], a: string | null, b: string | null): Score {
  const score: Score = {
    wins: [0, 0],
    ties: 0,
    fasterFirstToken: [0, 0],
    fasterDecode: [0, 0],
    rounds: 0,
  };
  if (!a || !b) return score;
  for (const round of rounds) {
    const [x, y] = round.models;
    const flipped = x === b && y === a;
    if (!(x === a && y === b) && !flipped) continue;
    const side = (i: 0 | 1): 0 | 1 => (flipped ? ((1 - i) as 0 | 1) : i);
    score.rounds += 1;
    if (round.vote === "tie") score.ties += 1;
    else if (round.vote) score.wins[side(round.vote === "a" ? 0 : 1)] += 1;
    const [t0, t1] = round.ttftMs;
    if (t0 != null && t1 != null && t0 !== t1) score.fasterFirstToken[side(t0 < t1 ? 0 : 1)] += 1;
    const [d0, d1] = round.tokensPerSecond;
    if (d0 != null && d1 != null && d0 !== d1) score.fasterDecode[side(d0 > d1 ? 0 : 1)] += 1;
  }
  return score;
}

/**
 * Send every prompt to two backends and stream both answers. In "fair timing" mode the
 * second backend starts only after the first finishes, so they don't share the GPU and
 * their latency numbers are comparable.
 */
export function useArena(settings: Settings) {
  const [columns, setColumns] = useState<ArenaColumn[]>([
    { model: null, messages: [] },
    { model: null, messages: [] },
  ]);
  const [streaming, setStreaming] = useState(false);
  const [fairTiming, setFairTiming] = useState(true);
  const [rounds, setRounds] = useState<ArenaRound[]>(loadRounds);
  const [currentRound, setCurrentRound] = useState<string | null>(null);
  const controllers = useRef<AbortController[]>([]);

  useEffect(() => {
    localStorage.setItem(ROUNDS_KEY, JSON.stringify(rounds.slice(-MAX_ROUNDS)));
  }, [rounds]);

  const patch = useCallback((column: number, messageId: string, update: Partial<ChatMessage>) => {
    setColumns((all) =>
      all.map((c, i) =>
        i !== column
          ? c
          : {
              ...c,
              messages: c.messages.map((m) => (m.id === messageId ? { ...m, ...update } : m)),
            },
      ),
    );
  }, []);

  const setModel = useCallback((column: number, model: string) => {
    setColumns((all) => all.map((c, i) => (i === column ? { ...c, model } : c)));
  }, []);

  const swap = useCallback(() => {
    setColumns((all) => [...all].reverse());
  }, []);

  const send = useCallback(
    async (text: string) => {
      const [left, right] = columns;
      if (!left?.model || !right?.model || streaming) return;

      const user: ChatMessage = { id: newId(), role: "user", content: text, createdAt: Date.now() };
      const jobs = columns.map((column, index) => {
        const reply: ChatMessage = {
          id: newId(),
          role: "assistant",
          content: "",
          reasoning: "",
          model: column.model ?? undefined,
          status: "streaming",
          createdAt: Date.now(),
        };
        return { index, model: column.model as string, history: [...column.messages, user], reply };
      });
      setColumns((all) =>
        all.map((c, i) => {
          const job = jobs[i];
          return job ? { ...c, messages: [...job.history, job.reply] } : c;
        }),
      );
      setCurrentRound(null);

      controllers.current = jobs.map(() => new AbortController());
      setStreaming(true);
      const run = async (job: (typeof jobs)[number]): Promise<ReplyPatch> => {
        const signal = controllers.current[job.index]?.signal ?? new AbortController().signal;
        const result = await streamReply({
          model: job.model,
          history: job.history,
          settings,
          signal,
          onProgress: (partial) => patch(job.index, job.reply.id, partial),
        });
        patch(job.index, job.reply.id, result);
        return result;
      };

      const fair = fairTiming;
      const results: ReplyPatch[] = [];
      if (fair) {
        for (const job of jobs) results.push(await run(job));
      } else {
        results.push(...(await Promise.all(jobs.map(run))));
      }
      setStreaming(false);

      const [a, b] = results;
      if (a?.status === "done" && b?.status === "done") {
        const round: ArenaRound = {
          id: newId(),
          at: Date.now(),
          models: [left.model, right.model],
          ttftMs: [a.stats?.ttftMs ?? null, b.stats?.ttftMs ?? null],
          tokensPerSecond: [a.stats?.tokensPerSecond ?? null, b.stats?.tokensPerSecond ?? null],
          fairTiming: fair,
          vote: null,
        };
        setRounds((all) => [...all, round]);
        setCurrentRound(round.id);
      }
    },
    [columns, fairTiming, patch, settings, streaming],
  );

  const vote = useCallback((roundId: string, choice: Vote) => {
    setRounds((all) => all.map((r) => (r.id === roundId ? { ...r, vote: choice } : r)));
  }, []);

  const stop = useCallback(() => {
    for (const controller of controllers.current) controller.abort();
  }, []);

  const reset = useCallback(() => {
    setColumns((all) => all.map((c) => ({ ...c, messages: [] })));
    setCurrentRound(null);
  }, []);

  const resetScores = useCallback(() => setRounds([]), []);

  return {
    columns,
    streaming,
    fairTiming,
    setFairTiming,
    setModel,
    swap,
    send,
    vote,
    stop,
    reset,
    resetScores,
    rounds,
    round: rounds.find((r) => r.id === currentRound) ?? null,
    score: scoreFor(rounds, columns[0]?.model ?? null, columns[1]?.model ?? null),
  };
}
