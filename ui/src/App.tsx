import { MessagesSquare, PanelLeftOpen, Settings2, SquarePen, Swords, WifiOff } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { ArenaView } from "./components/ArenaView";
import { Composer } from "./components/Composer";
import { EmptyState } from "./components/EmptyState";
import { MessageView } from "./components/MessageView";
import { ModelPicker } from "./components/ModelPicker";
import { SettingsDialog } from "./components/SettingsDialog";
import { Sidebar } from "./components/Sidebar";
import { useChat } from "./hooks/useChat";
import { useModels } from "./hooks/useModels";
import { loadSettings, saveSettings } from "./lib/storage";

const MODEL_KEY = "llp.model.v1";

type Mode = "chat" | "arena";

export default function App() {
  const [settings, setSettings] = useState(loadSettings);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [mode, setMode] = useState<Mode>("chat");
  const [sidebarOpen, setSidebarOpen] = useState(() => window.innerWidth >= 768);
  const [model, setModel] = useState<string | null>(() => localStorage.getItem(MODEL_KEY));
  const { models, defaultModel, error: gatewayError, loaded } = useModels();
  const chat = useChat(settings);
  const scrollRef = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true);

  useEffect(() => saveSettings(settings), [settings]);
  useEffect(() => {
    if (model) localStorage.setItem(MODEL_KEY, model);
  }, [model]);

  // Pick a sensible model once the list arrives: keep the saved one if it still exists,
  // otherwise the first one that is online, otherwise the gateway's default.
  useEffect(() => {
    if (models.length === 0 || models.some((m) => m.id === model)) return;
    const online = models.find((m) => m.available);
    setModel(online?.id ?? defaultModel ?? models[0]?.id ?? null);
  }, [models, model, defaultModel]);

  // Follow the stream unless the user scrolled up to read something.
  const messages = chat.active?.messages ?? [];
  const lastContent = messages.at(-1)?.content.length ?? 0;
  const lastReasoning = messages.at(-1)?.reasoning?.length ?? 0;
  useEffect(() => {
    const el = scrollRef.current;
    if (el && stickToBottom.current) el.scrollTop = el.scrollHeight;
  }, [messages.length, lastContent, lastReasoning, chat.activeId]);

  const current = models.find((m) => m.id === model) ?? null;
  const labelFor = (id?: string) => models.find((m) => m.id === id)?.label ?? id ?? "model";
  const online = !!current?.available;

  const send = (text: string) => {
    if (!model) return;
    stickToBottom.current = true;
    chat.send(text, model);
  };

  return (
    <div className="flex h-dvh overflow-hidden bg-zinc-950 text-zinc-100">
      {sidebarOpen && (
        <>
          <div
            className="fixed inset-0 z-30 bg-black/50 md:hidden"
            onClick={() => setSidebarOpen(false)}
          />
          <div className="fixed inset-y-0 left-0 z-40 md:static">
            <Sidebar
              conversations={chat.conversations}
              activeId={chat.activeId}
              onSelect={(id) => {
                setMode("chat");
                chat.select(id);
                stickToBottom.current = true;
                if (window.innerWidth < 768) setSidebarOpen(false);
              }}
              onNew={() => {
                setMode("chat");
                chat.newChat();
              }}
              onDelete={chat.remove}
              onClose={() => setSidebarOpen(false)}
            />
          </div>
        </>
      )}

      <main className="relative flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-1 px-3">
          {!sidebarOpen && (
            <>
              <button
                type="button"
                onClick={() => setSidebarOpen(true)}
                title="Open sidebar"
                aria-label="Open sidebar"
                className="rounded-lg p-2 text-zinc-400 transition hover:bg-white/5 hover:text-zinc-100"
              >
                <PanelLeftOpen className="size-5" />
              </button>
              <button
                type="button"
                onClick={() => {
                  setMode("chat");
                  chat.newChat();
                }}
                title="New chat"
                aria-label="New chat"
                className="rounded-lg p-2 text-zinc-400 transition hover:bg-white/5 hover:text-zinc-100"
              >
                <SquarePen className="size-5" />
              </button>
            </>
          )}
          {mode === "chat" && <ModelPicker models={models} value={model} onChange={setModel} />}
          <div className="flex-1" />
          <div className="mr-1 flex rounded-xl border border-white/10 p-0.5 text-sm">
            {(
              [
                ["chat", "Chat", MessagesSquare],
                ["arena", "Arena", Swords],
              ] as const
            ).map(([value, label, Icon]) => (
              <button
                type="button"
                key={value}
                onClick={() => setMode(value)}
                aria-pressed={mode === value}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 transition ${
                  mode === value ? "bg-white/10 text-zinc-100" : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                <Icon className="size-4" />
                {label}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() => setSettingsOpen(true)}
            title="Settings"
            aria-label="Settings"
            className="rounded-lg p-2 text-zinc-400 transition hover:bg-white/5 hover:text-zinc-100"
          >
            <Settings2 className="size-5" />
          </button>
        </header>

        {gatewayError && loaded && (
          <div className="mx-auto mt-2 flex items-center gap-2 rounded-full border border-amber-500/20 bg-amber-500/10 px-4 py-1.5 text-sm text-amber-200">
            <WifiOff className="size-4" />
            Gateway unreachable: {gatewayError}. Run <code className="font-mono">make gateway</code>
          </div>
        )}

        <div className={mode === "arena" ? "flex min-h-0 flex-1 flex-col" : "hidden"}>
          <ArenaView
            models={models}
            settings={settings}
            onToggleThinking={() => setSettings((s) => ({ ...s, thinking: !s.thinking }))}
          />
        </div>

        <div
          ref={scrollRef}
          onScroll={(e) => {
            const el = e.currentTarget;
            stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
          }}
          className={mode === "chat" ? "flex flex-1 flex-col overflow-y-auto" : "hidden"}
        >
          {messages.length === 0 ? (
            <EmptyState modelLabel={current?.label ?? null} online={online} onPick={send} />
          ) : (
            <div className="mx-auto w-full max-w-3xl space-y-8 px-4 pt-6 pb-10">
              {messages.map((message, index) => (
                <MessageView
                  key={message.id}
                  message={message}
                  modelLabel={labelFor(message.model)}
                  labelFor={labelFor}
                  canRegenerate={index === messages.length - 1 && !chat.streaming && online}
                  onRegenerate={() => model && chat.regenerate(model)}
                />
              ))}
            </div>
          )}
        </div>

        <div className={mode === "chat" ? "mx-auto w-full max-w-3xl px-4 pb-4" : "hidden"}>
          <Composer
            streaming={chat.streaming}
            disabled={!online}
            thinking={settings.thinking}
            onToggleThinking={() => setSettings((s) => ({ ...s, thinking: !s.thinking }))}
            onSend={send}
            onStop={chat.stop}
          />
          <p className="mt-2 text-center text-xs text-zinc-600">
            Local models make mistakes. Metrics under each reply are measured live in your browser.
          </p>
        </div>
      </main>

      {settingsOpen && (
        <SettingsDialog
          settings={settings}
          onChange={setSettings}
          onClose={() => setSettingsOpen(false)}
        />
      )}
    </div>
  );
}
