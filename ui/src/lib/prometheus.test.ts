import { describe, expect, it } from "vitest";
import {
  EMPTY_BUFFER,
  HISTORY_MS,
  classifyOutcome,
  deriveWindow,
  pushSnapshot,
  windowBase,
} from "../hooks/useGatewayMetrics";
import afterText from "./__fixtures__/gateway-after.prom?raw";
import beforeText from "./__fixtures__/gateway-before.prom?raw";
import freshText from "./__fixtures__/gateway-fresh.prom?raw";
import {
  type Bucket,
  type Sample,
  createSnapshot,
  histogramIncrease,
  histogramMean,
  histogramQuantile,
  histograms,
  increase,
  mergeHistograms,
  parsePrometheus,
  rate,
  select,
  seriesKey,
  sum,
  sumBy,
  sumHistogramsBy,
} from "./prometheus";

// Real scrapes of the running gateway: a fresh start, then two scrapes 12.477 s apart
// around a burst of 9 streaming requests (6 to llamacpp, 2 to mlx, 1 to ollama-gguf,
// which was offline and fell back to llamacpp).
const FRESH_AT = 1_793_338_590_582;
const BEFORE_AT = 1_793_338_868_310;
const AFTER_AT = 1_793_338_880_787;
const WINDOW_S = (AFTER_AT - BEFORE_AT) / 1000;

const snap = (text: string, time: number) => createSnapshot(parsePrometheus(text).samples, time);
const fresh = snap(freshText, FRESH_AT);
const before = snap(beforeText, BEFORE_AT);
const after = snap(afterText, AFTER_AT);

const TTFT = "llm_gateway_time_to_first_token_seconds";
const TPOT = "llm_gateway_time_per_output_token_seconds";
const REQUESTS = "llm_gateway_requests_total";

function valueOf(samples: readonly Sample[], labels: Record<string, string>) {
  const match = samples.find((s) =>
    Object.entries(labels).every(([key, value]) => s.labels[key] === value),
  );
  return match?.value;
}

