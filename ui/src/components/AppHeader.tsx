import {
  Activity,
  MessagesSquare,
  PanelLeftOpen,
  Settings2,
  SquarePen,
  Swords,
} from "lucide-react";
import type { ReactNode } from "react";
import type { GatewayStatus } from "../hooks/useModels";

export type Mode = "chat" | "arena" | "monitor";

const MODES = [
  { value: "chat", label: "Chat", icon: MessagesSquare },
  { value: "arena", label: "Arena", icon: Swords },
  { value: "monitor", label: "Monitor", icon: Activity },
] as const;

function ModeSwitch({ mode, onChange }: { mode: Mode; onChange: (mode: Mode) => void }) {
  const index = MODES.findIndex((m) => m.value === mode);
  return (
    <div className="relative grid shrink-0 grid-cols-3 rounded-xl glass p-0.5 text-sm">
      <span
        aria-hidden="true"
        className="absolute inset-y-0.5 left-0.5 w-[calc((100%-4px)/3)] rounded-[10px] bg-white/[0.09] shadow-inner shadow-white/5 transition-transform duration-300 ease-out"
        style={{ transform: `translateX(${index * 100}%)` }}
      />
      {MODES.map(({ value, label, icon: Icon }) => (
        <button
          type="button"
          key={value}
          onClick={() => onChange(value)}
          aria-pressed={mode === value}
          aria-label={label}
          title={label}
          className={`relative z-10 flex items-center justify-center gap-1.5 rounded-[10px] px-3 py-1.5 transition ${
            mode === value ? "text-zinc-100" : "text-zinc-500 hover:text-zinc-300"
          }`}
        >
          <Icon className="size-4" />
          <span className="hidden md:inline">{label}</span>
        </button>
      ))}
    </div>
  );
}

function GatewayPill({
  status,
  latencyMs,
  online,
  total,
  onRetry,
}: {
  status: GatewayStatus;
  latencyMs: number | null;
  online: number;
  total: number;
  onRetry: () => void;
}) {
  if (status === "offline") {
    return (
      <button
        type="button"
        onClick={onRetry}
        title="The gateway is not responding. Start it with `make gateway`, then click to retry."
        className="flex items-center gap-2 rounded-full border border-red-400/25 bg-red-500/10 px-3 py-1.5 text-xs text-red-200 transition hover:bg-red-500/15"
      >
        <span className="size-1.5 rounded-full bg-red-400" />
        Gateway offline
      </button>
    );
  }
  const live = status === "online";
  return (
    <div
      title={live ? `Gateway round-trip ${Math.round(latencyMs ?? 0)} ms` : "Connecting…"}
      className="hidden items-center gap-2 rounded-full border border-white/[0.07] bg-white/[0.03] px-3 py-1.5 font-mono text-[11px] text-zinc-400 sm:flex"
    >
      <span className="relative flex size-1.5">
        {live && (
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-60" />
        )}
        <span
          className={`relative inline-flex size-1.5 rounded-full ${live ? "bg-emerald-400" : "bg-zinc-500"}`}
        />
      </span>
      {live ? `${online}/${total} engines · ${Math.round(latencyMs ?? 0)} ms` : "connecting"}
    </div>
  );
}

export function AppHeader({
  mode,
  onModeChange,
  sidebarOpen,
  onOpenSidebar,
  onNewChat,
  onOpenSettings,
  gateway,
  left,
  right,
}: {
  mode: Mode;
  onModeChange: (mode: Mode) => void;
  sidebarOpen: boolean;
  onOpenSidebar: () => void;
  onNewChat: () => void;
  onOpenSettings: () => void;
  gateway: {
    status: GatewayStatus;
    latencyMs: number | null;
    online: number;
    total: number;
    onRetry: () => void;
  };
  left?: ReactNode;
  right?: ReactNode;
}) {
  const iconButton =
    "rounded-lg p-2 text-zinc-400 transition hover:bg-white/5 hover:text-zinc-100 shrink-0";
  return (
    <header className="relative z-30 flex h-14 shrink-0 items-center gap-1.5 border-b border-white/[0.04] bg-ink/70 px-3 backdrop-blur-xl">
      {!sidebarOpen && (
        <>
          <button
            type="button"
            onClick={onOpenSidebar}
            title="Open sidebar"
            aria-label="Open sidebar"
            className={iconButton}
          >
            <PanelLeftOpen className="size-5" />
          </button>
          <button
            type="button"
            onClick={onNewChat}
            title="New chat (⌘⇧O)"
            aria-label="New chat"
            className={iconButton}
          >
            <SquarePen className="size-5" />
          </button>
        </>
      )}
      <div className="flex min-w-0 flex-1 items-center gap-1">{left}</div>
      <ModeSwitch mode={mode} onChange={onModeChange} />
      <div className="flex shrink-0 items-center justify-end gap-1.5 md:flex-1">
        {right}
        <GatewayPill {...gateway} />
        <button
          type="button"
          onClick={onOpenSettings}
          title="Settings"
          aria-label="Settings"
          className={iconButton}
        >
          <Settings2 className="size-5" />
        </button>
      </div>
    </header>
  );
}
