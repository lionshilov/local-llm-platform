import { engineMeta } from "../lib/engines";

const SIZES = {
  sm: "size-6 rounded-md text-[9px]",
  md: "size-8 rounded-lg text-[10px]",
  lg: "size-10 rounded-xl text-xs",
};

export function EngineAvatar({
  engine,
  size = "md",
  pulse = false,
}: {
  engine: string | undefined;
  size?: keyof typeof SIZES;
  pulse?: boolean;
}) {
  const meta = engineMeta(engine);
  return (
    <div
      title={meta.name}
      className={`relative flex shrink-0 items-center justify-center bg-gradient-to-br font-mono font-bold tracking-tight text-white shadow-lg ${meta.gradient} ${meta.glow} ${SIZES[size]}`}
    >
      {meta.monogram}
      {pulse && (
        <span className="absolute -top-0.5 -right-0.5 flex size-2.5">
          <span
            className={`absolute inline-flex size-full animate-ping rounded-full opacity-60 ${meta.dot}`}
          />
          <span
            className={`relative inline-flex size-2.5 rounded-full ring-2 ring-zinc-950 ${meta.dot}`}
          />
        </span>
      )}
    </div>
  );
}

export function StatusDot({ up, className = "" }: { up: boolean; className?: string }) {
  return (
    <span className={`relative flex size-2 shrink-0 ${className}`}>
      {up && (
        <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-40" />
      )}
      <span
        className={`relative inline-flex size-2 rounded-full ${up ? "bg-emerald-400" : "bg-zinc-600"}`}
      />
    </span>
  );
}