describe("parsePrometheus", () => {
  it("parses a real prometheus_client exposition", () => {
    const { samples, metadata } = parsePrometheus(afterText);
    // Every non-comment line of the fixture is a sample.
    expect(samples).toHaveLength(afterText.split("\n").filter((l) => /^[a-z]/.test(l)).length);
    expect(samples).toHaveLength(133);
    expect(samples[0]).toEqual({
      name: "python_info",
      labels: {
        implementation: "CPython",
        major: "3",
        minor: "12",
        patchlevel: "13",
        version: "3.12.13",
      },
      value: 1,
    });
    expect(
      valueOf(
        samples.filter((s) => s.name === REQUESTS),
        { backend: "llamacpp", outcome: "ok" },
      ),
    ).toBe(12);
    expect(metadata.get(REQUESTS)).toEqual({
      type: "counter",
      help: "Chat completion requests by backend and outcome.",
    });
    expect(metadata.get(TTFT)?.type).toBe("histogram");
    expect(metadata.get("llm_gateway_queue_depth")?.type).toBe("gauge");
  });

  it("keeps _created samples as their own gauge series", () => {
    const { samples, metadata } = parsePrometheus(afterText);
    const created = samples.find(
      (s) => s.name === "llm_gateway_requests_created" && s.labels.backend === "llamacpp",
    );
    expect(created?.value).toBeCloseTo(1_793_337_706.8409889, 6);
    expect(metadata.get("llm_gateway_requests_created")?.type).toBe("gauge");
    // _created never leaks into the counter itself.
    expect(samples.filter((s) => s.name === REQUESTS)).toHaveLength(7);
  });

  it("parses histogram buckets including le=+Inf", () => {
    const { samples } = parsePrometheus(afterText);
    const inf = samples.find(
      (s) =>
        s.name === `${TTFT}_bucket` && s.labels.backend === "llamacpp" && s.labels.le === "+Inf",
    );
    expect(inf?.value).toBe(12);
    expect(
      valueOf(
        samples.filter((s) => s.name === `${TTFT}_sum`),
        { backend: "llamacpp" },
      ),
    ).toBe(36.461979917949066);
  });

  it("unescapes label values and handles special characters inside them", () => {
    const { samples } = parsePrometheus(
      [
        String.raw`msg{path="C:\\temp\\x",quote="say \"hi\"",nl="a\nb",other="keep\t"} 1`,
        'tricky{v="a,b=c}{d", empty=""} 2',
        '  spaced { a = "1" , b="2", } 3  ',
        "braces{} 4",
        'proto{__proto__="p",constructor="c"} 5',
      ].join("\n"),
    );
    const expected: Record<string, string>[] = [
      { path: "C:\\temp\\x", quote: 'say "hi"', nl: "a\nb", other: "keep\\t" },
      { v: "a,b=c}{d", empty: "" },
      { a: "1", b: "2" },
      {},
    ];
    expect(samples.slice(0, 4).map((s) => s.labels)).toEqual(expected);
    expect(samples.map((s) => s.value)).toEqual([1, 2, 3, 4, 5]);
    // Reserved-looking label names are plain data, not prototype pollution.
    const proto = samples[4]?.labels;
    expect(proto && Object.getPrototypeOf(proto)).toBeNull();
    expect(proto && Object.entries(proto)).toEqual([
      ["__proto__", "p"],
      ["constructor", "c"],
    ]);
  });

  it("parses NaN, ±Inf, exponents and timestamps", () => {
    const { samples } = parsePrometheus(
      [
        "a NaN",
        "b +Inf",
        "c -Inf",
        "d Inf",
        "e 1.5e+09",
        "f -0.25",
        "g 7 1700000000123",
        "h\t3\t-5",
      ].join("\n"),
    );
    expect(samples.map((s) => [s.name, s.value])).toEqual([
      ["a", NaN],
      ["b", Infinity],
      ["c", -Infinity],
      ["d", Infinity],
      ["e", 1.5e9],
      ["f", -0.25],
      ["g", 7],
      ["h", 3],
    ]);
    expect(samples[6]?.timestamp).toBe(1_700_000_000_123);
    expect(samples[7]?.timestamp).toBe(-5);
    expect(samples[0]?.timestamp).toBeUndefined();
  });

  it("reads HELP/TYPE metadata and ignores other comments", () => {
    const { samples, metadata } = parsePrometheus(
      [
        "# a free-form comment mentioning x 1",
        "   # indented comment",
        String.raw`# HELP x Line one\nline two with a backslash \\ here`,
        "# TYPE x counter",
        "# TYPE x gauge",
        "# TYPE y nonsense",
        "x_total 1",
        "# EOF",
      ].join("\r\n"),
    );
    expect(samples).toEqual([{ name: "x_total", labels: {}, value: 1 }]);
    expect(metadata.get("x")).toEqual({
      help: "Line one\nline two with a backslash \\ here",
      type: "counter",
    });
    expect(metadata.get("y")).toEqual({});
  });

  it("skips malformed lines instead of failing the scrape", () => {
    const { samples } = parsePrometheus(
      [
        "ok 1",
        'unterminated{a="1} 2',
        'missing_value{a="1"}',
        "garbage_value abc",
        'dup{a="1",a="2"} 3',
        "no_quotes{a=1} 4",
        "bad_ts 1 1.5",
        "too many 1 2 3",
        "9starts_with_digit 1",
        "name-with-dash 1",
        "also_ok 2",
      ].join("\n"),
    );
    expect(samples.map((s) => s.name)).toEqual(["ok", "also_ok"]);
  });

  it("returns nothing for an empty body", () => {
    expect(parsePrometheus("")).toEqual({ samples: [], metadata: new Map() });
    expect(parsePrometheus("\n\n# just comments\n").samples).toEqual([]);
  });
});

