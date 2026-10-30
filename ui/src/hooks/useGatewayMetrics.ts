import { useEffect, useMemo, useState } from "react";
import {
  type Histogram,
  type Snapshot,
  createSnapshot,
  histogramIncrease,
  histogramQuantile,
  increase,
  mergeHistograms,
  parsePrometheus,
  select,
  sum,
  sumBy,
  sumHistogramsBy,
} from "../lib/prometheus";

export const POLL_INTERVAL_MS = 2_000;
export const DEFAULT_WINDOW_MS = 60_000;
export const HISTORY_MS = 5 * 60_000;
/** Sparkline points are rates over this trailing span, like Grafana's $__rate_interval. */
export const SMOOTHING_MS = 10_000;
const REQUEST_TIMEOUT_MS = 5_000;
/** Polls drift by a few ms, so a "60 s" window may reach back up to half a poll further. */
const SLACK_MS = POLL_INTERVAL_MS / 2;

const METRIC = {
  requests: "llm_gateway_requests_total",
  inFlight: "llm_gateway_in_flight_requests",
  queueDepth: "llm_gateway_queue_depth",
  fallbacks: "llm_gateway_fallbacks_total",
  ttft: "llm_gateway_time_to_first_token_seconds",
  tpot: "llm_gateway_time_per_output_token_seconds",
  promptTokens: "llm_gateway_prompt_tokens_total",
  outputTokens: "llm_gateway_output_tokens_total",
} as const;

export interface RequestCounts {
  total: number;
  ok: number;
  /** Server-side failures: upstream_error, upstream_unavailable, upstream_5xx. */
  errors: number;
  /** Turned away by admission control (429). */
  rejected: number;
  /** Client went away mid-stream. */
  cancelled: number;
  /** Upstream 4xx passed through: the request was bad, not the server. */
  clientErrors: number;
}

export interface TrafficStats {
  requestsPerSecond: number;
  requests: RequestCounts;
  /** errors / total, like Grafana's server-side error ratio; null without requests. */
  errorRatio: number | null;
  /** Completion tokens per second; counted when each response finishes. */
  outputTokensPerSecond: number;
  promptTokensPerSecond: number;
  /** Seconds, from the TTFT histogram's bucket increases over the window. */
  ttftP50: number | null;
  ttftP95: number | null;
  /** Median time per output token (s) and its inverse, the decode speed one user sees. */
  tpotP50: number | null;
  decodeTokensPerSecond: number | null;
  /** Streams being relayed right now (gauge). */
  inFlight: number;
  /** Requests waiting for an admission slot right now (gauge). */
  queueDepth: number;
  /** No requests in the window and nothing in flight or queued. */
  idle: boolean;
}

export interface BackendMetrics extends TrafficStats {
  backend: string;
  /** Requests this backend could not take that were re-routed elsewhere. */
  fallbacksOut: number;
  /** Requests this backend took over from another one. */
  fallbacksIn: number;
  /** fallbacksOut by target backend. */
  fallbackTargets: Record<string, number>;
  /** fallbacksIn by source backend. */
  fallbackSources: Record<string, number>;
}

export interface GatewayTotals extends TrafficStats {
  fallbacks: number;
  /** The backend with the highest TTFT p95 in the window. */
  slowest: { backend: string; ttftP95: number } | null;
}

export interface SeriesPoint {
  outputTokensPerSecond: number;
  requestsPerSecond: number;
  inFlight: number;
}

export interface HistoryPoint extends SeriesPoint {
  time: number;
  backends: Record<string, SeriesPoint>;
}

export interface WindowMetrics {
  totals: GatewayTotals;
  backends: BackendMetrics[];
  /** Seconds actually covered; shorter than the window right after mounting. */
  windowSeconds: number;
}

export interface GatewayMetrics {
  /** "error" means the latest scrape failed; the last good numbers are still returned. */
  status: "loading" | "ok" | "error";
  error: string | null;
  totals: GatewayTotals | null;
  backends: BackendMetrics[];
  history: HistoryPoint[];
  /** Time of the latest successful scrape (ms since the epoch). */
  lastUpdated: number | null;
  windowSeconds: number;
}

export type OutcomeClass = "ok" | "error" | "rejected" | "cancelled" | "client_error" | "other";

