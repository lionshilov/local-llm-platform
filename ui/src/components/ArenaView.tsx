import { ArrowLeftRight, Equal, RotateCcw, ThumbsUp, Timer, Trophy, Zap } from "lucide-react";
import { type ReactNode, useEffect, useRef } from "react";
import { type ArenaRound, type Score, type Vote, useArena } from "../hooks/useArena";
import { engineMeta, splitLabel } from "../lib/engines";
import type { ChatMessage, ModelInfo, Settings } from "../lib/types";
import { Composer } from "./Composer";
import { EngineAvatar } from "./EngineAvatar";
import { MessageView } from "./MessageView";
import { ModelPicker } from "./ModelPicker";

const SIDES = ["A", "B"] as const;

function lastReply(messages: ChatMessage[]): ChatMessage | undefined {
  return messages.findLast((m) => m.role === "assistant");
}

function LiveMeter({ message, model }: { message?: ChatMessage; model?: ModelInfo }) {
  const meta = engineMeta(model?.owned_by);
  if (!message) {
    return (
      <span className="hidden truncate font-mono text-[11px] text-zinc-500 lg:inline">
        {model?.upstream_model}
      </span>
    );
  }
  const streaming = message.status === "streaming";
  const tps = streaming ? message.live?.tokensPerSecond : message.stats?.tokensPerSecond;
  const ttft = streaming ? message.live?.ttftMs : message.stats?.ttftMs;
  const waiting = streaming && ttft == null;
  return (
    <div className="flex items-center gap-3 font-mono tabular-nums">
      <div className="text-right">
        <div className="text-[10px] tracking-wide text-zinc-500 uppercase">TTFT</div>
        <div className="text-sm text-zinc-300">
          {ttft != null ? `${Math.round(ttft)} ms` : waiting ? "…" : "–"}
        </div>
      </div>
      <div className="text-right">
        <div className="text-[10px] tracking-wide text-zinc-500 uppercase">tok/s</div>
        <div
          className={`text-lg leading-tight font-semibold ${streaming ? meta.text : "text-zinc-100"}`}
        >
          {tps != null ? tps.toFixed(1) : "–"}
        </div>
      </div>
    </div>
  );
}

