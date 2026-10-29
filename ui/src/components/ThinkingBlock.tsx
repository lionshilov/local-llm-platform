import { Brain, ChevronRight } from "lucide-react";
import { useState } from "react";
import { LazyMarkdown } from "./LazyMarkdown";

export function ThinkingBlock({
  text,
  active,
  durationMs,
}: {
  text: string;
  active: boolean;
  durationMs: number | null;
}) {
  const [open, setOpen] = useState(false);
  const title = active
    ? "Thinking…"
    : durationMs
      ? `Thought for ${(durationMs / 1000).toFixed(1)}s`
      : "Reasoning";

  return (
    <div className="mb-3">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="group inline-flex items-center gap-2 rounded-full py-1 text-sm text-zinc-400 transition hover:text-zinc-200"
      >
        <Brain className={`size-4 ${active ? "animate-pulse text-violet-300" : ""}`} />
        <span className={active ? "shimmer-text" : ""}>{title}</span>
        <ChevronRight className={`size-3.5 transition ${open ? "rotate-90" : ""}`} />
      </button>
      {(open || active) && (
        <div className="mt-2 max-h-80 overflow-y-auto border-l-2 border-violet-400/30 pl-4">
          <LazyMarkdown text={text} variant="muted" />
        </div>
      )}
    </div>
  );
}
