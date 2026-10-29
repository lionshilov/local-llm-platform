import { Code2, Lightbulb, Lock, Rocket, Scale } from "lucide-react";

const SUGGESTIONS = [
  {
    icon: Code2,
    title: "Write code",
    prompt: "Write a Python async rate limiter using the token bucket algorithm, with tests.",
  },
  {
    icon: Lightbulb,
    title: "Explain a concept",
    prompt: "Explain how KV caching speeds up LLM inference, with a small numeric example.",
  },
  {
    icon: Scale,
    title: "Compare options",
    prompt: "Compare llama.cpp, MLX and vLLM for serving LLMs. When would you pick each?",
  },
  {
    icon: Rocket,
    title: "Plan a project",
    prompt: "Plan a weekend project that uses a local LLM to organise my notes. Keep it practical.",
  },
];

export function EmptyState({
  modelLabel,
  online,
  onPick,
}: {
  modelLabel: string | null;
  online: boolean;
  onPick: (prompt: string) => void;
}) {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center px-4 pb-8">
      <h1 className="text-center text-3xl font-semibold tracking-tight text-zinc-100 sm:text-4xl">
        What can I help with?
      </h1>
      <p className="mt-3 flex items-center justify-center gap-1.5 text-center text-sm text-zinc-500">
        <Lock className="size-3.5" />
        {online && modelLabel
          ? `${modelLabel} · running on this machine, nothing leaves it`
          : "No engine is running. Start one with make serve-llamacpp"}
      </p>
      <div className="mt-10 grid gap-3 sm:grid-cols-2">
        {SUGGESTIONS.map(({ icon: Icon, title, prompt }) => (
          <button
            type="button"
            key={title}
            disabled={!online}
            onClick={() => onPick(prompt)}
            className="group rounded-2xl border border-white/[0.07] bg-white/[0.02] p-4 text-left transition hover:border-white/15 hover:bg-white/[0.05] disabled:cursor-not-allowed disabled:opacity-50"
          >
            <div className="flex items-center gap-2 text-sm font-medium text-zinc-200">
              <Icon className="size-4 text-violet-300" />
              {title}
            </div>
            <div className="mt-1.5 line-clamp-2 text-sm text-zinc-500 group-hover:text-zinc-400">
              {prompt}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
