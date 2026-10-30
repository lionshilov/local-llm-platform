import { useId } from "react";

// Drawing space; the SVG stretches to its box and strokes stay crisp (non-scaling-stroke).
const W = 300;
const H = 100;
const PAD = 6;

type Point = [x: number, y: number];

/** Tangent at an interior point, limited so the curve never overshoots (Fritsch–Carlson). */
function interiorSlope([x0, y0]: Point, [x1, y1]: Point, [x2, y2]: Point): number {
  const h0 = x1 - x0;
  const h1 = x2 - x1;
  const s0 = (y1 - y0) / h0;
  const s1 = (y2 - y1) / h1;
  const p = (s0 * h1 + s1 * h0) / (h0 + h1);
  return (
    (Math.sign(s0) + Math.sign(s1)) * Math.min(Math.abs(s0), Math.abs(s1), 0.5 * Math.abs(p)) || 0
  );
}

/** Monotone cubic path through the points, the same curve as d3's curveMonotoneX. */
function monotonePath(points: readonly Point[]): string {
  const first = points[0];
  if (!first) return "";
  if (points.length < 3) return points.map(([x, y], i) => `${i ? "L" : "M"}${x},${y}`).join("");
  const n = points.length;
  const t: number[] = points.map((p, i) => {
    const prev = points[i - 1];
    const next = points[i + 1];
    return prev && next ? interiorSlope(prev, p, next) : 0;
  });
  const secant = (a: Point, b: Point) => (b[1] - a[1]) / (b[0] - a[0]);
  t[0] = (3 * secant(first, points[1]!) - t[1]!) / 2;
  t[n - 1] = (3 * secant(points[n - 2]!, points[n - 1]!) - t[n - 2]!) / 2;
  const clampY = (y: number) => Math.min(H - PAD, Math.max(PAD, y));
  let d = `M${first[0]},${first[1]}`;
  for (let i = 1; i < n; i++) {
    const [x0, y0] = points[i - 1]!;
    const [x1, y1] = points[i]!;
    const dx = (x1 - x0) / 3;
    d += `C${x0 + dx},${clampY(y0 + dx * t[i - 1]!)},${x1 - dx},${clampY(y1 - dx * t[i]!)},${x1},${y1}`;
  }
  return d;
}

export function Sparkline({
  data,
  color,
  label,
  className = "h-10 w-full",
  slots = 0,
  max,
  showDot = true,
}: {
  data: readonly number[];
  /** Stroke and fill colour (hex), e.g. engineMeta(...).color. */
  color: string;
  /** What the chart shows, for screen readers. */
  label: string;
  className?: string;
  /** Minimum x-axis capacity: shorter series are drawn right-aligned instead of stretched. */
  slots?: number;
  /** Fixed top of the y-axis; defaults to the series maximum plus headroom. */
  max?: number;
  showDot?: boolean;
}) {
  const gradientId = `spark-${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
  const values = data.map((v) => (Number.isFinite(v) ? Math.max(0, v) : 0));
  const top = max ?? Math.max(0, ...values) * 1.15;
  const capacity = Math.max(values.length, slots, 2);
  const points: Point[] = values.map((v, i) => [
    (W * (capacity - values.length + i)) / (capacity - 1),
    top > 0 ? H - PAD - (Math.min(v, top) / top) * (H - 2 * PAD) : H - PAD,
  ]);
  const line = monotonePath(points);
  const first = points[0];
  const last = points.at(-1);
  const area =
    first && last && points.length > 1 ? `${line}L${last[0]},${H}L${first[0]},${H}Z` : "";

  return (
    <div role="img" aria-label={label} className={`relative ${className}`}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        aria-hidden="true"
        className="absolute inset-0 size-full overflow-visible"
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.32} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <line
          x1={0}
          x2={W}
          y1={H - PAD}
          y2={H - PAD}
          stroke="white"
          strokeOpacity={0.06}
          vectorEffect="non-scaling-stroke"
        />
        {area && <path d={area} fill={`url(#${gradientId})`} />}
        {line && (
          <path
            d={line}
            fill="none"
            stroke={color}
            strokeWidth={1.5}
            strokeLinecap="round"
            strokeLinejoin="round"
            vectorEffect="non-scaling-stroke"
          />
        )}
      </svg>
      {showDot && last && (
        <span
          aria-hidden="true"
          className="absolute size-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full"
          style={{
            left: `${(last[0] / W) * 100}%`,
            top: `${(last[1] / H) * 100}%`,
            backgroundColor: color,
            boxShadow: `0 0 0 3px ${color}33, 0 0 10px ${color}`,
          }}
        />
      )}
    </div>
  );
}