describe("snapshots", () => {
  it("identifies series independently of label order", () => {
    expect(seriesKey("m", { b: "2", a: "1" })).toBe(seriesKey("m", { a: "1", b: "2" }));
    expect(seriesKey("m", { a: "1" })).not.toBe(seriesKey("m", { a: "1", b: "" }));
    expect(seriesKey("m", { a: 'x",b="y' })).not.toBe(seriesKey("m", { a: "x", b: "y" }));
  });

  it("selects by name and label matchers", () => {
    expect(select(after, REQUESTS)).toHaveLength(7);
    expect(select(after, REQUESTS, { backend: "mlx" }).map((s) => s.labels.outcome)).toEqual([
      "ok",
      "cancelled",
    ]);
    expect(select(after, "does_not_exist")).toEqual([]);
  });
});

describe("increase and rate", () => {
  it("subtracts counters between two real scrapes", () => {
    const requests = increase(before, after, REQUESTS);
    expect(valueOf(requests, { backend: "llamacpp", outcome: "ok" })).toBe(8);
    expect(valueOf(requests, { backend: "mlx", outcome: "ok" })).toBe(2);
    expect(valueOf(requests, { backend: "mlx", outcome: "cancelled" })).toBe(0);
    expect(valueOf(requests, { backend: "ollama-gguf", outcome: "upstream_unavailable" })).toBe(1);
    expect(sum(requests)).toBe(11);

    const tokens = sumBy(increase(before, after, "llm_gateway_output_tokens_total"), "backend");
    expect(Object.fromEntries(tokens)).toEqual({
      llamacpp: 2460,
      mlx: 195,
      "ollama-gguf": 0,
      "ollama-mlx": 0,
    });
  });

  it("turns increases into per-second rates over the real interval", () => {
    const tokens = rate(before, after, "llm_gateway_output_tokens_total");
    expect(valueOf(tokens, { backend: "llamacpp" })).toBeCloseTo(2460 / WINDOW_S, 9);
    expect(valueOf(tokens, { backend: "llamacpp" })).toBeCloseTo(197.16, 2);
    const requests = sumBy(rate(before, after, REQUESTS), "backend");
    expect(requests.get("llamacpp")).toBeCloseTo(8 / 12.477, 9);
  });

  it("counts series created between scrapes from zero", () => {
    // The fresh gateway had no cancelled/unavailable outcomes and no fallback series yet.
    expect(select(fresh, "llm_gateway_fallbacks_total")).toEqual([]);
    const fallbacks = increase(fresh, before, "llm_gateway_fallbacks_total");
    expect(fallbacks.map((s) => [s.labels.from_backend, s.labels.to_backend, s.value])).toEqual([
      ["ollama-gguf", "llamacpp", 1],
      ["ollama-mlx", "mlx", 1],
    ]);
    const requests = increase(fresh, before, REQUESTS);
    expect(valueOf(requests, { backend: "mlx", outcome: "cancelled" })).toBe(1);
  });

  it("treats a decrease as a counter reset", () => {
    const prev = snap("c_total 100\nc_created 1000", 0);
    const curr = snap("c_total 7\nc_created 1000", 2_000);
    expect(increase(prev, curr, "c_total")[0]?.value).toBe(7);
    expect(rate(prev, curr, "c_total")[0]?.value).toBe(3.5);
  });

  it("detects a restart from a changed _created even when the value grew", () => {
    const prev = snap('c_total{x="1"} 5\nc_created{x="1"} 1000', 0);
    const curr = snap('c_total{x="1"} 9\nc_created{x="1"} 1050', 10_000);
    expect(increase(prev, curr, "c_total")[0]?.value).toBe(9);
    // Without _created a growing counter is a plain difference.
    expect(increase(snap("c_total 5", 0), snap("c_total 9", 1), "c_total")[0]?.value).toBe(4);
  });

  it("is zero over an empty window and has no rate without elapsed time", () => {
    expect(sum(increase(after, after, REQUESTS))).toBe(0);
    expect(rate(after, after, REQUESTS)).toEqual([]);
    expect(increase(before, after, "missing_total")).toEqual([]);
  });

  it("skips series whose value is not a number", () => {
    const prev = snap("c_total 1\nd_total 1", 0);
    const curr = snap("c_total NaN\nd_total 3", 1_000);
    expect(increase(prev, curr, "c_total")).toEqual([]);
    expect(increase(prev, snap("d_total 3", 1_000), "d_total")[0]?.value).toBe(2);
    // A NaN in the earlier scrape counts as a reset.
    expect(increase(curr, snap("c_total 4", 2_000), "c_total")[0]?.value).toBe(4);
  });
});

