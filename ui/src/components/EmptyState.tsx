import { Code2, Lightbulb, Lock, Rocket, Scale } from "lucide-react";
import { engineMeta, splitLabel } from "../lib/engines";
import type { ModelInfo } from "../lib/types";
import { BrandMark } from "./BrandMark";
import { EngineAvatar } from "./EngineAvatar";

const SUGGESTIONS = [
  {
    icon: Code2,
    title: "Write code",
    prompt: "Write a Python async rate limiter using the token bucket algorithm, with tests.",
    tint: "text-amber-300 bg-amber-400/10",
  },
  {
    icon: Lightbulb,
    title: "Explain a concept",
    prompt: "Explain how KV caching speeds up LLM inference, with a small numeric example.",
    tint: "text-sky-300 bg-sky-400/10",
  },
  {
    icon: Scale,
    title: "Compare options",
    prompt: "Compare llama.cpp, MLX and vLLM for serving LLMs. When would you pick each?",
    tint: "text-emerald-300 bg-emerald-400/10",
  },
  {
    icon: Rocket,
    title: "Plan a project",
    prompt: "Plan a weekend project that uses a local LLM to organise my notes. Keep it practical.",
    tint: "text-fuchsia-300 bg-fuchsia-400/10",
  },
];

export function EmptyState({
  current,
  models,
  onPick,
  onSelectModel,
}: {
  current: ModelInfo | undefined;
  models: ModelInfo[];
  onPick: (prompt: string) => void;
  onSelectModel: (id: string) => void;
}) {
  const online = !!current?.available;
  const meta = engineMeta(current?.owned_by);

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4">
      <div className="my-auto py-10">
        <div className="flex animate-fade-up flex-col items-center text-center">
          <div className="mb-6">
            <BrandMark size="lg" />
          </div>
          <h1 className="text-gradient text-3xl font-semibold tracking-tight sm:text-[2.6rem] sm:leading-tight">
            What can I help with?
          </h1>
          <p className="mt-3 flex items-center gap-1.5 text-sm text-zinc-500">
            <Lock className="size-3.5" />
            {online && current ? (
              <>
                <span className={meta.text}>{meta.name}</span>
                <span>· {splitLabel(current.label).model} · runs on this machine</span>
              </>
            ) : (
              "No engine online. Start one with make serve-llamacpp"
            )}
          </p>
        </div>

        {models.length > 1 && (
          <div className="mt-6 flex animate-fade-up flex-wrap justify-center gap-2 [animation-delay:60ms]">
            {models.map((m) => {
              const meta = engineMeta(m.owned_by);
              const selected = m.id === current?.id;
              return (
                <button
                  type="button"
                  key={m.id}
                  onClick={() => onSelectModel(m.id)}
                  disabled={!m.available}
                  className={`inline-flex items-center gap-2 rounded-full border py-1 pr-3 pl-1 text-sm transition disabled:cursor-not-allowed disabled:opacity-40 ${
                    selected
                      ? `${meta.border} ${meta.softBg} ${meta.text}`
                      : "border-white/[0.07] text-zinc-400 hover:border-white/15 hover:text-zinc-200"
                  }`}
                >
                  <EngineAvatar engine={m.owned_by} size="sm" />
                  {splitLabel(m.label).engine || meta.name}
                </button>
              );
            })}
          </div>
        )}

        <div className="mt-10 grid gap-3 sm:grid-cols-2">
          {SUGGESTIONS.map(({ icon: Icon, title, prompt, tint }, index) => (
            <button
              type="button"
              key={title}
              disabled={!online}
              onClick={() => onPick(prompt)}
              style={{ animationDelay: `${120 + index * 50}ms` }}
              className={`${index >= 2 ? "hidden sm:block" : ""}group animate-fade-up rounded-2xl glass p-4 text-left transition hover:-translate-y-0.5 hover:border-white/15 hover:bg-white/[0.05] disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:translate-y-0`}
            >
              <div className="flex items-center gap-2.5 text-sm font-medium text-zinc-200">
                <span className={`flex size-7 items-center justify-center rounded-lg ${tint}`}>
                  <Icon className="size-4" />
                </span>
                {title}
              </div>
              <div className="mt-2 line-clamp-2 text-sm text-zinc-500 group-hover:text-zinc-400">
                {prompt}
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
