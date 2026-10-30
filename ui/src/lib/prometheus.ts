/**
 * A small toolkit for the Prometheus text exposition format (version 0.0.4): parse a
 * scrape, then turn two scrapes into the numbers PromQL would give for the same interval
 * (counter increases and rates, histogram quantiles, sums by label). Pure, no I/O.
 */

export type Labels = Readonly<Record<string, string>>;

export interface Sample {
  name: string;
  labels: Labels;
  value: number;
  /** Milliseconds since the epoch, when the exporter wrote one (most don't). */
  timestamp?: number;
}

export type MetricType = "counter" | "gauge" | "histogram" | "summary" | "untyped";

export interface MetricMetadata {
  type?: MetricType;
  help?: string;
}

export interface Exposition {
  samples: Sample[];
  /** `# HELP` and `# TYPE` lines, keyed by metric family name. */
  metadata: Map<string, MetricMetadata>;
}

const METRIC_NAME = /[a-zA-Z_:][a-zA-Z0-9_:]*/y;
const LABEL_NAME = /[a-zA-Z_][a-zA-Z0-9_]*/y;
const METADATA_LINE = /^#\s+(HELP|TYPE)\s+([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\s+(.*))?$/;
const METRIC_TYPES: ReadonlySet<string> = new Set([
  "counter",
  "gauge",
  "histogram",
  "summary",
  "untyped",
]);

/** Label sets use a null prototype so a label called `__proto__` is just a label. */
function emptyLabels(): Record<string, string> {
  return Object.create(null) as Record<string, string>;
}

/** Sample values follow Go's ParseFloat: `NaN`, `+Inf` and `-Inf` are valid. */
function parseValue(token: string): number | null {
  if (/^[+-]?inf(inity)?$/i.test(token)) return token.startsWith("-") ? -Infinity : Infinity;
  if (/^nan$/i.test(token)) return NaN;
  if (token === "") return null;
  const value = Number(token);
  return Number.isNaN(value) ? null : value;
}

function skipBlanks(line: string, pos: number): number {
  while (line[pos] === " " || line[pos] === "\t") pos++;
  return pos;
}

/** Parses `name="value",...}` starting after the `{`; returns the index after `}` or -1. */
function parseLabels(line: string, start: number, out: Record<string, string>): number {
  let pos = skipBlanks(line, start);
  while (pos < line.length) {
    if (line[pos] === "}") return pos + 1;
    LABEL_NAME.lastIndex = pos;
    const label = LABEL_NAME.exec(line)?.[0];
    if (!label || Object.hasOwn(out, label)) return -1;
    pos = skipBlanks(line, pos + label.length);
    if (line[pos] !== "=") return -1;
    pos = skipBlanks(line, pos + 1);
    if (line[pos] !== '"') return -1;
    pos++;
    let value = "";
    for (;;) {
      const ch = line[pos];
      if (ch === undefined) return -1;
      if (ch === '"') break;
      if (ch === "\\") {
        const next = line[pos + 1];
        if (next === undefined) return -1;
        // The format defines \\, \" and \n; anything else is kept verbatim, like Prometheus.
        value += next === "n" ? "\n" : next === "\\" || next === '"' ? next : `\\${next}`;
        pos += 2;
      } else {
        value += ch;
        pos++;
      }
    }
    out[label] = value;
    pos = skipBlanks(line, pos + 1);
    if (line[pos] === ",") pos = skipBlanks(line, pos + 1);
    else if (line[pos] !== "}") return -1;
  }
  return -1;
}

function parseSampleLine(line: string): Sample | null {
  METRIC_NAME.lastIndex = 0;
  const name = METRIC_NAME.exec(line)?.[0];
  if (!name) return null;
  const labels = emptyLabels();
  let pos = skipBlanks(line, name.length);
  if (line[pos] === "{") {
    pos = parseLabels(line, pos + 1, labels);
    if (pos < 0) return null;
  } else if (pos === name.length) {
    return null; // the name must be followed by labels or whitespace
  }
  const fields = line
    .slice(pos)
    .trim()
    .split(/[ \t]+/);
  if (fields.length > 2) return null;
  const value = parseValue(fields[0] ?? "");
  if (value === null) return null;
  const sample: Sample = { name, labels, value };
  if (fields[1] !== undefined) {
    const timestamp = Number(fields[1]);
    if (!Number.isInteger(timestamp)) return null;
    sample.timestamp = timestamp;
  }
  return sample;
}