function Column({
  side,
  column,
  models,
  onModel,
}: {
  side: (typeof SIDES)[number];
  column: { model: string | null; messages: ChatMessage[] };
  models: ModelInfo[];
  onModel: (id: string) => void;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const content = useRef<HTMLDivElement>(null);
  const model = models.find((m) => m.id === column.model);
  const meta = engineMeta(model?.owned_by);
  const reply = lastReply(column.messages);
  const labelFor = (id: string) => models.find((m) => m.id === id)?.label ?? id;

  // Follow the stream, including height changes without new tokens (lazy markdown, fonts).
  useEffect(() => {
    const el = scroller.current;
    const inner = content.current;
    if (!el || !inner) return;
    const observer = new ResizeObserver(() => {
      el.scrollTop = el.scrollHeight;
    });
    observer.observe(inner);
    return () => observer.disconnect();
  }, [column.messages.length > 0]);

  return (
    <section className="relative flex min-h-0 flex-col overflow-hidden rounded-2xl glass">
      <div className={`h-0.5 w-full bg-gradient-to-r ${meta.gradient} opacity-80`} />
      <div className="flex items-center gap-2 border-b border-white/[0.05] px-3 py-2">
        <span
          className={`flex size-6 shrink-0 items-center justify-center rounded-md border font-mono text-xs font-semibold ${meta.border} ${meta.text}`}
        >
          {side}
        </span>
        <ModelPicker models={models} value={column.model} onChange={onModel} />
        <div className="ml-auto">
          <LiveMeter message={reply} model={model} />
        </div>
      </div>
      <div ref={scroller} className="flex-1 overflow-y-auto">
        {column.messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
            <EngineAvatar engine={model?.owned_by} size="lg" />
            <div>
              <div className={`font-medium ${meta.text}`}>{meta.name}</div>
              <div className="text-sm text-zinc-500">
                {model ? splitLabel(model.label).model : "Pick a backend"}
              </div>
            </div>
          </div>
        ) : (
          <div ref={content} className="space-y-6 px-4 pt-5 pb-6">
            {column.messages.map((message) => (
              <MessageView
                key={message.id}
                message={message}
                model={models.find((m) => m.id === message.model)}
                labelFor={labelFor}
                compact
              />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function CompareRow({
  icon,
  name,
  values,
  unit,
  higherIsBetter,
  metas,
}: {
  icon: ReactNode;
  name: string;
  values: [number | null, number | null];
  unit: string;
  higherIsBetter: boolean;
  metas: [ReturnType<typeof engineMeta>, ReturnType<typeof engineMeta>];
}) {
  const [a, b] = values;
  if (a == null || b == null || a <= 0 || b <= 0) return null;
  const max = Math.max(a, b);
  const winner = higherIsBetter ? (a >= b ? 0 : 1) : a <= b ? 0 : 1;
  const ratio = Math.max(a, b) / Math.min(a, b);
  const fmt = (v: number) => (unit === "ms" ? `${Math.round(v)} ms` : `${v.toFixed(1)} ${unit}`);
  return (
    <div className="grid grid-cols-[5.5rem_1fr] items-center gap-x-3 gap-y-1.5">
      <div className="row-span-2 flex items-center gap-1.5 text-xs text-zinc-400">
        {icon}
        {name}
      </div>
      {[a, b].map((value, i) => {
        const meta = metas[i as 0 | 1];
        return (
          <div key={SIDES[i]} className="flex items-center gap-2">
            <span className={`w-4 font-mono text-[11px] ${meta.text}`}>{SIDES[i]}</span>
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/[0.04]">
              <div
                className={`h-full rounded-full bg-gradient-to-r ${meta.gradient} transition-[width] duration-700 ease-out`}
                style={{ width: `${Math.max(4, (value / max) * 100)}%` }}
              />
            </div>
            <span className="w-24 text-right font-mono text-xs text-zinc-300 tabular-nums">
              {fmt(value)}
            </span>
            <span className="w-16">
              {i === winner && ratio >= 1.05 && (
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-1.5 py-0.5 font-mono text-[10px] text-emerald-300">
                  <Trophy className="size-3" />
                  {ratio.toFixed(2)}×
                </span>
              )}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function RoundPanel({
  round,
  streaming,
  models,
  onVote,
}: {
  round: ArenaRound | null;
  streaming: boolean;
  models: ModelInfo[];
  onVote: (vote: Vote) => void;
}) {
  if (streaming) {
    return (
      <div className="flex items-center justify-center gap-2 rounded-2xl glass px-4 py-3 text-sm text-zinc-400">
        <span className="size-1.5 animate-pulse rounded-full bg-violet-400" />
        Racing… metrics update live in each column
      </div>
    );
  }
  if (!round) return null;
  const metas = round.models.map((id) => engineMeta(models.find((m) => m.id === id)?.owned_by)) as [
    ReturnType<typeof engineMeta>,
    ReturnType<typeof engineMeta>,
  ];
  const voteButton = (choice: Vote, label: ReactNode) => (
    <button
      type="button"
      onClick={() => onVote(choice)}
      aria-pressed={round.vote === choice}
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs transition ${
        round.vote === choice
          ? "border-violet-400/40 bg-violet-500/15 text-violet-100"
          : "border-white/10 text-zinc-400 hover:border-white/20 hover:text-zinc-200"
      }`}
    >
      {label}
    </button>
  );
  return (
    <div className="grid animate-fade-up gap-4 rounded-2xl glass px-4 py-3 lg:grid-cols-[1fr_auto] lg:items-center">
      <div className="space-y-2.5">
        <CompareRow
          icon={<Timer className="size-3.5" />}
          name="First token"
          values={round.ttftMs}
          unit="ms"
          higherIsBetter={false}
          metas={metas}
        />
        <CompareRow
          icon={<Zap className="size-3.5" />}
          name="Decode"
          values={round.tokensPerSecond}
          unit="tok/s"
          higherIsBetter
          metas={metas}
        />
      </div>
      <div className="flex flex-col items-start gap-2 lg:items-end">
        <span className="caption">Which answer is better?</span>
        <div className="flex gap-1.5">
          {voteButton(
            "a",
            <>
              <ThumbsUp className="size-3.5" /> A
            </>,
          )}
          {voteButton(
            "tie",
            <>
              <Equal className="size-3.5" /> Tie
            </>,
          )}
          {voteButton(
            "b",
            <>
              <ThumbsUp className="size-3.5" /> B
            </>,
          )}
        </div>
        {!round.fairTiming && (
          <span className="text-[11px] text-amber-300/80">
            Parallel run: both shared the GPU, speeds are lower than isolated.
          </span>
        )}
      </div>
    </div>
  );
}

function Tally({
  label,
  icon,
  values,
  metas,
  title,
}: {
  label: string;
  icon: ReactNode;
  values: [number, number];
  metas: ReturnType<typeof engineMeta>[];
  title: string;
}) {
  return (
    <div title={title} className="flex flex-col items-center px-2.5">
      <span className="flex items-center gap-1 text-[10px] tracking-wide text-zinc-500 uppercase">
        {icon}
        {label}
      </span>
      <span className="font-mono text-sm tabular-nums">
        <span className={metas[0]?.text}>{values[0]}</span>
        <span className="px-1 text-zinc-600">:</span>
        <span className={metas[1]?.text}>{values[1]}</span>
      </span>
    </div>
  );
}

function Scoreboard({ score, models }: { score: Score; models: [ModelInfo?, ModelInfo?] }) {
  if (score.rounds === 0) return null;
  const metas = models.map((m) => engineMeta(m?.owned_by));
  return (
    <div className="hidden items-center divide-x divide-white/[0.06] rounded-xl glass py-1 md:flex">
      <div className="flex flex-col items-center px-2.5" title="Finished rounds for this pair">
        <span className="text-[10px] tracking-wide text-zinc-500 uppercase">Rounds</span>
        <span className="font-mono text-sm text-zinc-200 tabular-nums">{score.rounds}</span>
      </div>
      <Tally
        label="Votes"
        icon={<ThumbsUp className="size-3" />}
        values={score.wins}
        metas={metas}
        title={`Your votes: A ${score.wins[0]}, B ${score.wins[1]}, ties ${score.ties}`}
      />
      <Tally
        label="TTFT"
        icon={<Timer className="size-3" />}
        values={score.fasterFirstToken}
        metas={metas}
        title="Rounds won on time to first token"
      />
      <Tally
        label="Decode"
        icon={<Zap className="size-3" />}
        values={score.fasterDecode}
        metas={metas}
        title="Rounds won on decode speed"
      />
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
  const { columns, setModel } = arena;

  // Default to the first two backends that are online (or any two).
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

  const pair: [ModelInfo?, ModelInfo?] = [
    models.find((m) => m.id === columns[0]?.model),
    models.find((m) => m.id === columns[1]?.model),
  ];
  const online = pair.every((m) => m?.available);
  const empty = columns.every((c) => c.messages.length === 0);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 px-3 pb-3 md:px-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="mr-auto">
          <h2 className="text-[15px] font-semibold tracking-tight">Arena</h2>
          <p className="text-xs text-zinc-500">
            One prompt, two engines, measured live. Vote for the better answer.
          </p>
        </div>
        <Scoreboard score={arena.score} models={pair} />
        <button
          type="button"
          onClick={() => arena.setFairTiming(!arena.fairTiming)}
          role="switch"
          aria-checked={arena.fairTiming}
          title="Run engines one after another so they don't compete for the GPU"
          className="flex items-center gap-2 rounded-xl glass px-3 py-1.5 text-xs text-zinc-300"
        >
          <span
            className={`relative h-4 w-7 rounded-full transition ${arena.fairTiming ? "bg-emerald-500/70" : "bg-zinc-700"}`}
          >
            <span
              className={`absolute top-0.5 size-3 rounded-full bg-white transition-all ${arena.fairTiming ? "left-3.5" : "left-0.5"}`}
            />
          </span>
          Fair timing
        </button>
        <button
          type="button"
          onClick={arena.swap}
          disabled={arena.streaming}
          title="Swap columns"
          aria-label="Swap columns"
          className="rounded-xl glass p-2 text-zinc-400 transition hover:text-zinc-200 disabled:opacity-40"
        >
          <ArrowLeftRight className="size-4" />
        </button>
        <button
          type="button"
          onClick={arena.reset}
          disabled={arena.streaming || empty}
          title="Clear both columns"
          aria-label="Clear arena"
          className="rounded-xl glass p-2 text-zinc-400 transition hover:text-zinc-200 disabled:opacity-40"
        >
          <RotateCcw className="size-4" />
        </button>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 md:grid-cols-2">
        {columns.map((column, i) => (
          <Column
            key={SIDES[i]}
            side={SIDES[i] ?? "A"}
            column={column}
            models={models}
            onModel={(id) => setModel(i, id)}
          />
        ))}
      </div>

      <div className="mx-auto w-full max-w-4xl space-y-3">
        <RoundPanel
          round={arena.round}
          streaming={arena.streaming}
          models={models}
          onVote={(vote) => arena.round && arena.vote(arena.round.id, vote)}
        />
        <Composer
          streaming={arena.streaming}
          disabled={!online}
          disabledReason="Both arena backends must be online"
          thinking={settings.thinking}
          onToggleThinking={onToggleThinking}
          onSend={(text) => void arena.send(text)}
          onStop={arena.stop}
          placeholder="Ask both engines…"
        />
      </div>
    </div>
  );
}
