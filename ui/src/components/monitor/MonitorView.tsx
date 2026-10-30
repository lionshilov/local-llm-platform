import {
  Activity,
  ChartLine,
  CornerDownLeft,
  CornerDownRight,
  ExternalLink,
  Radio,
  Send,
  Timer,
  TriangleAlert,
  WifiOff,
  Zap,
} from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";
import {
  type BackendMetrics,
  type GatewayMetrics,
  type HistoryPoint,
  type RequestCounts,
  DEFAULT_WINDOW_MS,
  POLL_INTERVAL_MS,
  useGatewayMetrics,
} from "../../hooks/useGatewayMetrics";
import { engineMeta, splitLabel } from "../../lib/engines";
import type { ModelInfo } from "../../lib/types";
import { EngineAvatar, StatusDot } from "../EngineAvatar";
import { Sparkline } from "./Sparkline";

const BRAND = "#a78bfa";
/** Sparklines fill in from the right during the first minute, then stretch to 5 minutes. */
const SPARK_SLOTS = 60_000 / POLL_INTERVAL_MS;
const DASH = "—";
const WINDOW_S = DEFAULT_WINDOW_MS / 1000;

/** Engine for a backend the models list doesn't know (yet): "ollama-gguf" → "ollama". */
const engineOf = (id: string) => id.split("-")[0];

function fmtRate(value: number): string {
  if (value === 0) return "0";
  if (value >= 10_000) return `${(value / 1000).toFixed(0)}k`;
  if (value >= 1000) return `${(value / 1000).toFixed(1)}k`;
  if (value >= 100) return value.toFixed(0);
  if (value >= 10) return value.toFixed(1);
  if (value >= 0.01) return value.toFixed(2);
  return "<0.01";
}

/** [number, unit]: milliseconds below a second, seconds above. */
function fmtDuration(seconds: number | null): [string, string] {
  if (seconds === null) return [DASH, ""];
  if (seconds < 1) return [String(Math.round(seconds * 1000)), "ms"];
  return [seconds < 10 ? seconds.toFixed(2) : seconds.toFixed(1), "s"];
}

function fmtPercent(ratio: number | null): string {
  if (ratio === null) return DASH;
  const percent = ratio * 100;
  if (percent === 0) return "0";
  if (percent < 0.1) return "<0.1";
  return percent >= 10 ? percent.toFixed(0) : percent.toFixed(1);
}

const fmtCount = (n: number) => Math.round(n).toLocaleString("en-US");

function fmtSpan(seconds: number): string {
  if (seconds >= 59.5) return `${Math.round(seconds / 60)} min`;
  return `${Math.max(1, Math.round(seconds))} s`;
}

function plural(n: number, word: string): string {
  return `${fmtCount(n)} ${word}${Math.round(n) === 1 ? "" : "s"}`;
}

function useNow(intervalMs: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(timer);
  }, [intervalMs]);
  return now;
}

function LiveIndicator({
  status,
  lastUpdated,
}: {
  status: GatewayMetrics["status"];
  lastUpdated: number | null;
}) {
  const now = useNow(1000);
  const ago = lastUpdated === null ? null : Math.max(0, Math.floor((now - lastUpdated) / 1000));
  const tone = {
    ok: { dot: "bg-emerald-400", text: "text-emerald-200", label: "Live" },
    loading: { dot: "bg-zinc-500", text: "text-zinc-300", label: "Connecting" },
    error: { dot: "bg-rose-400", text: "text-rose-200", label: "Scrape failed" },
  }[status];
  return (
    <div className="flex shrink-0 items-center gap-2 rounded-full glass px-3 py-1.5 text-xs">
      <span className="relative flex size-2">
        {status !== "error" && (
          <span
            className={`absolute inline-flex size-full animate-ping rounded-full opacity-60 ${tone.dot}`}
          />
        )}
        <span className={`relative inline-flex size-2 rounded-full ${tone.dot}`} />
      </span>
      <span className={`font-medium ${tone.text}`}>{tone.label}</span>
      {ago !== null && (
        <span className="font-mono text-zinc-500 tabular-nums">
          · updated {ago === 0 ? "just now" : `${ago}s ago`}
        </span>
      )}
    </div>
  );
}

