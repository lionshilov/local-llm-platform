import { useCallback, useRef, useState } from "react";
import { streamReply } from "../lib/reply";
import { newId } from "../lib/storage";
import type { ChatMessage, Settings } from "../lib/types";

export interface ArenaColumn {
  model: string | null;
  messages: ChatMessage[];
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
  const [fairTiming, setFairTiming] = useState(false);
  const controllers = useRef<AbortController[]>([]);

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

  const send = useCallback(
    async (text: string) => {
      const ready = columns.every((c) => c.model);
      if (!ready || streaming) return;

      const user: ChatMessage = { id: newId(), role: "user", content: text };
      const jobs = columns.map((column, index) => {
        const reply: ChatMessage = {
          id: newId(),
          role: "assistant",
          content: "",
          reasoning: "",
          model: column.model ?? undefined,
          status: "streaming",
        };
        return {
          index,
          model: column.model as string,
          history: [...column.messages, user],
          reply,
        };
      });
      setColumns((all) =>
        all.map((c, i) => {
          const job = jobs[i];
          return job ? { ...c, messages: [...job.history, job.reply] } : c;
        }),
      );

      controllers.current = jobs.map(() => new AbortController());
      setStreaming(true);
      const run = async (job: (typeof jobs)[number]) => {
        const signal = controllers.current[job.index]?.signal ?? new AbortController().signal;
        const result = await streamReply({
          model: job.model,
          history: job.history,
          settings,
          signal,
          onProgress: (partial) => patch(job.index, job.reply.id, partial),
        });
        patch(job.index, job.reply.id, result);
      };

      if (fairTiming) {
        for (const job of jobs) await run(job);
      } else {
        await Promise.all(jobs.map(run));
      }
      setStreaming(false);
    },
    [columns, fairTiming, patch, settings, streaming],
  );

  const stop = useCallback(() => {
    for (const controller of controllers.current) controller.abort();
  }, []);

  const reset = useCallback(() => {
    setColumns((all) => all.map((c) => ({ ...c, messages: [] })));
  }, []);

  return { columns, streaming, fairTiming, setFairTiming, setModel, send, stop, reset };
}
