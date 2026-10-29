import { AlertTriangle, CornerDownRight, Gauge, RotateCcw, Sparkles, Timer, Zap } from "lucide-react";
import type { ReactNode } from "react";
import type { ChatMessage } from "../lib/types";
import { CopyButton } from "./CopyButton";
import { LazyMarkdown } from "./LazyMarkdown";
import { ThinkingBlock } from "./ThinkingBlock";

function Stat({ icon, children, title }: { icon: ReactNode; children: ReactNode; title: string }) {
  return (
    <span title={title} className="inline-flex items-center gap-1">
      {icon}
      {children}
    </span>
  );
}

function StatsBar({
  message,
  modelLabel,
  labelFor,
}: {
  message: ChatMessage;
  modelLabel: string;
  labelFor: (id: string) => string;
}) {
  const s = message.stats;
  const fellBack = s?.servedBy && message.model && s.servedBy !== message.model;
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[11px] text-zinc-500">
      {fellBack && s?.servedBy ? (
        <span
          className="inline-flex items-center gap-1 text-amber-300/90"
          title={`${modelLabel} was busy or down; the gateway fell back`}
        >
          <CornerDownRight className="size-3" />
          {labelFor(s.servedBy)} (fallback)
        </span>
      ) : (
        <span className="text-zinc-400">{modelLabel}</span>
      )}
      {s?.ttftMs != null && (
        <Stat icon={<Timer className="size-3" />} title="Time to first token">
          {Math.round(s.ttftMs)} ms
        </Stat>
      )}
      {s?.tokensPerSecond != null && (
        <Stat icon={<Zap className="size-3" />} title="Decode speed after the first token">
          {s.tokensPerSecond.toFixed(1)} tok/s
        </Stat>
      )}
      {s?.completionTokens != null && (
        <Stat icon={<Gauge className="size-3" />} title="Prompt → completion tokens">
          {s.promptTokens ?? "?"} → {s.completionTokens} tok
        </Stat>
      )}
      {s?.finishReason === "length" && <span className="text-amber-400/80">max tokens reached</span>}
      {message.status === "stopped" && <span className="text-zinc-400">stopped</span>}
    </div>
  );
}

export function MessageView({
  message,
  modelLabel,
  labelFor = (id) => id,
  canRegenerate,
  onRegenerate,
}: {
  message: ChatMessage;
  modelLabel: string;
  labelFor?: (id: string) => string;
  canRegenerate: boolean;
  onRegenerate: () => void;
}) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-3xl bg-zinc-800/80 px-5 py-2.5 leading-7 whitespace-pre-wrap text-zinc-100">
          {message.content}
        </div>
      </div>
    );
  }

  const streaming = message.status === "streaming";
  const waiting = streaming && !message.content && !message.reasoning;
  const thinkingActive = streaming && !!message.reasoning && !message.content;

  return (
    <div className="group flex gap-4">
      <div className="mt-1 flex size-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-500 shadow-lg shadow-violet-500/20">
        <Sparkles className="size-4 text-white" />
      </div>
      <div className="min-w-0 flex-1">
        {message.reasoning ? (
          <ThinkingBlock
            text={message.reasoning}
            active={thinkingActive}
            durationMs={message.stats?.thinkingMs ?? null}
          />
        ) : null}

        {waiting ? (
          <div className="flex h-8 items-center gap-1.5">
            <span className="typing-dot" />
            <span className="typing-dot [animation-delay:150ms]" />
            <span className="typing-dot [animation-delay:300ms]" />
          </div>
        ) : (
          message.content && (
            <LazyMarkdown text={message.content} streaming={streaming} />
          )
        )}

        {message.status === "error" && (
          <div className="mt-2 flex items-start gap-2 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-200">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" />
            <span className="break-words">{message.error}</span>
          </div>
        )}

        {!streaming && (
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <div className="flex items-center opacity-60 transition group-hover:opacity-100">
              {message.content && <CopyButton text={message.content} />}
              {canRegenerate && (
                <button
                  type="button"
                  title="Regenerate"
                  aria-label="Regenerate"
                  onClick={onRegenerate}
                  className="rounded-md p-1.5 text-zinc-400 transition hover:bg-white/10 hover:text-zinc-100"
                >
                  <RotateCcw className="size-3.5" />
                </button>
              )}
            </div>
            <StatsBar message={message} modelLabel={modelLabel} labelFor={labelFor} />
          </div>
        )}
      </div>
    </div>
  );
}