/** Shown once scrapes have been failing for a few polls; a single blip only flips the pill. */
function StaleBanner({ error, lastUpdated }: { error: string; lastUpdated: number | null }) {
  const now = useNow(1000);
  if (lastUpdated === null || now - lastUpdated < 3 * POLL_INTERVAL_MS) return null;
  return (
    <div className="mt-5 flex animate-fade-up items-center gap-2.5 rounded-xl border border-rose-400/20 bg-rose-500/[0.07] px-4 py-2.5 text-sm text-rose-200">
      <TriangleAlert className="size-4 shrink-0" />
      <span className="min-w-0 truncate">
        Scrapes are failing (<span className="font-mono text-xs">{error}</span>). Showing the
        numbers from {Math.round((now - lastUpdated) / 1000)} s ago; retrying.
      </span>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  unit,
  footer,
  title,
  muted,
  valueClass = "text-zinc-50",
  className = "",
  delay,
  children,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  unit?: string;
  footer: ReactNode;
  title: string;
  muted: boolean;
  valueClass?: string;
  className?: string;
  delay: number;
  children: ReactNode;
}) {
  return (
    <section
      title={title}
      style={{ animationDelay: `${delay}ms` }}
      className={`flex min-w-0 animate-fade-up flex-col rounded-2xl glass p-4 transition-colors hover:border-white/[0.12] ${className}`}
    >
      <h2 className="flex items-center gap-1.5 caption">
        {icon}
        <span className="truncate">{label}</span>
      </h2>
      <div className="mt-2.5 flex min-w-0 items-baseline gap-1.5">
        <span
          className={`font-mono text-[28px] leading-none font-semibold tracking-tight tabular-nums transition-colors ${
            muted ? "text-zinc-500" : valueClass
          }`}
        >
          {value}
        </span>
        {unit && <span className="truncate text-xs text-zinc-500">{unit}</span>}
      </div>
      <div className="mt-3 h-10">{children}</div>
      <div className="mt-2.5 truncate text-[11px] text-zinc-500">{footer}</div>
    </section>
  );
}

interface LatencyRow {
  id: string;
  name: string;
  monogram: string;
  text: string;
  gradient: string;
  value: number;
}

function LatencyBars({ rows }: { rows: LatencyRow[] }) {
  if (rows.length === 0) {
    return (
      <div className="flex h-full items-center">
        <div className="h-1.5 w-full rounded-full bg-white/[0.05]" />
      </div>
    );
  }
  const max = Math.max(...rows.map((r) => r.value));
  return (
    <div className="flex h-full flex-col justify-center gap-1.5">
      {rows.slice(0, 3).map((row) => {
        const [value, unit] = fmtDuration(row.value);
        return (
          <div
            key={row.id}
            className="flex items-center gap-2"
            title={`${row.name}: p95 ${value} ${unit}`}
          >
            <span className={`w-4 font-mono text-[9px] leading-none font-semibold ${row.text}`}>
              {row.monogram}
            </span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/[0.05]">
              <div
                className={`h-full rounded-full bg-gradient-to-r ${row.gradient} transition-[width] duration-700 ease-out`}
                style={{ width: `${Math.max(6, (row.value / max) * 100)}%` }}
              />
            </div>
            <span className="w-12 text-right font-mono text-[10px] leading-none text-zinc-400 tabular-nums">
              {value} {unit}
            </span>
          </div>
        );
      })}
    </div>
  );
}

const OUTCOMES = [
  { key: "ok", label: "ok", bar: "bg-emerald-400/80", text: "text-emerald-300" },
  { key: "errors", label: "error", bar: "bg-rose-400", text: "text-rose-300" },
  { key: "rejected", label: "rejected", bar: "bg-amber-400", text: "text-amber-300" },
  { key: "clientErrors", label: "4xx", bar: "bg-orange-300/80", text: "text-orange-200" },
  { key: "cancelled", label: "cancelled", bar: "bg-zinc-500", text: "text-zinc-400" },
] as const;

/** "1 error", "2 errors"; the other outcome labels don't inflect. */
const outcomeLabel = (outcome: (typeof OUTCOMES)[number], n: number) =>
  outcome.key === "errors" && Math.round(n) !== 1 ? "errors" : outcome.label;

