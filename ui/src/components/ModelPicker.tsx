import { Check, ChevronDown, Cpu } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { ModelInfo } from "../lib/types";

const ENGINE_NAMES: Record<string, string> = {
  llamacpp: "llama.cpp",
  mlx: "MLX-LM",
  ollama: "Ollama",
  openai: "OpenAI-compatible",
};

function StatusDot({ up }: { up: boolean }) {
  return (
    <span className="relative flex size-2">
      {up && (
        <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-40" />
      )}
      <span
        className={`relative inline-flex size-2 rounded-full ${up ? "bg-emerald-400" : "bg-zinc-600"}`}
      />
    </span>
  );
}

export function ModelPicker({
  models,
  value,
  onChange,
}: {
  models: ModelInfo[];
  value: string | null;
  onChange: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const current = models.find((m) => m.id === value);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    const escape = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-xl px-3 py-2 text-[15px] font-medium text-zinc-100 transition hover:bg-white/5"
      >
        {current ? <StatusDot up={current.available} /> : <Cpu className="size-4" />}
        <span>{current?.label ?? "Select a model"}</span>
        <ChevronDown className="size-4 text-zinc-500" />
      </button>

      {open && (
        <div className="absolute top-full left-0 z-30 mt-2 w-80 overflow-hidden rounded-2xl border border-white/10 bg-zinc-900/95 p-1.5 shadow-2xl shadow-black/50 backdrop-blur">
          <div className="px-3 pt-2 pb-1 text-xs font-medium tracking-wide text-zinc-500 uppercase">
            Local backends
          </div>
          {models.map((m) => (
            <button
              type="button"
              key={m.id}
              onClick={() => {
                onChange(m.id);
                setOpen(false);
              }}
              className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition hover:bg-white/5"
            >
              <StatusDot up={m.available} />
              <div className="min-w-0 flex-1">
                <div className={`text-sm ${m.available ? "text-zinc-100" : "text-zinc-500"}`}>
                  {m.label}
                </div>
                <div className="truncate font-mono text-[11px] text-zinc-500">
                  {ENGINE_NAMES[m.owned_by] ?? m.owned_by} · {m.upstream_model}
                  {!m.available && " · offline"}
                </div>
              </div>
              {m.id === value && <Check className="size-4 text-zinc-300" />}
            </button>
          ))}
          {models.length === 0 && (
            <div className="px-3 py-4 text-sm text-zinc-500">No backends configured.</div>
          )}
        </div>
      )}
    </div>
  );
}