function parseMetadata(line: string, metadata: Map<string, MetricMetadata>): void {
  const match = METADATA_LINE.exec(line);
  if (!match) return; // an ordinary comment
  const [, keyword, name = "", text = ""] = match;
  const entry = metadata.get(name) ?? {};
  if (keyword === "HELP") {
    entry.help ??= text.replace(/\\([\\n])/g, (_, ch: string) => (ch === "n" ? "\n" : "\\"));
  } else if (METRIC_TYPES.has(text)) {
    entry.type ??= text as MetricType;
  }
  metadata.set(name, entry);
}

/**
 * Parse a Prometheus text exposition. Malformed lines are skipped rather than failing the
 * whole scrape, so one odd collector can't blank a dashboard.
 */
export function parsePrometheus(text: string): Exposition {
  const samples: Sample[] = [];
  const metadata = new Map<string, MetricMetadata>();
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (line === "") continue;
    if (line.startsWith("#")) parseMetadata(line, metadata);
    else {
      const sample = parseSampleLine(line);
      if (sample) samples.push(sample);
    }
  }
  return { samples, metadata };
}

/** Stable identity of a series: name plus labels in sorted order. */
export function seriesKey(name: string, labels: Labels): string {
  const pairs = Object.keys(labels)
    .sort()
    .map((key) => `${key}=${JSON.stringify(labels[key])}`);
  return `${name}{${pairs.join(",")}}`;
}

export function withoutLabels(labels: Labels, drop: readonly string[]): Labels {
  const out = emptyLabels();
  for (const [key, value] of Object.entries(labels)) if (!drop.includes(key)) out[key] = value;
  return out;
}

/** One scrape, indexed for lookups by metric name and by series. */
export interface Snapshot {
  /** When the scrape completed, in milliseconds since the epoch. */
  time: number;
  samples: readonly Sample[];
  byName: ReadonlyMap<string, readonly Sample[]>;
  bySeries: ReadonlyMap<string, Sample>;
}

export function createSnapshot(samples: readonly Sample[], time: number): Snapshot {
  const byName = new Map<string, Sample[]>();
  const bySeries = new Map<string, Sample>();
  for (const sample of samples) {
    const group = byName.get(sample.name);
    if (group) group.push(sample);
    else byName.set(sample.name, [sample]);
    bySeries.set(seriesKey(sample.name, sample.labels), sample);
  }
  return { time, samples, byName, bySeries };
}

/** Samples named `name` whose labels include every pair in `matchers`. */
export function select(snapshot: Snapshot, name: string, matchers: Labels = {}): Sample[] {
  const wanted = Object.entries(matchers);
  return (snapshot.byName.get(name) ?? []).filter((sample) =>
    wanted.every(([key, value]) => sample.labels[key] === value),
  );
}

const CREATED_SUFFIX = /_(total|bucket|count|sum)$/;

/**
 * prometheus_client exports `<family>_created` next to counters, histograms and summaries.
 * Returns that timestamp's series key for a counter-like sample, or null if it has none.
 */
function createdKey(name: string, labels: Labels): string | null {
  const match = CREATED_SUFFIX.exec(name);
  if (!match) return null;
  const family = name.slice(0, match.index);
  return seriesKey(
    `${family}_created`,
    match[1] === "bucket" ? withoutLabels(labels, ["le"]) : labels,
  );
}

function createdChanged(prev: Snapshot, curr: Snapshot, key: string | null): boolean {
  if (key === null) return false;
  const before = prev.bySeries.get(key)?.value;
  const after = curr.bySeries.get(key)?.value;
  return before !== undefined && after !== undefined && before !== after;
}

/**
 * How much every counter series named `name` grew between two snapshots: PromQL's
 * `increase()` over exactly that interval, without extrapolation.
 *
 * - A counter that went down was reset (the process restarted and counted again from 0),
 *   so the increase is its new value, as in PromQL.
 * - If the series' `_created` timestamp changed, it was recreated even if it has since
 *   climbed past its old value; that is a reset too.
 * - A series missing from `prev` was created in between (prometheus_client creates
 *   labelled series on first use), so it grew from 0.
 */