function OutcomeBar({ counts }: { counts: RequestCounts }) {
  const parts = OUTCOMES.filter((o) => counts[o.key] > 0);
  return (
    <div className="flex h-full flex-col justify-center gap-2">
      <div className="flex h-1.5 gap-0.5 overflow-hidden rounded-full bg-white/[0.05]">
        {parts.map((o) => (
          <div
            key={o.key}
            title={`${fmtCount(counts[o.key])} ${outcomeLabel(o, counts[o.key])}`}
            className={`h-full ${o.bar} transition-[flex-grow] duration-700 ease-out`}
            style={{ flexGrow: counts[o.key] }}
          />
        ))}
      </div>
      <div className="flex h-3 gap-x-2.5 overflow-hidden text-[10px] leading-3 text-zinc-500">
        {parts.map((o) => (
          <span key={o.key} className="flex shrink-0 items-center gap-1">
            <span className={`size-1.5 rounded-full ${o.bar}`} />
            <span className="font-mono tabular-nums">{fmtCount(counts[o.key])}</span>
            {outcomeLabel(o, counts[o.key])}
          </span>
        ))}
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  unit,
  title,
  tone = "",
  className = "",
}: {
  label: string;
  value: string;
  unit?: string;
  title: string;
  tone?: string;
  className?: string;
}) {
  return (
    <div title={title} className={`min-w-0 border-white/[0.06] px-3 py-2.5 ${className}`}>
      <dt className="truncate caption">{label}</dt>
      <dd className="mt-1 flex min-w-0 items-baseline gap-1">
        <span
          className={`font-mono text-[15px] font-medium tabular-nums ${value === DASH ? "text-zinc-600" : tone || "text-zinc-100"}`}
        >
          {value}
        </span>
        {unit && value !== DASH && (
          <span className="truncate text-[11px] text-zinc-500">{unit}</span>
        )}
      </dd>
    </div>
  );
}

function OutcomeSummary({ counts, span }: { counts: RequestCounts; span: string }) {
  if (counts.total === 0) return <span>No requests in the last {span}</span>;
  return (
    <span className="flex flex-wrap items-center gap-x-2 gap-y-0.5 font-mono tabular-nums">
      {OUTCOMES.filter((o) => o.key === "ok" || counts[o.key] > 0).map((o, i) => (
        <span key={o.key} className="flex items-center gap-2">
          {i > 0 && <span className="text-zinc-700">·</span>}
          <span className={counts[o.key] > 0 ? o.text : "text-zinc-500"}>
            {fmtCount(counts[o.key])} {outcomeLabel(o, counts[o.key])}
          </span>
        </span>
      ))}
    </span>
  );
}

