import { CornerDownRight, Gauge, Hourglass, Timer, Zap } from "lucide-react";
import type { ReactNode } from "react";
import type { ChatMessage } from "../lib/types";

function Chip({
  icon,
  children,
  title,
  tone = "default",
}: {
  icon: ReactNode;
  children: ReactNode;
  title: string;
  tone?: "default" | "live" | "warn";
}) {
  const tones = {
    default: "border-white/[0.06] bg-white/[0.03] text-zinc-400",
    live: "border-violet-400/25 bg-violet-500/10 text-violet-200",
    warn: "border-amber-400/25 bg-amber-500/10 text-amber-200",
  };
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[11px] tabular-nums ${tones[tone]}`}
    >
      {icon}
      {children}
    </span>
  );
}

const fmtMs = (ms: number) =>
  ms >= 10_000 ? `${(ms / 1000).toFixed(1)} s` : `${Math.round(ms)} ms`;

/** Live counters while streaming, final metrics afterwards. */
export function MetricChips({
  message,
  labelFor,
}: {
  message: ChatMessage;
  labelFor: (id: string) => string;
}) {
  if (message.status === "streaming") {
    const live = message.live;
    return (
      <div className="flex flex-wrap items-center gap-1.5">
        <Chip
          icon={<span className="size-1.5 animate-pulse rounded-full bg-violet-300" />}
          title="Elapsed since the request was sent"
          tone="live"
        >
          {((live?.elapsedMs ?? 0) / 1000).toFixed(1)} s
        </Chip>
        {live?.ttftMs != null ? (
          <Chip icon={<Timer className="size-3" />} title="Time to first token">
            {fmtMs(live.ttftMs)}
          </Chip>
        ) : (
          <Chip icon={<Hourglass className="size-3" />} title="Waiting for the first token">
            prefill…
          </Chip>
        )}
        {live?.tokensPerSecond != null && (
          <Chip icon={<Zap className="size-3" />} title="Live decode speed" tone="live">
            {live.tokensPerSecond.toFixed(1)} tok/s
          </Chip>
        )}
        {live && live.tokens > 0 && (
          <Chip icon={<Gauge className="size-3" />} title="Tokens generated so far">
            {live.tokens} tok
          </Chip>
        )}
      </div>
    );
  }

  const s = message.stats;
  if (!s) return null;
  const fellBack = s.servedBy && message.model && s.servedBy !== message.model;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {fellBack && s.servedBy && (
        <Chip
          icon={<CornerDownRight className="size-3" />}
          title="The requested backend was busy or down; the gateway fell back"
          tone="warn"
        >
          served by {labelFor(s.servedBy)}
        </Chip>
      )}
      {s.ttftMs != null && (
        <Chip icon={<Timer className="size-3" />} title="Time to first token">
          {fmtMs(s.ttftMs)}
        </Chip>
      )}
      {s.tokensPerSecond != null && (
        <Chip icon={<Zap className="size-3" />} title="Decode speed after the first token">
          {s.tokensPerSecond.toFixed(1)} tok/s
        </Chip>
      )}
      {s.completionTokens != null && (
        <Chip icon={<Gauge className="size-3" />} title="Prompt → completion tokens">
          {s.promptTokens ?? "?"} → {s.completionTokens} tok
        </Chip>
      )}
      {s.finishReason === "length" && (
        <Chip icon={<Hourglass className="size-3" />} title="Stopped at max tokens" tone="warn">
          max tokens
        </Chip>
      )}
      {message.status === "stopped" && (
        <Chip icon={<Hourglass className="size-3" />} title="Stopped by you">
          stopped
        </Chip>
      )}
    </div>
  );
}
