import { X } from "lucide-react";
import { useEffect } from "react";
import { DEFAULT_SETTINGS } from "../lib/storage";
import type { Settings } from "../lib/types";

export function SettingsDialog({
  settings,
  onChange,
  onClose,
}: {
  settings: Settings;
  onChange: (settings: Settings) => void;
  onClose: () => void;
}) {
  useEffect(() => {
    const escape = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        className="w-full max-w-lg rounded-3xl border border-white/10 bg-zinc-900 p-6 shadow-2xl"
      >
        <div className="flex items-center justify-between">
          <h2 id="settings-title" className="text-lg font-semibold">
            Settings
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close settings"
            className="rounded-lg p-1.5 text-zinc-400 hover:bg-white/5 hover:text-zinc-100"
          >
            <X className="size-5" />
          </button>
        </div>

        <label className="mt-6 block text-sm font-medium text-zinc-300" htmlFor="system-prompt">
          System prompt
        </label>
        <textarea
          id="system-prompt"
          rows={4}
          value={settings.systemPrompt}
          placeholder="You are a concise senior engineer…"
          onChange={(e) => onChange({ ...settings, systemPrompt: e.target.value })}
          className="mt-2 w-full resize-none rounded-xl border border-white/10 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-violet-400/50 focus:outline-none"
        />

        <div className="mt-5 flex items-center justify-between text-sm">
          <label htmlFor="temperature" className="font-medium text-zinc-300">
            Temperature
          </label>
          <span className="font-mono text-zinc-400">{settings.temperature.toFixed(1)}</span>
        </div>
        <input
          id="temperature"
          type="range"
          min={0}
          max={1.5}
          step={0.1}
          value={settings.temperature}
          onChange={(e) => onChange({ ...settings, temperature: Number(e.target.value) })}
          className="mt-2 w-full accent-violet-400"
        />
        <p className="mt-1 text-xs text-zinc-500">0 = deterministic, higher = more varied.</p>

        <label className="mt-5 block text-sm font-medium text-zinc-300" htmlFor="max-tokens">
          Max response tokens
        </label>
        <input
          id="max-tokens"
          type="number"
          min={16}
          max={32768}
          step={256}
          value={settings.maxTokens}
          onChange={(e) =>
            onChange({
              ...settings,
              maxTokens: Math.max(16, Number(e.target.value) || 16),
            })
          }
          className="mt-2 w-40 rounded-xl border border-white/10 bg-zinc-950 px-3 py-2 font-mono text-sm text-zinc-100 focus:border-violet-400/50 focus:outline-none"
        />

        <div className="mt-8 flex justify-between">
          <button
            type="button"
            onClick={() => onChange({ ...DEFAULT_SETTINGS, thinking: settings.thinking })}
            className="rounded-xl px-4 py-2 text-sm text-zinc-400 hover:bg-white/5 hover:text-zinc-200"
          >
            Reset defaults
          </button>
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl bg-zinc-100 px-5 py-2 text-sm font-medium text-zinc-900 hover:bg-white"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