describe("histogramQuantile", () => {
  const b = (pairs: [number, number][]): Bucket[] => pairs.map(([le, count]) => ({ le, count }));
  // 10 observations: 2 in (0, 0.1], 3 in (0.1, 0.5], 4 in (0.5, 1], 1 above 1.
  const buckets = b([
    [0.1, 2],
    [0.5, 5],
    [1, 9],
    [Infinity, 10],
  ]);

  it("interpolates linearly inside the bucket holding the rank", () => {
    // rank 5 → top of (0.1, 0.5]
    expect(histogramQuantile(0.5, buckets)).toBeCloseTo(0.5, 12);
    // rank 3 → 1 of 3 into (0.1, 0.5]: 0.1 + 0.4 / 3
    expect(histogramQuantile(0.3, buckets)).toBeCloseTo(0.1 + 0.4 / 3, 12);
    // rank 8 → 3 of 4 into (0.5, 1]
    expect(histogramQuantile(0.8, buckets)).toBeCloseTo(0.875, 12);
  });

  it("assumes 0 as the lower bound of the first bucket", () => {
    // rank 1 → half of (0, 0.1]
    expect(histogramQuantile(0.1, buckets)).toBeCloseTo(0.05, 12);
    expect(histogramQuantile(0, buckets)).toBe(0);
  });

  it("returns the highest finite bound when the rank is in the +Inf bucket", () => {
    expect(histogramQuantile(0.95, buckets)).toBe(1);
    expect(histogramQuantile(1, buckets)).toBe(1);
  });

  it("returns the first bound when it is not positive", () => {
    expect(
      histogramQuantile(
        0.25,
        b([
          [-1, 4],
          [0, 6],
          [Infinity, 8],
        ]),
      ),
    ).toBe(-1);
  });

  it("sorts, merges duplicate bounds and forces monotonic counts like PromQL", () => {
    const messy = b([
      [Infinity, 10],
      [1, 9],
      [0.1, 1],
      [0.1, 1],
      [0.5, 5],
    ]);
    expect(histogramQuantile(0.3, messy)).toBeCloseTo(0.1 + 0.4 / 3, 12);
    // A dip (5 → 4) is flattened to 5 instead of producing a negative bucket.
    const dip = b([
      [0.1, 2],
      [0.5, 5],
      [1, 4],
      [2, 9],
      [Infinity, 10],
    ]);
    expect(histogramQuantile(0.8, dip)).toBeCloseTo(1 + (3 / 4) * 1, 12);
  });

  it("returns null when there is nothing to compute", () => {
    expect(histogramQuantile(0.5, [])).toBeNull();
    expect(
      histogramQuantile(
        0.5,
        b([
          [0.1, 0],
          [Infinity, 0],
        ]),
      ),
    ).toBeNull();
    expect(histogramQuantile(0.5, b([[Infinity, 3]]))).toBeNull();
    expect(
      histogramQuantile(
        0.5,
        b([
          [0.1, 1],
          [1, 3],
        ]),
      ),
    ).toBeNull();
    expect(histogramQuantile(NaN, buckets)).toBeNull();
  });

  it("follows PromQL for q outside [0, 1]", () => {
    expect(histogramQuantile(-0.1, buckets)).toBe(-Infinity);
    expect(histogramQuantile(1.1, buckets)).toBe(Infinity);
  });
});

