/**
 * Visual identity per inference engine, used everywhere a backend appears (avatars,
 * arena columns, monitor cards). Class names are spelled out in full so Tailwind can see
 * them at build time.
 */
export interface EngineMeta {
  name: string;
  /** Two-letter monogram for avatars. */
  monogram: string;
  /** Solid hex colour for SVG strokes and charts. */
  color: string;
  text: string;
  softBg: string;
  border: string;
  dot: string;
  gradient: string;
  glow: string;
}

const ENGINES: Record<string, EngineMeta> = {
  llamacpp: {
    name: "llama.cpp",
    monogram: "LC",
    color: "#f59e0b",
    text: "text-amber-300",
    softBg: "bg-amber-400/10",
    border: "border-amber-400/30",
    dot: "bg-amber-400",
    gradient: "from-amber-400 to-orange-500",
    glow: "shadow-amber-500/25",
  },
  mlx: {
    name: "MLX-LM",
    monogram: "MX",
    color: "#38bdf8",
    text: "text-sky-300",
    softBg: "bg-sky-400/10",
    border: "border-sky-400/30",
    dot: "bg-sky-400",
    gradient: "from-sky-400 to-indigo-500",
    glow: "shadow-sky-500/25",
  },
  ollama: {
    name: "Ollama",
    monogram: "OL",
    color: "#34d399",
    text: "text-emerald-300",
    softBg: "bg-emerald-400/10",
    border: "border-emerald-400/30",
    dot: "bg-emerald-400",
    gradient: "from-emerald-400 to-teal-500",
    glow: "shadow-emerald-500/25",
  },
};

const FALLBACK: EngineMeta = {
  name: "OpenAI-compatible",
  monogram: "AI",
  color: "#a78bfa",
  text: "text-violet-300",
  softBg: "bg-violet-400/10",
  border: "border-violet-400/30",
  dot: "bg-violet-400",
  gradient: "from-violet-500 to-fuchsia-500",
  glow: "shadow-violet-500/25",
};

export function engineMeta(ownedBy: string | undefined): EngineMeta {
  return (ownedBy && ENGINES[ownedBy]) || FALLBACK;
}

/** "Qwen3.5 4B · llama.cpp" → { model: "Qwen3.5 4B", engine: "llama.cpp" } */
export function splitLabel(label: string): { model: string; engine: string } {
  const [model, ...rest] = label.split("·").map((part) => part.trim());
  return { model: model ?? label, engine: rest.join(" · ") };
}
