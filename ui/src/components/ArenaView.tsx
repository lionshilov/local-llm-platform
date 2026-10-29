import { RotateCcw, Scale, Swords, Timer, Zap } from "lucide-react";
import { type ReactNode, useEffect, useRef } from "react";
import { useArena } from "../hooks/useArena";
import type { ChatMessage, ModelInfo, Settings } from "../lib/types";
import { Composer } from "./Composer";
import { MessageView } from "./MessageView";
import { ModelPicker } from "./ModelPicker";

const SIDES = ["A", "B"] as const;

function lastReply(messages: ChatMessage[]): ChatMessage | undefined {
  return messages.findLast((m) => m.role === "assistant");
}

function Verdict({
  icon,
  name,
  a,
  b,
  unit,
  higherIsBetter,
  labels,
}: {
  icon: ReactNode;
  name: string;
  a: number | null | undefined;
  b: number | null | undefined;
  unit: string;
  higherIsBetter: boolean;
  labels: [string, string];
}) {
  if (a == null || b == null || a <= 0 || b <= 0) return null;
  const aWins = higherIsBetter ? a >= b : a <= b;
  const ratio = aWins ? (higherIsBetter ? a / b : b / a) : higherIsBetter ? b / a : a / b;
  const fmt = (v: number) => (unit === "ms" ? Math.round(v).toString() : v.toFixed(1));
  return (
    <div className="flex items-center gap-2">
      <span className="flex items-center gap-1 text-zinc-500">
        {icon}
        {name}
      </span>
      <span className={aWins ? "text-emerald-300" : "text-zinc-400"}>A {fmt(a)}</span>
      <span className="text-zinc-600">vs</span>
      <span className={aWins ? "text-zinc-400" : "text-emerald-300"}>
        B {fmt(b)} {unit}
      </span>
      {ratio >= 1.05 && (
        <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-emerald-300">
          {aWins ? labels[0] : labels[1]} {ratio.toFixed(2)}×
        </span>
      )}
    </div>
  );
}

export function ArenaView({
  models,
  settings,
  onToggleThinking,
}: {
  models: ModelInfo[];
  settings: Settings;
  onToggleThinking: () => void;
}) {
  const arena = useArena(settings);
  const scrollRefs = useRef<(HTMLDivElement | null)[]>([]);
  const labelFor = (id?: string | null) => models.find((m) => m.id === id)?.label ?? id ?? "model";
  const shortLabel = (id?: string | null) => labelFor(id).split("·").pop()?.trim() ?? "";

  // Default to the first two backends that are online (or any two).
  const { columns, setModel } = arena;
  useEffect(() => {
    const ranked = [...models.filter((m) => m.available), ...models.filter((m) => !m.available)];
    const taken = columns.flatMap((c) => (c.model ? [c.model] : []));
    columns.forEach((column, i) => {
      if (column.model) return;
      const pick = ranked.find((m) => !taken.includes(m.id)) ?? ranked[i];
      if (pick) {
        taken.push(pick.id);
        setModel(i, pick.id);
      }
    });
  }, [models, columns, setModel]);

  const lengths = arena.columns.map(
    (c) => `${c.messages.length}:${c.messages.at(-1)?.content.length}`,
  );
  useEffect(() => {
    for (const el of scrollRefs.current) if (el) el.scrollTop = el.scrollHeight;
  }, [lengths.join("|")]);

  const [left, right] = arena.columns;
  const a = left ? lastReply(left.messages) : undefined;
  const b = right ? lastReply(right.messages) : undefined;
  const labels: [string, string] = [
    `${shortLabel(left?.model)} faster`,
    `${shortLabel(right?.model)} faster`,
  ];
  const online = arena.columns.every((c) => models.find((m) => m.id === c.model)?.available);
  const empty = arena.columns.every((c) => c.messages.length === 0);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="grid min-h-0 flex-1 grid-cols-1 md:grid-cols-2 md:divide-x md:divide-white/5">
        {arena.columns.map((column, i) => (
          <section key={SIDES[i]} className="flex min-h-0 flex-col">
            <div className="flex items-center gap-2 border-b border-white/5 px-3 py-1.5">
              <span className="flex size-6 items-center justify-center rounded-md bg-white/5 font-mono text-xs text-zinc-400">
                {SIDES[i]}
              </span>
              <ModelPicker
                models={models}
                value={column.model}
                onChange={(id) => arena.setModel(i, id)}
              />
            </div>
            <div
              ref={(el) => {
                scrollRefs.current[i] = el;
              }}
              className="flex-1 overflow-y-auto"
            >
              {empty ? (
                <div className="flex h-full flex-col items-center justify-center gap-2 p-8 text-center text-sm text-zinc-500">
                  {i === 0 ? <Swords className="size-6" /> : <Scale className="size-6" />}
                  {labelFor(column.model)}
                </div>
              ) : (
                <div className="space-y-6 px-4 pt-5 pb-8">
                  {column.messages.map((message) => (
                    <MessageView
                      key={message.id}
                      message={message}
                      modelLabel={labelFor(message.model)}
                      labelFor={labelFor}
                      canRegenerate={false}
                      onRegenerate={() => undefined}
                    />
                  ))}
                </div>
              )}
            </div>
          </section>
        ))}
      </div>

      <div className="mx-auto w-full max-w-3xl px-4 pb-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2 font-mono text-[11px]">
          <div className="flex flex-wrap items-center gap-x-5 gap-y-1">
            {a?.stats && b?.stats ? (
              <>
                <Verdict
                  icon={<Timer className="size-3" />}
                  name="TTFT"
                  a={a.stats.ttftMs}
                  b={b.stats.ttftMs}
                  unit="ms"
                  higherIsBetter={false}
                  labels={labels}
                />
                <Verdict
                  icon={<Zap className="size-3" />}
                  name="decode"
                  a={a.stats.tokensPerSecond}
                  b={b.stats.tokensPerSecond}
                  unit="tok/s"
                  higherIsBetter
                  labels={labels}
                />
              </>
            ) : (
              <span className="text-zinc-500">
                Same prompt, two backends, live latency. Turn on fair timing for comparable numbers.
              </span>
            )}
          </div>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => arena.setFairTiming(!arena.fairTiming)}
              aria-pressed={arena.fairTiming}
              title="Run backends one after another so they don't compete for the GPU"
              className={`rounded-full border px-2.5 py-1 transition ${
                arena.fairTiming
                  ? "border-emerald-400/40 bg-emerald-500/10 text-emerald-200"
                  : "border-white/10 text-zinc-400 hover:text-zinc-200"
              }`}
            >
              fair timing {arena.fairTiming ? "on" : "off"}
            </button>
            <button
              type="button"
              onClick={arena.reset}
              disabled={arena.streaming || empty}
              title="Clear both columns"
              aria-label="Clear arena"
              className="rounded-full p-1.5 text-zinc-400 transition hover:bg-white/5 hover:text-zinc-200 disabled:opacity-40"
            >
              <RotateCcw className="size-3.5" />
            </button>
          </div>
        </div>
        <Composer
          streaming={arena.streaming}
          disabled={!online}
          thinking={settings.thinking}
          onToggleThinking={onToggleThinking}
          onSend={(text) => void arena.send(text)}
          onStop={arena.stop}
        />
      </div>
    </div>
  );
}