describe("histograms from real scrapes", () => {
  it("reads cumulative buckets, count and sum per series", () => {
    const ttft = histograms(after, TTFT);
    expect(ttft.map((h) => h.labels.backend)).toEqual(["llamacpp", "mlx", "ollama-gguf"]);
    const llamacpp = ttft[0];
    expect(llamacpp?.buckets.map((x) => x.le)).toEqual([
      0.05,
      0.1,
      0.25,
      0.5,
      1,
      2,
      2.5,
      5,
      10,
      30,
      60,
      Infinity,
    ]);
    expect(llamacpp?.count).toBe(12);
    expect(llamacpp?.sum).toBe(36.461979917949066);
  });

  it("computes TTFT quantiles from bucket deltas, not lifetime totals", () => {
    const ttft = sumHistogramsBy(histogramIncrease(before, after, TTFT), "backend");
    const llamacpp = ttft.get("llamacpp");
    expect(llamacpp?.buckets.map((x) => x.count)).toEqual([0, 0, 0, 0, 0, 3, 3, 6, 8, 8, 8, 8]);
    expect(llamacpp?.count).toBe(8);
    expect(histogramMean(llamacpp)).toBeCloseTo((36.461979917949066 - 7.414205293403938) / 8, 12);
    // p50: rank 4 → 1 of 3 into (2.5, 5]; p95: rank 7.6 → 1.6 of 2 into (5, 10]
    expect(histogramQuantile(0.5, llamacpp?.buckets ?? [])).toBeCloseTo(2.5 + 2.5 / 3, 12);
    expect(histogramQuantile(0.95, llamacpp?.buckets ?? [])).toBeCloseTo(9, 12);
    // Lifetime buckets would give a very different (wrong for "last minute") answer.
    const lifetime = histograms(after, TTFT)[0]?.buckets ?? [];
    expect(histogramQuantile(0.5, lifetime)).toBeCloseTo(2 + 0.5 * (2 / 3), 12);

    const mlx = ttft.get("mlx");
    expect(histogramQuantile(0.5, mlx?.buckets ?? [])).toBeCloseTo(3.75, 12);
    expect(histogramQuantile(0.95, mlx?.buckets ?? [])).toBeCloseTo(4.875, 12);
    expect(histogramQuantile(0.5, ttft.get("ollama-gguf")?.buckets ?? [])).toBeNull();
  });

  it("aggregates across backends like sum by (le)", () => {
    const all = mergeHistograms(histogramIncrease(before, after, TTFT));
    expect(all?.count).toBe(10);
    expect(histogramQuantile(0.5, all?.buckets ?? [])).toBeCloseTo(3.5, 12);
    expect(histogramQuantile(0.95, all?.buckets ?? [])).toBeCloseTo(8.75, 12);
    expect(mergeHistograms([])).toBeNull();
  });

  it("computes TPOT quantiles", () => {
    const tpot = sumHistogramsBy(histogramIncrease(before, after, TPOT), "backend");
    // llamacpp: 8 new observations, rank 4 → 2 of 4 into (0.05, 0.075]
    expect(histogramQuantile(0.5, tpot.get("llamacpp")?.buckets ?? [])).toBeCloseTo(0.0625, 12);
    // mlx: 2 new observations, both in (0.03, 0.05]
    expect(histogramQuantile(0.5, tpot.get("mlx")?.buckets ?? [])).toBeCloseTo(0.04, 12);
  });

  it("restarts the whole histogram when any part of it was reset", () => {
    const prev = snap(
      [
        'h_bucket{le="1"} 5',
        'h_bucket{le="+Inf"} 9',
        "h_count 9",
        "h_sum 12",
        "h_created 100",
      ].join("\n"),
      0,
    );
    const restarted = snap(
      [
        'h_bucket{le="1"} 1',
        'h_bucket{le="+Inf"} 10',
        "h_count 10",
        "h_sum 30",
        "h_created 200",
      ].join("\n"),
      1_000,
    );
    const [delta] = histogramIncrease(prev, restarted, "h");
    expect(delta?.buckets).toEqual([
      { le: 1, count: 1 },
      { le: Infinity, count: 10 },
    ]);
    expect(delta?.count).toBe(10);
  });

  it("has no quantiles over an empty window", () => {
    const [delta] = histogramIncrease(after, after, TTFT);
    expect(delta?.count).toBe(0);
    expect(histogramQuantile(0.95, delta?.buckets ?? [])).toBeNull();
    expect(histogramMean(delta)).toBeNull();
  });
});