function BackendCard({
  id,
  model,
  metrics,
  history,
  sharedMax,
  span,
  warm,
  nameFor,
  delay,
}: {
  id: string;
  model: ModelInfo | undefined;
  metrics: BackendMetrics | undefined;
  history: HistoryPoint[];
  sharedMax: number | undefined;
  span: string;
  warm: boolean;
  nameFor: (id: string) => string;
  delay: number;
}) {
  const engine = model?.owned_by ?? engineOf(id);
  const meta = engineMeta(engine);
  const label = splitLabel(model?.label ?? id);
  // Rates and percentiles need a window with traffic; gauges are always current.
  const w = warm && metrics && !metrics.idle ? metrics : null;
  const inFlight = metrics?.inFlight ?? 0;
  const queued = metrics?.queueDepth ?? 0;
  const series = history.map((p) => p.backends[id]?.outputTokensPerSecond ?? 0);
  const historySeconds = Math.max(
    SPARK_SLOTS * (POLL_INTERVAL_MS / 1000),
    ((history.at(-1)?.time ?? 0) - (history[0]?.time ?? 0)) / 1000,
  );
  const [p50, p50Unit] = fmtDuration(w?.ttftP50 ?? null);
  const [p95, p95Unit] = fmtDuration(w?.ttftP95 ?? null);
  const errorRatio = w?.errorRatio ?? null;
  const reroutes = [
    ...Object.entries(w?.fallbackTargets ?? {}).map(([other, n]) => ({ other, n, out: true })),
    ...Object.entries(w?.fallbackSources ?? {}).map(([other, n]) => ({ other, n, out: false })),
  ].filter((r) => r.n > 0);

  return (
    <article
      style={{ animationDelay: `${delay}ms` }}
      className={`@container relative flex animate-fade-up flex-col overflow-hidden rounded-2xl glass transition-opacity duration-500 ${
        !w && inFlight === 0 && model?.available === false ? "opacity-60 hover:opacity-100" : ""
      }`}
    >
      <div
        className={`h-0.5 w-full bg-gradient-to-r ${meta.gradient} transition-opacity duration-500 ${w ? "opacity-90" : "opacity-40"}`}
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-36 transition-opacity duration-700"
        style={{
          background: `radial-gradient(420px 140px at 10% 0%, ${meta.color}1f, transparent 70%)`,
          opacity: w || inFlight > 0 ? 1 : 0.35,
        }}
      />

      <div className="relative flex flex-1 flex-col gap-4 p-4 sm:p-5">
        <header className="flex items-start gap-3">
          <EngineAvatar engine={engine} size="lg" pulse={inFlight > 0} />
          <div className="min-w-0 flex-1">
            <h3 className="truncate font-medium text-zinc-100">{label.model}</h3>
            <p className="truncate text-xs text-zinc-500">
              <span className={meta.text}>{label.engine || meta.name}</span>
              <span className="text-zinc-700"> · </span>
              <span className="font-mono">{id}</span>
            </p>
          </div>
          {model && (
            <span
              className={`flex shrink-0 items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] ${
                model.available
                  ? "border-emerald-400/20 bg-emerald-500/[0.07] text-emerald-200"
                  : "border-white/[0.06] text-zinc-500"
              }`}
            >
              <StatusDot up={model.available} />
              {model.available ? "online" : "offline"}
            </span>
          )}
        </header>

        <div className="flex items-end justify-between gap-4">
          <div className="min-w-0">
            <div className="caption">Throughput</div>
            <div className="mt-1 flex items-baseline gap-1.5">
              <span
                className={`font-mono text-2xl leading-none font-semibold tracking-tight tabular-nums ${w ? "text-zinc-50" : "text-zinc-600"}`}
              >
                {w ? fmtRate(w.outputTokensPerSecond) : DASH}
              </span>
              <span className="text-xs text-zinc-500">tok/s</span>
            </div>
          </div>
          <dl className="flex shrink-0 gap-4 text-right sm:gap-5">
            <div>
              <dt className="caption">Requests</dt>
              <dd className="mt-1 font-mono text-sm text-zinc-200 tabular-nums">
                {w ? fmtRate(w.requestsPerSecond) : DASH}
                <span className="ml-1 font-sans text-[11px] text-zinc-500">req/s</span>
              </dd>
            </div>
            <div>
              <dt className="caption">In flight</dt>
              <dd className="mt-1 font-mono text-sm text-zinc-200 tabular-nums">
                {fmtCount(inFlight)}
              </dd>
            </div>
            <div>
              <dt className="caption">Queued</dt>
              <dd
                className={`mt-1 font-mono text-sm tabular-nums ${queued > 0 ? "text-amber-300" : "text-zinc-200"}`}
              >
                {fmtCount(queued)}
              </dd>
            </div>
          </dl>
        </div>

        <div>
          <Sparkline
            data={series}
            color={meta.color}
            slots={SPARK_SLOTS}
            max={sharedMax}
            className="h-14 w-full"
            label={`${label.engine || meta.name} output tokens per second over the last ${fmtSpan(historySeconds)}`}
          />
          <div className="mt-1 flex justify-between font-mono text-[10px] text-zinc-600">
            <span>−{fmtSpan(historySeconds)}</span>
            <span>now</span>
          </div>
        </div>

        <dl className="grid grid-cols-2 overflow-hidden rounded-xl border border-white/[0.06] bg-white/[0.015] @md:grid-cols-4">
          <Stat
            label="TTFT p50"
            value={p50}
            unit={p50Unit}
            title="Median time to first token in the window (queueing + prefill)"
            className="border-r border-b @md:border-b-0"
          />
          <Stat
            label="TTFT p95"
            value={p95}
            unit={p95Unit}
            title="95th percentile time to first token in the window"
            className="border-b @md:border-r @md:border-b-0"
          />
          <Stat
            label="Decode"
            value={w?.decodeTokensPerSecond ? fmtRate(w.decodeTokensPerSecond) : DASH}
            unit="tok/s"
            title="Decode speed one user sees: 1 / median time per output token"
            className="border-r"
          />
          <Stat
            label="Errors"
            value={fmtPercent(errorRatio)}
            unit="%"
            title="Server-side errors / all attempts (cancelled and client 4xx excluded)"
            tone={errorRatio ? "text-rose-300" : ""}
          />
        </dl>

        <footer className="mt-auto flex flex-wrap items-center justify-between gap-x-4 gap-y-2 text-xs text-zinc-500">
          {warm ? (
            <OutcomeSummary counts={w?.requests ?? EMPTY_COUNTS} span={span} />
          ) : (
            <span>Measuring…</span>
          )}
          {reroutes.length > 0 && (
            <span className="flex flex-wrap items-center gap-1.5">
              {reroutes.map(({ other, n, out }) => (
                <span
                  key={`${out}-${other}`}
                  title={
                    out
                      ? `${plural(n, "request")} this backend could not serve, re-routed to ${other}`
                      : `${plural(n, "request")} taken over from ${other}`
                  }
                  className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] ${
                    out
                      ? "border-amber-400/20 bg-amber-500/[0.08] text-amber-200"
                      : "border-white/[0.08] bg-white/[0.03] text-zinc-300"
                  }`}
                >
                  {out ? (
                    <CornerDownRight className="size-3" />
                  ) : (
                    <CornerDownLeft className="size-3" />
                  )}
                  <span className="font-mono tabular-nums">{fmtCount(n)}</span>
                  {out ? "to" : "from"} {nameFor(other)}
                </span>
              ))}
            </span>
          )}
        </footer>
      </div>
    </article>
  );
}

const EMPTY_COUNTS: RequestCounts = {
  total: 0,
  ok: 0,
  errors: 0,
  rejected: 0,
  cancelled: 0,
  clientErrors: 0,
};

function ErrorCard({ error }: { error: string }) {
  return (
    <div className="flex animate-fade-up flex-col items-center gap-3 rounded-2xl border border-rose-400/20 bg-rose-500/[0.06] px-6 py-12 text-center">
      <span className="flex size-11 items-center justify-center rounded-xl bg-rose-500/15 text-rose-300">
        <WifiOff className="size-5" />
      </span>
      <div>
        <h2 className="font-medium text-zinc-100">Can't read the gateway's metrics</h2>
        <p className="mt-1 font-mono text-xs text-rose-200/80">{error}</p>
      </div>
      <p className="max-w-md text-sm text-zinc-400">
        Start the gateway with <code className="font-mono text-zinc-200">make gateway</code>. This
        page retries every {POLL_INTERVAL_MS / 1000} s and picks up as soon as{" "}
        <code className="font-mono text-zinc-200">/metrics</code> answers.
      </p>
    </div>
  );
}

function IdleHint({ span }: { span: string }) {
  return (
    <div className="flex animate-fade-up items-center gap-4 rounded-2xl border border-dashed border-white/[0.08] px-5 py-4">
      <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-violet-500/10 text-violet-300">
        <Send className="size-4" />
      </span>
      <p className="text-sm text-zinc-400">
        <span className="font-medium text-zinc-200">No traffic in the last {span}</span> — send a
        message in Chat or run <code className="font-mono text-zinc-200">make bench</code>; numbers
        show up within {POLL_INTERVAL_MS / 1000} s.
      </p>
    </div>
  );
}

export function MonitorView({ models }: { models: ModelInfo[] }) {
  const metrics = useGatewayMetrics();
  const { totals: t, backends, history, status, error, windowSeconds } = metrics;

  const nameFor = (id: string) => {
    const model = models.find((m) => m.id === id);
    return model ? splitLabel(model.label).engine || id : id;
  };
  const byId = new Map(backends.map((b) => [b.backend, b]));
  const rows = [
    ...models.map((model) => ({ id: model.id, model, metrics: byId.get(model.id) })),
    ...backends
      .filter((b) => !models.some((m) => m.id === b.backend))
      .map((b) => ({ id: b.backend, model: undefined, metrics: b })),
  ];

  const peak = Math.max(
    0,
    ...history.flatMap((p) => Object.values(p.backends).map((b) => b.outputTokensPerSecond)),
  );
  const sharedMax = peak > 0 ? peak * 1.15 : undefined;
  const warm = windowSeconds > 0;
  const span = warm ? fmtSpan(windowSeconds) : "minute";
  const quiet = !t || !warm || t.idle;
  const online = models.filter((m) => m.available).length;

  const latencyRows: LatencyRow[] = backends
    .flatMap((b) => {
      if (b.ttftP95 === null) return [];
      const model = models.find((m) => m.id === b.backend);
      const meta = engineMeta(model?.owned_by ?? engineOf(b.backend));
      return [
        {
          id: b.backend,
          name: nameFor(b.backend),
          monogram: meta.monogram,
          text: meta.text,
          gradient: meta.gradient,
          value: b.ttftP95,
        },
      ];
    })
    .sort((a, b) => b.value - a.value);

  const [ttftValue, ttftUnit] = fmtDuration(warm ? (t?.ttftP95 ?? null) : null);
  const [ttftP50, ttftP50Unit] = fmtDuration(warm ? (t?.ttftP50 ?? null) : null);
  const errorRatio = warm ? (t?.errorRatio ?? null) : null;

  return (
    <div className="@container mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:py-8">
      <header className="flex animate-fade-up flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-gradient text-2xl font-semibold tracking-tight sm:text-3xl">
            Live metrics
          </h1>
          <p className="mt-1.5 text-sm text-zinc-500">
            Scraped from the gateway's <code className="font-mono text-zinc-400">/metrics</code>{" "}
            every {POLL_INTERVAL_MS / 1000} s · last {WINDOW_S} s window
            {warm && windowSeconds < WINDOW_S - POLL_INTERVAL_MS / 1000 && (
              <span className="text-zinc-600"> ({fmtSpan(windowSeconds)} so far)</span>
            )}
          </p>
        </div>
        <LiveIndicator status={status} lastUpdated={metrics.lastUpdated} />
      </header>

      {status === "error" && error && t && (
        <StaleBanner error={error} lastUpdated={metrics.lastUpdated} />
      )}

      {status === "error" && error && !t ? (
        <div className="mt-6">
          <ErrorCard error={error} />
        </div>
      ) : (
        <>
          <div className="mt-6 grid grid-cols-2 gap-3 @3xl:grid-cols-6 @5xl:grid-cols-5">
            <StatCard
              icon={<Zap className="size-3.5" />}
              label="Throughput"
              value={warm && t ? fmtRate(t.outputTokensPerSecond) : DASH}
              unit="tok/s"
              muted={quiet}
              delay={0}
              className="col-span-2 @3xl:col-span-2 @5xl:col-span-1"
              title="rate(llm_gateway_output_tokens_total), all backends. Tokens are counted when a response finishes."
              footer={
                <>
                  prompt{" "}
                  <span className="font-mono text-zinc-400 tabular-nums">
                    {warm && t ? fmtRate(t.promptTokensPerSecond) : DASH}
                  </span>{" "}
                  tok/s
                </>
              }
            >
              <Sparkline
                data={history.map((p) => p.outputTokensPerSecond)}
                color={BRAND}
                slots={SPARK_SLOTS}
                className="size-full"
                label={`Total output tokens per second, now ${t ? fmtRate(t.outputTokensPerSecond) : "unknown"}`}
              />
            </StatCard>

            <StatCard
              icon={<Activity className="size-3.5" />}
              label="Requests"
              value={warm && t ? fmtRate(t.requestsPerSecond) : DASH}
              unit="req/s"
              muted={quiet}
              delay={40}
              className="@3xl:col-span-2 @5xl:col-span-1"
              title="rate(llm_gateway_requests_total), every outcome, including attempts that fell back."
              footer={
                warm && t
                  ? `${plural(t.requests.total, "request")} in the last ${span}`
                  : "warming up…"
              }
            >
              <Sparkline
                data={history.map((p) => p.requestsPerSecond)}
                color={BRAND}
                slots={SPARK_SLOTS}
                className="size-full"
                label={`Requests per second, now ${t ? fmtRate(t.requestsPerSecond) : "unknown"}`}
              />
            </StatCard>

            <StatCard
              icon={<Radio className="size-3.5" />}
              label="Active streams"
              value={t ? fmtCount(t.inFlight) : DASH}
              unit="in flight"
              muted={!t || t.inFlight === 0}
              delay={80}
              className="@3xl:col-span-2 @5xl:col-span-1"
              title="llm_gateway_in_flight_requests: streams being relayed right now."
              footer={
                t && t.queueDepth > 0 ? (
                  <span className="text-amber-300">
                    {fmtCount(t.queueDepth)} waiting for a slot
                  </span>
                ) : (
                  "nothing queued"
                )
              }
            >
              <Sparkline
                data={history.map((p) => p.inFlight)}
                color={BRAND}
                slots={SPARK_SLOTS}
                className="size-full"
                label={`Streams in flight, now ${t ? fmtCount(t.inFlight) : "unknown"}`}
              />
            </StatCard>

            <StatCard
              icon={<Timer className="size-3.5" />}
              label="TTFT p95"
              value={ttftValue}
              unit={ttftUnit}
              muted={quiet}
              delay={120}
              className="@3xl:col-span-3 @5xl:col-span-1"
              title="histogram_quantile(0.95) of time to first token over the window, all backends. Bars: p95 per backend."
              footer={
                warm && t?.slowest ? (
                  <>
                    p50{" "}
                    <span className="font-mono text-zinc-400 tabular-nums">
                      {ttftP50} {ttftP50Unit}
                    </span>{" "}
                    · slowest {nameFor(t.slowest.backend)}
                  </>
                ) : (
                  "no first tokens in the window"
                )
              }
            >
              <LatencyBars rows={warm ? latencyRows : []} />
            </StatCard>

            <StatCard
              icon={<TriangleAlert className="size-3.5" />}
              label="Error ratio"
              value={fmtPercent(errorRatio)}
              unit={errorRatio === null ? "" : "%"}
              muted={quiet}
              valueClass={
                errorRatio === null || errorRatio === 0
                  ? "text-zinc-50"
                  : errorRatio < 0.05
                    ? "text-amber-200"
                    : "text-rose-300"
              }
              delay={160}
              className="@3xl:col-span-3 @5xl:col-span-1"
              title="upstream_error + upstream_unavailable + upstream_5xx over all attempts. Cancelled requests and client 4xx are not errors."
              footer={
                warm && t && t.requests.total > 0 ? (
                  <>
                    {fmtCount(t.requests.errors)} of {plural(t.requests.total, "attempt")}
                    {t.fallbacks > 0 && <> · {plural(t.fallbacks, "fallback")}</>}
                  </>
                ) : (
                  "no requests in the window"
                )
              }
            >
              <OutcomeBar counts={warm && t ? t.requests : EMPTY_COUNTS} />
            </StatCard>
          </div>

          {warm && t?.idle && (
            <div className="mt-4">
              <IdleHint span={span} />
            </div>
          )}

          <section className="mt-8">
            <div className="mb-3 flex items-baseline justify-between gap-3">
              <h2 className="caption">Backends</h2>
              {models.length > 0 && (
                <span className="text-xs text-zinc-500">
                  <span className="font-mono text-zinc-300 tabular-nums">{online}</span> of{" "}
                  {models.length} online
                </span>
              )}
            </div>
            <div className="grid grid-cols-1 gap-4 @4xl:grid-cols-2">
              {rows.length === 0
                ? [0, 1].map((i) => (
                    <div key={i} className="h-[22rem] animate-pulse rounded-2xl glass" />
                  ))
                : rows.map((row, i) => (
                    <BackendCard
                      key={row.id}
                      id={row.id}
                      model={row.model}
                      metrics={row.metrics}
                      history={history}
                      sharedMax={sharedMax}
                      span={span}
                      warm={warm}
                      nameFor={nameFor}
                      delay={200 + i * 50}
                    />
                  ))}
            </div>
          </section>
        </>
      )}

      <footer className="mt-10 flex flex-col gap-2 border-t border-white/[0.06] pt-5 text-xs text-zinc-500 sm:flex-row sm:items-center sm:justify-between">
        <p className="max-w-xl">
          Rates and percentiles are computed in the browser from consecutive scrapes, the way
          PromQL's <code className="font-mono text-zinc-400">rate()</code> and{" "}
          <code className="font-mono text-zinc-400">histogram_quantile()</code> do. The gateway
          records requests, tokens and latencies when a stream finishes.
        </p>
        <div className="flex shrink-0 flex-wrap items-center gap-x-4 gap-y-1">
          <a
            href="/metrics"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 transition-colors hover:text-zinc-200"
          >
            <ExternalLink className="size-3.5" />
            <span>
              Raw <code className="font-mono">/metrics</code>
            </span>
          </a>
          <a
            href="http://127.0.0.1:3300"
            target="_blank"
            rel="noreferrer"
            title="Long-term history: start Prometheus + Grafana with make up"
            className="inline-flex items-center gap-1 transition-colors hover:text-zinc-200"
          >
            <ChartLine className="size-3.5" />
            <span>
              Grafana · <code className="font-mono">make up</code> · :3300
            </span>
          </a>
        </div>
      </footer>
    </div>
  );
}

export default MonitorView;