export function classifyOutcome(outcome: string): OutcomeClass {
  if (outcome === "ok") return "ok";
  if (outcome === "cancelled") return "cancelled";
  if (outcome === "rejected") return "rejected";
  if (outcome === "upstream_error" || outcome === "upstream_unavailable") return "error";
  if (/^upstream_5\d\d$/.test(outcome)) return "error";
  if (/^upstream_4\d\d$/.test(outcome)) return "client_error";
  return "other";
}

const COUNT_FIELD: Record<OutcomeClass, keyof RequestCounts | null> = {
  ok: "ok",
  error: "errors",
  rejected: "rejected",
  cancelled: "cancelled",
  client_error: "clientErrors",
  other: null,
};

function emptyCounts(): RequestCounts {
  return { total: 0, ok: 0, errors: 0, rejected: 0, cancelled: 0, clientErrors: 0 };
}

function addCounts(a: RequestCounts, b: RequestCounts): RequestCounts {
  return {
    total: a.total + b.total,
    ok: a.ok + b.ok,
    errors: a.errors + b.errors,
    rejected: a.rejected + b.rejected,
    cancelled: a.cancelled + b.cancelled,
    clientErrors: a.clientErrors + b.clientErrors,
  };
}

/**
 * The earliest snapshot at most `spanMs` older than the newest one. That is the newest
 * snapshot itself when nothing else is recent enough (first poll, or right after the tab
 * was hidden for longer than the span): the window is then empty instead of stretching
 * over the gap. Shortly after mounting this is the first snapshot ("since first scrape").
 */
export function windowBase(snapshots: readonly Snapshot[], spanMs: number): Snapshot | null {
  const latest = snapshots.at(-1);
  if (!latest) return null;
  const from = latest.time - spanMs - SLACK_MS;
  return snapshots.find((snapshot) => snapshot.time >= from) ?? latest;
}

function sumValues(map: ReadonlyMap<string, number>): number {
  let total = 0;
  for (const value of map.values()) total += value;
  return total;
}

function quantiles(histogram: Histogram | null | undefined) {
  const buckets = histogram?.buckets ?? [];
  return { p50: histogramQuantile(0.5, buckets), p95: histogramQuantile(0.95, buckets) };
}