describe("gateway window", () => {
  const { totals, backends, windowSeconds } = deriveWindow(before, after);
  const byName = Object.fromEntries(backends.map((b) => [b.backend, b]));

  it("lists every configured backend in config order", () => {
    expect(backends.map((b) => b.backend)).toEqual([
      "llamacpp",
      "mlx",
      "ollama-gguf",
      "ollama-mlx",
    ]);
    expect(windowSeconds).toBeCloseTo(WINDOW_S, 9);
  });

  it("derives per-backend throughput, latency and request outcomes", () => {
    const llamacpp = byName.llamacpp;
    expect(llamacpp?.requests).toEqual({
      total: 8,
      ok: 8,
      errors: 0,
      rejected: 0,
      cancelled: 0,
      clientErrors: 0,
    });
    expect(llamacpp?.requestsPerSecond).toBeCloseTo(8 / WINDOW_S, 9);
    expect(llamacpp?.outputTokensPerSecond).toBeCloseTo(2460 / WINDOW_S, 9);
    expect(llamacpp?.ttftP50).toBeCloseTo(2.5 + 2.5 / 3, 12);
    expect(llamacpp?.ttftP95).toBeCloseTo(9, 12);
    expect(llamacpp?.tpotP50).toBeCloseTo(0.0625, 12);
    expect(llamacpp?.decodeTokensPerSecond).toBeCloseTo(16, 9);
    expect(llamacpp?.errorRatio).toBe(0);
    expect(llamacpp?.fallbacksIn).toBe(1);
    expect(llamacpp?.fallbackSources).toEqual({ "ollama-gguf": 1 });
    expect(llamacpp?.fallbacksOut).toBe(0);
    expect(llamacpp?.idle).toBe(false);

    expect(byName.mlx?.decodeTokensPerSecond).toBeCloseTo(25, 9);
  });

  it("counts an offline backend's failed attempt and its fallback", () => {
    const ollama = byName["ollama-gguf"];
    expect(ollama?.requests.errors).toBe(1);
    expect(ollama?.errorRatio).toBe(1);
    expect(ollama?.fallbacksOut).toBe(1);
    expect(ollama?.fallbackTargets).toEqual({ llamacpp: 1 });
    expect(ollama?.ttftP95).toBeNull();
    expect(byName["ollama-mlx"]?.idle).toBe(true);
    expect(byName["ollama-mlx"]?.errorRatio).toBeNull();
  });

  it("sums totals across backends", () => {
    expect(totals.requests.total).toBe(11);
    expect(totals.requests.errors).toBe(1);
    expect(totals.errorRatio).toBeCloseTo(1 / 11, 12);
    expect(totals.outputTokensPerSecond).toBeCloseTo(2655 / WINDOW_S, 9);
    expect(totals.ttftP50).toBeCloseTo(3.5, 12);
    expect(totals.ttftP95).toBeCloseTo(8.75, 12);
    expect(totals.slowest).toEqual({ backend: "llamacpp", ttftP95: expect.closeTo(9, 12) });
    expect(totals.fallbacks).toBe(1);
    expect(totals.inFlight).toBe(0);
  });

  it("reads gauges from the latest scrape", () => {
    const mid = snap(
      afterText
        .replace(
          'llm_gateway_in_flight_requests{backend="llamacpp"} 0.0',
          'llm_gateway_in_flight_requests{backend="llamacpp"} 4.0',
        )
        .replace(
          'llm_gateway_queue_depth{backend="llamacpp"} 0.0',
          'llm_gateway_queue_depth{backend="llamacpp"} 3.0',
        ),
      AFTER_AT,
    );
    const { totals: t, backends: list } = deriveWindow(after, mid);
    expect(list[0]?.inFlight).toBe(4);
    expect(list[0]?.queueDepth).toBe(3);
    expect(list[0]?.idle).toBe(false);
    expect(t.inFlight).toBe(4);
    expect(t.requestsPerSecond).toBe(0);
  });

  it("is idle with no quantiles over an empty window", () => {
    const empty = deriveWindow(after, after);
    expect(empty.windowSeconds).toBe(0);
    expect(empty.totals.idle).toBe(true);
    expect(empty.totals.requestsPerSecond).toBe(0);
    expect(empty.totals.ttftP95).toBeNull();
    expect(empty.totals.errorRatio).toBeNull();
    expect(empty.totals.decodeTokensPerSecond).toBeNull();
  });

  it("classifies outcomes, keeping cancellations and client errors out of errors", () => {
    expect(
      ["ok", "cancelled", "rejected", "upstream_error", "upstream_unavailable"].map(
        classifyOutcome,
      ),
    ).toEqual(["ok", "cancelled", "rejected", "error", "error"]);
    expect(
      ["upstream_502", "upstream_400", "upstream_429", "mystery"].map(classifyOutcome),
    ).toEqual(["error", "client_error", "client_error", "other"]);
  });
});

