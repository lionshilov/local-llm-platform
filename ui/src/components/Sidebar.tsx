import { Activity, PanelLeftClose, Pencil, Search, SquarePen, Trash2, X } from "lucide-react";
import { useMemo, useState } from "react";
import { engineMeta, splitLabel } from "../lib/engines";
import type { Conversation, ModelInfo } from "../lib/types";
import { EngineAvatar, StatusDot } from "./EngineAvatar";
import { BrandMark } from "./BrandMark";
import { GitHubIcon } from "./GitHubIcon";

const REPO_URL = "https://github.com/lionshilov/local-llm-platform";
const DAY = 24 * 60 * 60 * 1000;

function groupLabel(timestamp: number): string {
  const startOfToday = new Date().setHours(0, 0, 0, 0);
  if (timestamp >= startOfToday) return "Today";
  if (timestamp >= startOfToday - DAY) return "Yesterday";
  if (timestamp >= startOfToday - 7 * DAY) return "Previous 7 days";
  return "Older";
}

function ConversationItem({
  conversation,
  active,
  engine,
  onSelect,
  onRename,
  onDelete,
}: {
  conversation: Conversation;
  active: boolean;
  engine: string | undefined;
  onSelect: () => void;
  onRename: (title: string) => void;
  onDelete: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(conversation.title);
  const meta = engineMeta(engine);

  if (editing) {
    const commit = () => {
      onRename(draft);
      setEditing(false);
    };
    return (
      <div className="flex items-center gap-1 rounded-xl bg-white/[0.06] px-2 py-1">
        <input
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === "Enter") commit();
            if (e.key === "Escape") setEditing(false);
          }}
          className="min-w-0 flex-1 bg-transparent px-1 py-1 text-sm text-zinc-100 focus:outline-none"
        />
      </div>
    );
  }

  return (
    <div
      className={`group relative flex items-center rounded-xl transition ${
        active ? "bg-white/[0.07]" : "hover:bg-white/[0.04]"
      }`}
    >
      {active && (
        <span
          className={`absolute top-2 bottom-2 left-0 w-0.5 rounded-full bg-gradient-to-b ${meta.gradient}`}
        />
      )}
      <button
        type="button"
        onClick={onSelect}
        onDoubleClick={() => {
          setDraft(conversation.title);
          setEditing(true);
        }}
        className="flex min-w-0 flex-1 items-center gap-2.5 py-2 pr-1 pl-3 text-left text-sm text-zinc-300"
      >
        <span className={`size-1.5 shrink-0 rounded-full ${meta.dot}`} />
        <span className="truncate">{conversation.title}</span>
      </button>
      <div className="mr-1 flex shrink-0 opacity-0 transition group-hover:opacity-100 focus-within:opacity-100">
        <button
          type="button"
          onClick={() => {
            setDraft(conversation.title);
            setEditing(true);
          }}
          title="Rename"
          aria-label={`Rename ${conversation.title}`}
          className="rounded-lg p-1.5 text-zinc-500 hover:text-zinc-200"
        >
          <Pencil className="size-3.5" />
        </button>
        <button
          type="button"
          onClick={onDelete}
          title="Delete"
          aria-label={`Delete ${conversation.title}`}
          className="rounded-lg p-1.5 text-zinc-500 hover:text-red-300"
        >
          <Trash2 className="size-3.5" />
        </button>
      </div>
    </div>
  );
}