/** Everything the dashboard shows, derived from the counters' growth between two scrapes. */
export function deriveWindow(prev: Snapshot, curr: Snapshot): WindowMetrics {
  const seconds = Math.max(0, (curr.time - prev.time) / 1000);
  const perSecond = (value: number) => (seconds > 0 ? value / seconds : 0);

  const requests = increase(prev, curr, METRIC.requests);
  const outputTokens = sumBy(increase(prev, curr, METRIC.outputTokens), "backend");
  const promptTokens = sumBy(increase(prev, curr, METRIC.promptTokens), "backend");
  const inFlight = sumBy(select(curr, METRIC.inFlight), "backend");
  const queueDepth = sumBy(select(curr, METRIC.queueDepth), "backend");
  const fallbacks = increase(prev, curr, METRIC.fallbacks);
  const ttftAll = histogramIncrease(prev, curr, METRIC.ttft);
  const tpotAll = histogramIncrease(prev, curr, METRIC.tpot);
  const ttft = sumHistogramsBy(ttftAll, "backend");
  const tpot = sumHistogramsBy(tpotAll, "backend");

  // Every configured backend has these series from startup, in config order.
  const names = new Set<string>();
  for (const name of [METRIC.requests, METRIC.inFlight, METRIC.outputTokens, METRIC.queueDepth]) {
    for (const { labels } of select(curr, name)) {
      if (labels.backend) names.add(labels.backend);
    }
  }

  const countsBy = new Map<string, RequestCounts>();
  for (const sample of requests) {
    const backend = sample.labels.backend ?? "";
    const counts = countsBy.get(backend) ?? emptyCounts();
    const field = COUNT_FIELD[classifyOutcome(sample.labels.outcome ?? "")];
    counts.total += sample.value;
    if (field) counts[field] += sample.value;
    countsBy.set(backend, counts);
  }

  const stats = (input: {
    counts: RequestCounts;
    outputTokens: number;
    promptTokens: number;
    ttft: Histogram | null | undefined;
    tpot: Histogram | null | undefined;
    inFlight: number;
    queueDepth: number;
  }): TrafficStats => {
    const { counts, inFlight: flying, queueDepth: queued } = input;
    const ttftQ = quantiles(input.ttft);
    const tpotP50 = quantiles(input.tpot).p50;
    return {
      requestsPerSecond: perSecond(counts.total),
      requests: counts,
      errorRatio: counts.total > 0 ? counts.errors / counts.total : null,
      outputTokensPerSecond: perSecond(input.outputTokens),
      promptTokensPerSecond: perSecond(input.promptTokens),
      ttftP50: ttftQ.p50,
      ttftP95: ttftQ.p95,
      tpotP50,
      decodeTokensPerSecond: tpotP50 && tpotP50 > 0 ? 1 / tpotP50 : null,
      inFlight: flying,
      queueDepth: queued,
      idle: counts.total === 0 && flying === 0 && queued === 0,
    };
  };

  const backends: BackendMetrics[] = [...names].map((backend) => {
    const fallbackTargets: Record<string, number> = {};
    const fallbackSources: Record<string, number> = {};
    for (const { labels, value } of fallbacks) {
      const from = labels.from_backend ?? "";
      const to = labels.to_backend ?? "";
      if (from === backend) fallbackTargets[to] = (fallbackTargets[to] ?? 0) + value;
      if (to === backend) fallbackSources[from] = (fallbackSources[from] ?? 0) + value;
    }
    return {
      backend,
      ...stats({
        counts: countsBy.get(backend) ?? emptyCounts(),
        outputTokens: outputTokens.get(backend) ?? 0,
        promptTokens: promptTokens.get(backend) ?? 0,
        ttft: ttft.get(backend),
        tpot: tpot.get(backend),
        inFlight: inFlight.get(backend) ?? 0,
        queueDepth: queueDepth.get(backend) ?? 0,
      }),
      fallbacksOut: Object.values(fallbackTargets).reduce((a, b) => a + b, 0),
      fallbacksIn: Object.values(fallbackSources).reduce((a, b) => a + b, 0),
      fallbackTargets,
      fallbackSources,
    };
  });

  let slowest: GatewayTotals["slowest"] = null;
  for (const b of backends) {
    if (b.ttftP95 !== null && (slowest === null || b.ttftP95 > slowest.ttftP95)) {
      slowest = { backend: b.backend, ttftP95: b.ttftP95 };
    }
  }
  const totals: GatewayTotals = {
    ...stats({
      counts: [...countsBy.values()].reduce(addCounts, emptyCounts()),
      outputTokens: sumValues(outputTokens),
      promptTokens: sumValues(promptTokens),
      ttft: mergeHistograms(ttftAll),
      tpot: mergeHistograms(tpotAll),
      inFlight: sumValues(inFlight),
      queueDepth: sumValues(queueDepth),
    }),
    fallbacks: sum(fallbacks),
    slowest,
  };
  return { totals, backends, windowSeconds: seconds };
}

function seriesPoint(prev: Snapshot, curr: Snapshot): HistoryPoint {
  const seconds = (curr.time - prev.time) / 1000;
  const perSecond = (value: number) => (seconds > 0 ? value / seconds : 0);
  const tokens = sumBy(increase(prev, curr, METRIC.outputTokens), "backend");
  const requests = sumBy(increase(prev, curr, METRIC.requests), "backend");
  const inFlight = sumBy(select(curr, METRIC.inFlight), "backend");
  const backends: Record<string, SeriesPoint> = {};
  for (const backend of new Set([...tokens.keys(), ...requests.keys(), ...inFlight.keys()])) {
    backends[backend] = {
      outputTokensPerSecond: perSecond(tokens.get(backend) ?? 0),
      requestsPerSecond: perSecond(requests.get(backend) ?? 0),
      inFlight: inFlight.get(backend) ?? 0,
    };
  }
  const all = Object.values(backends);
  return {
    time: curr.time,
    outputTokensPerSecond: all.reduce((acc, p) => acc + p.outputTokensPerSecond, 0),
    requestsPerSecond: all.reduce((acc, p) => acc + p.requestsPerSecond, 0),
    inFlight: all.reduce((acc, p) => acc + p.inFlight, 0),
    backends,
  };
}