export function increase(prev: Snapshot, curr: Snapshot, name: string): Sample[] {
  const out: Sample[] = [];
  for (const sample of curr.byName.get(name) ?? []) {
    if (!Number.isFinite(sample.value)) continue;
    const before = prev.bySeries.get(seriesKey(name, sample.labels));
    const reset =
      before === undefined ||
      !(sample.value >= before.value) ||
      createdChanged(prev, curr, createdKey(name, sample.labels));
    out.push({
      name,
      labels: sample.labels,
      value: reset ? sample.value : sample.value - before.value,
    });
  }
  return out;
}

/** Per-second rate of every counter series named `name` between two snapshots. */
export function rate(prev: Snapshot, curr: Snapshot, name: string): Sample[] {
  const seconds = (curr.time - prev.time) / 1000;
  if (!(seconds > 0)) return [];
  return increase(prev, curr, name).map((sample) => ({
    ...sample,
    value: sample.value / seconds,
  }));
}

export function sum(samples: readonly Sample[]): number {
  return samples.reduce((total, sample) => total + sample.value, 0);
}

/** `sum by (label)`: totals keyed by the label's value ("" where the label is absent). */
export function sumBy(samples: readonly Sample[], label: string): Map<string, number> {
  const out = new Map<string, number>();
  for (const sample of samples) {
    const key = sample.labels[label] ?? "";
    out.set(key, (out.get(key) ?? 0) + sample.value);
  }
  return out;
}

export interface Bucket {
  /** Upper bound (`le`); the last bucket is `Infinity`. */
  le: number;
  /** Cumulative count of observations ≤ `le`. */
  count: number;
}

export interface Histogram {
  /** Series labels without `le`. */
  labels: Labels;
  /** Sorted by `le`. */
  buckets: Bucket[];
  count: number;
  sum: number;
}

/** Classic histograms of family `name` (without the `_bucket` suffix) in one snapshot. */
export function histograms(snapshot: Snapshot, name: string): Histogram[] {
  const groups = new Map<string, { labels: Labels; buckets: Bucket[] }>();
  for (const sample of snapshot.byName.get(`${name}_bucket`) ?? []) {
    const le = parseValue(sample.labels.le ?? "");
    if (le === null || Number.isNaN(le)) continue;
    const labels = withoutLabels(sample.labels, ["le"]);
    const key = seriesKey(name, labels);
    const group = groups.get(key) ?? { labels, buckets: [] };
    group.buckets.push({ le, count: sample.value });
    groups.set(key, group);
  }
  return [...groups.values()].map(({ labels, buckets }) => {
    buckets.sort((a, b) => a.le - b.le);
    const count = snapshot.bySeries.get(seriesKey(`${name}_count`, labels))?.value;
    const total = snapshot.bySeries.get(seriesKey(`${name}_sum`, labels))?.value;
    return { labels, buckets, count: count ?? buckets.at(-1)?.count ?? 0, sum: total ?? NaN };
  });
}

function histogramWasReset(
  prev: Snapshot,
  curr: Snapshot,
  name: string,
  before: Histogram,
  after: Histogram,
): boolean {
  if (after.count < before.count || after.buckets.length !== before.buckets.length) return true;
  const changedBucket = after.buckets.some((bucket, i) => {
    const old = before.buckets[i];
    return old === undefined || old.le !== bucket.le || !(bucket.count >= old.count);
  });
  return changedBucket || createdChanged(prev, curr, seriesKey(`${name}_created`, after.labels));
}

/**
 * Observations made between two snapshots, per histogram series: bucket-by-bucket
 * increases, the same input as PromQL's `histogram_quantile(q, rate(x_bucket[w]))`.
 * A reset anywhere in a histogram restarts the whole series, so its buckets stay
 * consistent with each other (a per-bucket reset rule could mix old and new counts).
 */
export function histogramIncrease(prev: Snapshot, curr: Snapshot, name: string): Histogram[] {
  const before = new Map(histograms(prev, name).map((h) => [seriesKey(name, h.labels), h]));
  return histograms(curr, name).map((after) => {
    const old = before.get(seriesKey(name, after.labels));
    if (old === undefined || histogramWasReset(prev, curr, name, old, after)) return after;
    return {
      labels: after.labels,
      buckets: after.buckets.map((bucket, i) => ({
        le: bucket.le,
        count: bucket.count - (old.buckets[i]?.count ?? 0),
      })),
      count: after.count - old.count,
      sum: after.sum - old.sum,
    };
  });
}