describe("rolling buffer", () => {
  const at = (time: number, ok: number, tokens: number) =>
    snap(
      [
        `llm_gateway_requests_total{backend="a",outcome="ok"} ${ok}`,
        `llm_gateway_output_tokens_total{backend="a"} ${tokens}`,
        'llm_gateway_in_flight_requests{backend="a"} 1',
      ].join("\n"),
      time,
    );

  it("uses the last 60 s, or everything since the first scrape when younger", () => {
    const snapshots = [0, 2, 4, 6].map((s) => at(s * 1000, s, s * 10));
    expect(windowBase(snapshots, 60_000)?.time).toBe(0);
    const long = Array.from({ length: 40 }, (_, i) => at(i * 2000, i, i));
    // newest is at 78 s, so the window starts at the first scrape at or after 18 s (- slack)
    expect(windowBase(long, 60_000)?.time).toBe(18_000);
    expect(windowBase([], 60_000)).toBeNull();
  });

  it("does not stretch the window over a long gap", () => {
    const gap = [at(0, 0, 0), at(2_000, 1, 1), at(200_000, 5, 5)];
    expect(windowBase(gap, 60_000)?.time).toBe(200_000);
    expect(deriveWindow(windowBase(gap, 60_000)!, gap[2]!).windowSeconds).toBe(0);
  });

  it("keeps five minutes of snapshots and one smoothed point per scrape", () => {
    let buffer = EMPTY_BUFFER;
    for (let i = 0; i <= 200; i++) buffer = pushSnapshot(buffer, at(i * 2000, i, i * 20));
    const newest = 400_000;
    expect(buffer.snapshots.at(-1)?.time).toBe(newest);
    expect(buffer.snapshots[0]?.time).toBe(newest - HISTORY_MS);
    expect(buffer.history).toHaveLength(buffer.snapshots.length);
    const point = buffer.history.at(-1);
    // 1 request and 20 tokens every 2 s, measured over the trailing 10 s
    expect(point?.requestsPerSecond).toBeCloseTo(0.5, 12);
    expect(point?.outputTokensPerSecond).toBeCloseTo(10, 12);
    expect(point?.inFlight).toBe(1);
    expect(point?.backends.a?.outputTokensPerSecond).toBeCloseTo(10, 12);
  });

  it("starts the history at the second scrape", () => {
    const one = pushSnapshot(EMPTY_BUFFER, at(0, 0, 0));
    expect(one.history).toEqual([]);
    expect(pushSnapshot(one, at(2000, 1, 10)).history).toHaveLength(1);
  });
});