export interface MetricsBuffer {
  snapshots: Snapshot[];
  history: HistoryPoint[];
}

export const EMPTY_BUFFER: MetricsBuffer = { snapshots: [], history: [] };

/**
 * Add a scrape to the rolling buffer: keep HISTORY_MS of snapshots and one sparkline
 * point per scrape (rates over the trailing SMOOTHING_MS, so a single long response
 * finishing doesn't draw a spike as tall as the chart).
 */
export function pushSnapshot(buffer: MetricsBuffer, snapshot: Snapshot): MetricsBuffer {
  const from = snapshot.time - HISTORY_MS;
  const snapshots = [
    ...buffer.snapshots.filter((s) => s.time >= from && s.time < snapshot.time),
    snapshot,
  ];
  const base = windowBase(snapshots, SMOOTHING_MS);
  const history = buffer.history.filter((p) => p.time >= from && p.time < snapshot.time);
  if (base && base !== snapshot) history.push(seriesPoint(base, snapshot));
  return { snapshots, history };
}

function isGatewaySample(sample: { name: string }): boolean {
  return sample.name.startsWith("llm_gateway_");
}

/**
 * Scrape the gateway's Prometheus endpoint every 2 s while mounted and the tab is visible,
 * and derive per-backend live numbers over a sliding window (default: the last 60 s).
 */
export function useGatewayMetrics({
  url = "/metrics",
  windowMs = DEFAULT_WINDOW_MS,
}: { url?: string; windowMs?: number } = {}): GatewayMetrics {
  const [buffer, setBuffer] = useState<MetricsBuffer>(EMPTY_BUFFER);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let disposed = false;
    let running = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | null = null;

    const visible = () => document.visibilityState === "visible";

    const poll = async () => {
      if (running || disposed) return;
      running = true;
      clearTimeout(timer);
      controller = new AbortController();
      const current = controller;
      let timedOut = false;
      const timeout = setTimeout(() => {
        timedOut = true;
        current.abort();
      }, REQUEST_TIMEOUT_MS);
      try {
        const response = await fetch(url, { signal: current.signal, cache: "no-store" });
        if (!response.ok) throw new Error(`${url} returned HTTP ${response.status}`);
        const samples = parsePrometheus(await response.text()).samples.filter(isGatewaySample);
        if (samples.length === 0) throw new Error(`${url} has no llm_gateway_* metrics`);
        const snapshot = createSnapshot(samples, Date.now());
        if (disposed) return;
        setBuffer((prev) => pushSnapshot(prev, snapshot));
        setError(null);
      } catch (e) {
        if (disposed) return;
        // fetch() rejects with a TypeError when the connection itself fails.
        setError(
          timedOut
            ? `${url} did not answer within ${REQUEST_TIMEOUT_MS / 1000} s`
            : e instanceof TypeError
              ? "Gateway unreachable"
              : e instanceof Error
                ? e.message
                : String(e),
        );
      } finally {
        clearTimeout(timeout);
        running = false;
        if (!disposed && visible()) timer = setTimeout(() => void poll(), POLL_INTERVAL_MS);
      }
    };

    // Hidden tabs stop polling; coming back scrapes at once and resumes the cadence.
    const onVisibilityChange = () => {
      if (visible()) void poll();
      else clearTimeout(timer);
    };

    document.addEventListener("visibilitychange", onVisibilityChange);
    if (visible()) void poll();
    return () => {
      disposed = true;
      clearTimeout(timer);
      controller?.abort();
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [url]);

  const derived = useMemo(() => {
    const latest = buffer.snapshots.at(-1);
    const base = windowBase(buffer.snapshots, windowMs);
    return latest && base ? deriveWindow(base, latest) : null;
  }, [buffer.snapshots, windowMs]);

  return {
    status: error ? "error" : derived ? "ok" : "loading",
    error,
    totals: derived?.totals ?? null,
    backends: derived?.backends ?? [],
    history: buffer.history,
    lastUpdated: buffer.snapshots.at(-1)?.time ?? null,
    windowSeconds: derived?.windowSeconds ?? 0,
  };
}
