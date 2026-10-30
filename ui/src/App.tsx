import { Download, WifiOff } from "lucide-react";
import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
import { AppHeader, type Mode } from "./components/AppHeader";
import { ArenaView } from "./components/ArenaView";
import { Composer, type ComposerHandle } from "./components/Composer";
import { EmptyState } from "./components/EmptyState";
import { MessageView } from "./components/MessageView";
import { ModelPicker } from "./components/ModelPicker";
import { SettingsDialog } from "./components/SettingsDialog";
import { Sidebar } from "./components/Sidebar";
import { useChat } from "./hooks/useChat";
import { useModels } from "./hooks/useModels";
import { conversationToMarkdown, downloadText, slugify } from "./lib/export";
import { loadSettings, saveSettings } from "./lib/storage";

// The dashboard and its Prometheus parsing load only when the Monitor tab opens.
const MonitorView = lazy(() => import("./components/monitor/MonitorView"));

const MODEL_KEY = "llp.model.v1";
const MODE_KEY = "llp.mode.v1";

function isTyping(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  return !!el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable);
}

export default function App() {
  const [settings, setSettings] = useState(loadSettings);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(() => window.innerWidth >= 768);
  const [mode, setMode] = useState<Mode>(
    () => (localStorage.getItem(MODE_KEY) as Mode | null) ?? "chat",
  );
  const [model, setModel] = useState<string | null>(() => localStorage.getItem(MODEL_KEY));
  const gateway = useModels();
  const { models, defaultModel } = gateway;
  const chat = useChat(settings);
  const scrollRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const composer = useRef<ComposerHandle>(null);
  const stickToBottom = useRef(true);

  useEffect(() => saveSettings(settings), [settings]);
  useEffect(() => localStorage.setItem(MODE_KEY, mode), [mode]);
  useEffect(() => {
    if (model) localStorage.setItem(MODEL_KEY, model);
  }, [model]);

  // Keep the saved model if it still exists, else the first online one, else the default.
  useEffect(() => {
    if (models.length === 0 || models.some((m) => m.id === model)) return;
    const online = models.find((m) => m.available);
    setModel(online?.id ?? defaultModel ?? models[0]?.id ?? null);
  }, [models, model, defaultModel]);

  const messages = chat.active?.messages ?? [];
  const lastContent = messages.at(-1)?.content.length ?? 0;
  const lastReasoning = messages.at(-1)?.reasoning?.length ?? 0;
  useEffect(() => {
    const el = scrollRef.current;
    if (el && stickToBottom.current) el.scrollTop = el.scrollHeight;
  }, [messages.length, lastContent, lastReasoning, chat.activeId]);

  // Content also grows without new tokens (lazy markdown chunk, KaTeX fonts, highlighting).
  useEffect(() => {
    const scroller = scrollRef.current;
    const content = contentRef.current;
    if (!scroller || !content) return;
    const observer = new ResizeObserver(() => {
      if (stickToBottom.current) scroller.scrollTop = scroller.scrollHeight;
    });
    observer.observe(content);
    return () => observer.disconnect();
  }, [messages.length > 0, mode]);

  const current = models.find((m) => m.id === model);
  const labelFor = useCallback(
    (id?: string) => models.find((m) => m.id === id)?.label ?? id ?? "model",
    [models],
  );
  const online = !!current?.available;
  const toggleThinking = () => setSettings((s) => ({ ...s, thinking: !s.thinking }));

  const newChat = useCallback(() => {
    setMode("chat");
    chat.newChat();
    setTimeout(() => composer.current?.focus(), 0);
  }, [chat]);

  const send = (text: string) => {
    if (!model) return;
    stickToBottom.current = true;
    chat.send(text, model);
  };

  // ⌘⇧O new chat · Esc stop · / focus the composer
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === "o") {
        e.preventDefault();
        newChat();
      } else if (e.key === "Escape" && chat.streaming && mode === "chat") {
        chat.stop();
      } else if (e.key === "/" && !isTyping(e.target) && mode === "chat") {
        e.preventDefault();
        composer.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [chat, mode, newChat]);

  const exportChat = () => {
    if (!chat.active) return;
    downloadText(
      `${slugify(chat.active.title)}.md`,
      conversationToMarkdown(chat.active, (id) => labelFor(id)),
    );
  };

  return (
    <div className="relative flex h-dvh overflow-hidden">
      <div className="app-backdrop pointer-events-none fixed inset-0" aria-hidden="true" />

      {sidebarOpen && (
        <>
          <div
            className="fixed inset-0 z-30 animate-fade-in bg-black/50 md:hidden"
            onClick={() => setSidebarOpen(false)}
          />
          <div className="fixed inset-y-0 left-0 z-40 md:static">
            <Sidebar
              conversations={chat.conversations}
              activeId={mode === "chat" ? chat.activeId : null}
              models={models}
              selectedModel={model}
              onSelect={(id) => {
                setMode("chat");
                chat.select(id);
                stickToBottom.current = true;
                if (window.innerWidth < 768) setSidebarOpen(false);
              }}
              onNew={newChat}
              onRename={chat.rename}
              onDelete={chat.remove}
              onSelectModel={(id) => {
                setModel(id);
                setMode("chat");
              }}
              onOpenMonitor={() => setMode("monitor")}
              onClose={() => setSidebarOpen(false)}
            />
          </div>
        </>
      )}

      <main className="relative flex min-w-0 flex-1 flex-col">
        <AppHeader
          mode={mode}
          onModeChange={setMode}
          sidebarOpen={sidebarOpen}
          onOpenSidebar={() => setSidebarOpen(true)}
          onNewChat={newChat}
          onOpenSettings={() => setSettingsOpen(true)}
          gateway={{
            status: gateway.status,
            latencyMs: gateway.latencyMs,
            online: models.filter((m) => m.available).length,
            total: models.length,
            onRetry: gateway.refresh,
          }}
          left={
            mode === "chat" ? (
              <ModelPicker models={models} value={model} onChange={setModel} />
            ) : null
          }
          right={
            mode === "chat" && chat.active ? (
              <button
                type="button"
                onClick={exportChat}
                title="Export chat as Markdown"
                aria-label="Export chat as Markdown"
                className="rounded-lg p-2 text-zinc-400 transition hover:bg-white/5 hover:text-zinc-100"
              >
                <Download className="size-5" />
              </button>
            ) : null
          }
        />

        {gateway.status === "offline" && (
          <div className="mx-auto mt-1 mb-2 flex max-w-[calc(100%-2rem)] animate-fade-up items-center gap-2 rounded-full border border-red-400/20 bg-red-500/10 px-4 py-1.5 text-sm text-red-200">
            <WifiOff className="size-4 shrink-0" />
            <span className="truncate">
              Gateway offline. Run <code className="font-mono text-red-100">make gateway</code>;
              this page reconnects automatically.
            </span>
          </div>
        )}

        {mode === "monitor" && (
          <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
            <Suspense fallback={<div className="p-8 text-sm text-zinc-500">Loading metrics…</div>}>
              <MonitorView models={models} />
            </Suspense>
          </div>
        )}

        <div className={mode === "arena" ? "flex min-h-0 flex-1 flex-col" : "hidden"}>
          <ArenaView models={models} settings={settings} onToggleThinking={toggleThinking} />
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
            <EmptyState current={current} models={models} onPick={send} onSelectModel={setModel} />
          ) : (
            <div ref={contentRef} className="mx-auto w-full max-w-3xl space-y-8 px-4 pt-6 pb-10">
              {messages.map((message, index) => (
                <MessageView
                  key={message.id}
                  message={message}
                  model={models.find((m) => m.id === message.model)}
                  labelFor={labelFor}
                  canRegenerate={index === messages.length - 1 && !chat.streaming && online}
                  onRegenerate={() => model && chat.regenerate(model)}
                  canEdit={!chat.streaming && online}
                  onEdit={(text) => {
                    if (!model) return;
                    stickToBottom.current = true;
                    chat.editAndResend(message.id, text, model);
                  }}
                />
              ))}
            </div>
          )}
        </div>

        <div className={mode === "chat" ? "mx-auto w-full max-w-3xl px-4 pb-4" : "hidden"}>
          <Composer
            ref={composer}
            streaming={chat.streaming}
            disabled={!online}
            disabledReason={
              gateway.status === "offline"
                ? "Gateway offline: run make gateway"
                : "This backend is offline: pick another one or start it"
            }
            thinking={settings.thinking}
            onToggleThinking={toggleThinking}
            onSend={send}
            onStop={chat.stop}
          />
          <p className="mt-2 text-center text-[11px] text-zinc-600">
            Runs locally. Metrics under each reply are measured live in your browser.
          </p>
        </div>
      </main>

      {settingsOpen && (
        <SettingsDialog
          settings={settings}
          onChange={setSettings}
          onClose={() => setSettingsOpen(false)}
          onClearHistory={chat.clearAll}
          conversationCount={chat.conversations.length}
        />
      )}
    </div>
  );
}
