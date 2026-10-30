import { Check, ChevronDown } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { engineMeta, splitLabel } from "../lib/engines";
import type { ModelInfo } from "../lib/types";
import { EngineAvatar, StatusDot } from "./EngineAvatar";

export function ModelPicker({
  models,
  value,
  onChange,
  align = "left",
}: {
  models: ModelInfo[];
  value: string | null;
  onChange: (id: string) => void;
  align?: "left" | "right";
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const current = models.find((m) => m.id === value);
  const currentMeta = engineMeta(current?.owned_by);
  const { model: currentModel } = splitLabel(current?.label ?? "Select a model");
  const online = models.filter((m) => m.available).length;

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
    <div ref={ref} className="relative min-w-0">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className="flex max-w-full items-center gap-2.5 rounded-xl py-1.5 pr-2.5 pl-1.5 whitespace-nowrap transition hover:bg-white/[0.05]"
      >
        <EngineAvatar engine={current?.owned_by} size="sm" />
        <span className="flex min-w-0 items-baseline gap-1.5">
          <span
            className={`hidden truncate text-[15px] font-medium min-[420px]:inline ${currentMeta.text}`}
          >
            {current ? currentMeta.name : "No backend"}
          </span>
          <span className="hidden truncate text-sm text-zinc-500 sm:inline">{currentModel}</span>
        </span>
        {current && <StatusDot up={current.available} />}
        <ChevronDown
          className={`size-4 shrink-0 text-zinc-500 transition ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div
          role="listbox"
          className={`absolute top-full z-40 mt-2 w-[22rem] max-w-[calc(100vw-1.5rem)] origin-top animate-scale-in overflow-hidden rounded-2xl glass bg-zinc-900/90 p-1.5 shadow-2xl shadow-black/60 ${align === "right" ? "right-0" : "left-0"}`}
        >
          <div className="flex items-center justify-between px-3 pt-2 pb-1.5">
            <span className="caption">Backends</span>
            <span className="font-mono text-[11px] text-zinc-500">
              {online}/{models.length} online
            </span>
          </div>
          {models.map((m) => {
            const meta = engineMeta(m.owned_by);
            const { model } = splitLabel(m.label);
            return (
              <button
                type="button"
                role="option"
                aria-selected={m.id === value}
                key={m.id}
                onClick={() => {
                  onChange(m.id);
                  setOpen(false);
                }}
                className={`flex w-full items-center gap-3 rounded-xl px-2.5 py-2 text-left transition hover:bg-white/[0.05] ${m.id === value ? "bg-white/[0.04]" : ""}`}
              >
                <EngineAvatar engine={m.owned_by} size="md" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-sm font-medium ${m.available ? meta.text : "text-zinc-500"}`}
                    >
                      {meta.name}
                    </span>
                    <span className="truncate text-sm text-zinc-400">{model}</span>
                  </div>
                  <div className="mt-0.5 flex items-center gap-1.5 font-mono text-[11px] text-zinc-500">
                    <StatusDot up={m.available} />
                    <span>{m.available ? "online" : "offline"}</span>
                    <span className="text-zinc-700">·</span>
                    <span className="truncate">{m.upstream_model}</span>
                  </div>
                </div>
                {m.id === value && <Check className="size-4 shrink-0 text-zinc-300" />}
              </button>
            );
          })}
          {models.length === 0 && (
            <div className="px-3 py-6 text-center text-sm text-zinc-500">
              Gateway unreachable. Run <code className="font-mono text-zinc-300">make gateway</code>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