/** `sum by (le)` across histograms: one combined histogram, or null when there are none. */
export function mergeHistograms(list: readonly Histogram[], labels: Labels = {}): Histogram | null {
  if (list.length === 0) return null;
  const counts = new Map<number, number>();
  let count = 0;
  let total = 0;
  for (const histogram of list) {
    for (const bucket of histogram.buckets) {
      counts.set(bucket.le, (counts.get(bucket.le) ?? 0) + bucket.count);
    }
    count += histogram.count;
    total += histogram.sum;
  }
  const buckets = [...counts].map(([le, n]) => ({ le, count: n })).sort((a, b) => a.le - b.le);
  return { labels, buckets, count, sum: total };
}

/** `sum by (le, label)`: one combined histogram per value of `label`. */
export function sumHistogramsBy(list: readonly Histogram[], label: string): Map<string, Histogram> {
  const groups = new Map<string, Histogram[]>();
  for (const histogram of list) {
    const key = histogram.labels[label] ?? "";
    groups.set(key, [...(groups.get(key) ?? []), histogram]);
  }
  const out = new Map<string, Histogram>();
  for (const [key, group] of groups) {
    const merged = mergeHistograms(group, { [label]: key });
    if (merged) out.set(key, merged);
  }
  return out;
}

/** Mean observation, or null without observations. */
export function histogramMean(histogram: Histogram | null | undefined): number | null {
  if (!histogram || !(histogram.count > 0) || !Number.isFinite(histogram.sum)) return null;
  return histogram.sum / histogram.count;
}

// Relative differences below this are floating point noise (same constant as Prometheus).
const SMALL_DELTA_TOLERANCE = 1e-12;
const MIN_NORMAL = 2.2250738585072014e-308;

function almostEqual(a: number, b: number, epsilon: number): boolean {
  if (a === b) return true;
  const absSum = Math.abs(a) + Math.abs(b);
  const diff = Math.abs(a - b);
  if (a === 0 || b === 0 || absSum < MIN_NORMAL) return diff < epsilon * MIN_NORMAL;
  return diff / Math.min(absSum, Number.MAX_VALUE) < epsilon;
}

/**
 * The q-quantile of a classic histogram, computed exactly like PromQL's
 * `histogram_quantile` (promql/quantile.go, `BucketQuantile`):
 *
 * - linear interpolation inside the bucket that holds the rank, assuming a lower bound
 *   of 0 for the first bucket when its upper bound is positive;
 * - if the rank falls in the `+Inf` bucket, the highest finite upper bound is returned;
 * - buckets with equal bounds are merged and counts are forced to be monotonic.
 *
 * Returns null where PromQL returns NaN: no observations, fewer than two buckets, or no
 * `+Inf` bucket. q < 0 gives -Infinity and q > 1 gives Infinity, as in PromQL.
 */
export function histogramQuantile(q: number, buckets: readonly Bucket[]): number | null {
  if (Number.isNaN(q)) return null;
  if (q < 0) return -Infinity;
  if (q > 1) return Infinity;
  const sorted = [...buckets].sort((a, b) => a.le - b.le);
  if (sorted.at(-1)?.le !== Infinity) return null;

  const merged: Bucket[] = [];
  for (const { le, count } of sorted) {
    const last = merged.at(-1);
    if (last && last.le === le) last.count += count;
    else merged.push({ le, count });
  }
  let previous = merged[0]?.count ?? 0;
  for (const bucket of merged.slice(1)) {
    if (bucket.count === previous) continue;
    if (almostEqual(previous, bucket.count, SMALL_DELTA_TOLERANCE) || bucket.count < previous) {
      bucket.count = previous;
      continue;
    }
    previous = bucket.count;
  }

  const last = merged.length - 1;
  const observations = merged[last]?.count ?? 0;
  if (merged.length < 2 || !(observations > 0)) return null;

  let rank = q * observations;
  let b = merged.findIndex((bucket, i) => i < last && bucket.count >= rank);
  if (b === -1) b = last;
  const upper = merged[b];
  const lower = merged[b - 1];
  if (b === last) return lower?.le ?? null;
  if (!upper) return null;
  if (b === 0 && upper.le <= 0) return upper.le;

  let start = 0;
  let count = upper.count;
  if (lower) {
    start = lower.le;
    count -= lower.count;
    rank -= lower.count;
  }
  const quantile = start + (upper.le - start) * (rank / count);
  return Number.isNaN(quantile) ? null : quantile;
}