export function Sidebar({
  conversations,
  activeId,
  models,
  selectedModel,
  onSelect,
  onNew,
  onRename,
  onDelete,
  onSelectModel,
  onOpenMonitor,
  onClose,
}: {
  conversations: Conversation[];
  activeId: string | null;
  models: ModelInfo[];
  selectedModel: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
  onSelectModel: (id: string) => void;
  onOpenMonitor: () => void;
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const engineOf = (id: string) => models.find((m) => m.id === id)?.owned_by;

  const groups = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const matches = conversations
      .filter(
        (c) =>
          !needle ||
          c.title.toLowerCase().includes(needle) ||
          c.messages.some((m) => m.content.toLowerCase().includes(needle)),
      )
      .sort((a, b) => b.updatedAt - a.updatedAt);
    const grouped = new Map<string, Conversation[]>();
    for (const c of matches) {
      const label = groupLabel(c.updatedAt);
      grouped.set(label, [...(grouped.get(label) ?? []), c]);
    }
    return [...grouped.entries()];
  }, [conversations, query]);

  return (
    <aside className="flex h-full w-72 flex-col border-r border-white/[0.06] bg-zinc-950/80 backdrop-blur-xl">
      <div className="flex items-center justify-between px-3 pt-3 pb-2">
        <div className="flex items-center gap-2.5 px-1.5">
          <BrandMark />
          <div className="leading-tight">
            <div className="text-[15px] font-semibold tracking-tight">Local LLM</div>
            <div className="text-[11px] text-zinc-500">platform</div>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          title="Close sidebar"
          aria-label="Close sidebar"
          className="rounded-lg p-2 text-zinc-500 transition hover:bg-white/5 hover:text-zinc-100"
        >
          <PanelLeftClose className="size-5" />
        </button>
      </div>

      <div className="space-y-2 px-3 pt-1">
        <button
          type="button"
          onClick={onNew}
          className="flex w-full items-center gap-2.5 rounded-xl glass px-3 py-2.5 text-sm text-zinc-100 transition hover:border-white/15 hover:bg-white/[0.06]"
        >
          <SquarePen className="size-4" />
          New chat
          <kbd className="ml-auto font-mono text-[10px] text-zinc-500">⌘⇧O</kbd>
        </button>
        <label className="flex items-center gap-2 rounded-xl border border-transparent bg-white/[0.03] px-3 py-2 text-sm text-zinc-400 focus-within:border-white/10">
          <Search className="size-4 shrink-0" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search chats"
            className="min-w-0 flex-1 bg-transparent text-zinc-200 placeholder:text-zinc-500 focus:outline-none"
          />
          {query && (
            <button type="button" onClick={() => setQuery("")} aria-label="Clear search">
              <X className="size-3.5" />
            </button>
          )}
        </label>
      </div>

      <nav className="mt-3 flex-1 overflow-y-auto px-3 pb-3">
        {groups.map(([label, items]) => (
          <div key={label} className="mt-4 first:mt-1">
            <div className="px-3 pb-1.5 caption">{label}</div>
            <div className="space-y-0.5">
              {items.map((c) => (
                <ConversationItem
                  key={c.id}
                  conversation={c}
                  active={c.id === activeId}
                  engine={engineOf(c.model)}
                  onSelect={() => onSelect(c.id)}
                  onRename={(title) => onRename(c.id, title)}
                  onDelete={() => onDelete(c.id)}
                />
              ))}
            </div>
          </div>
        ))}
        {groups.length === 0 && (
          <p className="px-3 pt-6 text-center text-sm text-zinc-500">
            {query ? "No chats match your search." : "Your chats stay in this browser."}
          </p>
        )}
      </nav>

      <div className="border-t border-white/[0.06] p-3">
        <div className="flex items-center justify-between px-2 pb-2">
          <span className="caption">Engines</span>
          <span className="font-mono text-[11px] text-zinc-500">
            {models.filter((m) => m.available).length}/{models.length} online
          </span>
        </div>
        <div className="space-y-0.5">
          {models.map((m) => {
            const meta = engineMeta(m.owned_by);
            return (
              <button
                type="button"
                key={m.id}
                onClick={() => onSelectModel(m.id)}
                className={`flex w-full items-center gap-2.5 rounded-lg px-2 py-1.5 text-left text-[13px] transition hover:bg-white/[0.04] ${
                  m.id === selectedModel ? "bg-white/[0.04]" : ""
                }`}
              >
                <EngineAvatar engine={m.owned_by} size="sm" />
                <span className={m.available ? "text-zinc-300" : "text-zinc-600"}>
                  {splitLabel(m.label).engine || meta.name}
                </span>
                <StatusDot up={m.available} className="ml-auto" />
              </button>
            );
          })}
        </div>
        <div className="mt-2 flex items-center gap-1 border-t border-white/[0.06] pt-2">
          <button
            type="button"
            onClick={onOpenMonitor}
            className="flex flex-1 items-center gap-2 rounded-lg px-2 py-1.5 text-[13px] text-zinc-400 transition hover:bg-white/[0.04] hover:text-zinc-200"
          >
            <Activity className="size-4" />
            Live metrics
          </button>
          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer"
            title="Source on GitHub"
            aria-label="Source on GitHub"
            className="rounded-lg p-2 text-zinc-500 transition hover:bg-white/[0.04] hover:text-zinc-200"
          >
            <GitHubIcon className="size-4" />
          </a>
        </div>
      </div>
    </aside>
  );
}
