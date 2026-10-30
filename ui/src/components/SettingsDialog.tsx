import { Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { DEFAULT_SETTINGS } from "../lib/storage";
import type { Settings } from "../lib/types";

const PRESETS = [
  { name: "Default", prompt: "" },
  {
    name: "Senior engineer",
    prompt:
      "You are a pragmatic senior software engineer. Answer concisely, show code when useful, and point out trade-offs.",
  },
  {
    name: "Russian",
    prompt: "Always answer in Russian, clearly and concisely, keeping technical terms in English.",
  },
  {
    name: "Code reviewer",
    prompt:
      "You review code. List concrete problems (bugs, security, performance, readability) ordered by severity, each with a fix.",
  },
  {
    name: "Teacher",
    prompt:
      "Explain like a patient teacher: start from intuition, then the details, then a small worked example.",
  },
];

function temperatureLabel(t: number): string {
  if (t === 0) return "deterministic";
  if (t < 0.5) return "focused";
  if (t <= 1) return "balanced";
  return "creative";
}

export function SettingsDialog({
  settings,
  onChange,
  onClose,
  onClearHistory,
  conversationCount,
}: {
  settings: Settings;
  onChange: (settings: Settings) => void;
  onClose: () => void;
  onClearHistory: () => void;
  conversationCount: number;
}) {
  const [confirmClear, setConfirmClear] = useState(false);

  useEffect(() => {
    const escape = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex animate-fade-in items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        className="w-full max-w-xl animate-scale-in rounded-3xl border border-white/10 bg-zinc-900/95 shadow-2xl shadow-black/60"
      >
        <div className="flex items-center justify-between border-b border-white/[0.06] px-6 py-4">
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

        <div className="space-y-6 px-6 py-5">
          <section>
            <div className="flex items-baseline justify-between">
              <label className="text-sm font-medium text-zinc-200" htmlFor="system-prompt">
                System prompt
              </label>
              <span className="text-xs text-zinc-500">applies to new replies</span>
            </div>
            <div className="mt-2.5 flex flex-wrap gap-1.5">
              {PRESETS.map((preset) => {
                const active = settings.systemPrompt === preset.prompt;
                return (
                  <button
                    type="button"
                    key={preset.name}
                    onClick={() => onChange({ ...settings, systemPrompt: preset.prompt })}
                    className={`rounded-full border px-3 py-1 text-xs transition ${
                      active
                        ? "border-violet-400/40 bg-violet-500/15 text-violet-200"
                        : "border-white/10 text-zinc-400 hover:text-zinc-200"
                    }`}
                  >
                    {preset.name}
                  </button>
                );
              })}
            </div>
            <textarea
              id="system-prompt"
              rows={4}
              value={settings.systemPrompt}
              placeholder="No system prompt: the model's default behaviour."
              onChange={(e) => onChange({ ...settings, systemPrompt: e.target.value })}
              className="mt-2.5 w-full resize-none rounded-xl border border-white/10 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-violet-400/50 focus:outline-none"
            />
          </section>

          <section className="grid gap-6 sm:grid-cols-2">
            <div>
              <div className="flex items-center justify-between text-sm">
                <label htmlFor="temperature" className="font-medium text-zinc-200">
                  Temperature
                </label>
                <span className="font-mono text-zinc-400">
                  {settings.temperature.toFixed(1)}{" "}
                  <span className="text-zinc-600">{temperatureLabel(settings.temperature)}</span>
                </span>
              </div>
              <input
                id="temperature"
                type="range"
                min={0}
                max={1.5}
                step={0.1}
                value={settings.temperature}
                onChange={(e) => onChange({ ...settings, temperature: Number(e.target.value) })}
                className="mt-3 w-full accent-violet-400"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-zinc-200" htmlFor="max-tokens">
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
                  onChange({ ...settings, maxTokens: Math.max(16, Number(e.target.value) || 16) })
                }
                className="mt-2 w-full rounded-xl border border-white/10 bg-zinc-950 px-3 py-2 font-mono text-sm text-zinc-100 focus:border-violet-400/50 focus:outline-none"
              />
            </div>
          </section>

          <section className="rounded-2xl border border-red-500/15 bg-red-500/[0.04] p-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <div className="text-sm font-medium text-zinc-200">Chat history</div>
                <div className="text-xs text-zinc-500">
                  {conversationCount} conversation{conversationCount === 1 ? "" : "s"} stored in
                  this browser
                </div>
              </div>
              <button
                type="button"
                disabled={conversationCount === 0}
                onClick={() => {
                  if (!confirmClear) {
                    setConfirmClear(true);
                    return;
                  }
                  onClearHistory();
                  setConfirmClear(false);
                }}
                className="inline-flex items-center gap-1.5 rounded-xl border border-red-400/25 px-3 py-1.5 text-sm text-red-200 transition hover:bg-red-500/10 disabled:opacity-40"
              >
                <Trash2 className="size-3.5" />
                {confirmClear ? "Click again to delete" : "Delete all"}
              </button>
            </div>
          </section>
        </div>

        <div className="flex justify-between border-t border-white/[0.06] px-6 py-4">
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
