import { Activity, MessageSquare, PanelLeftClose, SquarePen, Trash2 } from "lucide-react";
import { GitHubIcon } from "./GitHubIcon";
import type { Conversation } from "../lib/types";

const REPO_URL = "https://github.com/lionshilov/local-llm-platform";

function groupLabel(timestamp: number): string {
  const startOfToday = new Date().setHours(0, 0, 0, 0);
  const day = 24 * 60 * 60 * 1000;
  if (timestamp >= startOfToday) return "Today";
  if (timestamp >= startOfToday - day) return "Yesterday";
  if (timestamp >= startOfToday - 7 * day) return "Previous 7 days";
  return "Older";
}

export function Sidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
  onClose,
}: {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onClose: () => void;
}) {
  const sorted = [...conversations].sort((a, b) => b.updatedAt - a.updatedAt);
  const groups = new Map<string, Conversation[]>();
  for (const c of sorted) {
    const label = groupLabel(c.updatedAt);
    groups.set(label, [...(groups.get(label) ?? []), c]);
  }

  return (
    <aside className="flex h-full w-72 flex-col border-r border-white/5 bg-zinc-925">
      <div className="flex items-center justify-between px-3 pt-3 pb-2">
        <div className="flex items-center gap-2.5 px-2">
          <div className="flex size-7 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500 to-fuchsia-500 text-sm font-bold text-white shadow-lg shadow-violet-500/25">
            L
          </div>
          <span className="font-semibold tracking-tight">Local LLM</span>
        </div>
        <button
          type="button"
          onClick={onClose}
          title="Close sidebar"
          aria-label="Close sidebar"
          className="rounded-lg p-2 text-zinc-400 transition hover:bg-white/5 hover:text-zinc-100"
        >
          <PanelLeftClose className="size-5" />
        </button>
      </div>

      <div className="px-3">
        <button
          type="button"
          onClick={onNew}
          className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm text-zinc-200 transition hover:bg-white/5"
        >
          <SquarePen className="size-4" />
          New chat
        </button>
      </div>

      <nav className="mt-2 flex-1 overflow-y-auto px-3 pb-3">
        {[...groups.entries()].map(([label, items]) => (
          <div key={label} className="mt-4 first:mt-1">
            <div className="px-3 pb-1 text-xs font-medium text-zinc-500">{label}</div>
            {items.map((c) => (
              <div
                key={c.id}
                className={`group flex items-center rounded-xl transition ${
                  c.id === activeId ? "bg-white/[0.07]" : "hover:bg-white/[0.04]"
                }`}
              >
                <button
                  type="button"
                  onClick={() => onSelect(c.id)}
                  className="flex min-w-0 flex-1 items-center gap-2.5 px-3 py-2 text-left text-sm text-zinc-300"
                >
                  <MessageSquare className="size-3.5 shrink-0 text-zinc-500" />
                  <span className="truncate">{c.title}</span>
                </button>
                <button
                  type="button"
                  onClick={() => onDelete(c.id)}
                  title="Delete chat"
                  aria-label={`Delete ${c.title}`}
                  className="mr-1 rounded-lg p-1.5 text-zinc-500 opacity-0 transition group-hover:opacity-100 hover:text-red-300"
                >
                  <Trash2 className="size-3.5" />
                </button>
              </div>
            ))}
          </div>
        ))}
        {conversations.length === 0 && (
          <p className="px-3 pt-4 text-sm text-zinc-500">Your chats stay in this browser.</p>
        )}
      </nav>

      <div className="space-y-0.5 border-t border-white/5 p-3 text-sm">
        <a
          href="/metrics"
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-2.5 rounded-xl px-3 py-2 text-zinc-400 transition hover:bg-white/5 hover:text-zinc-200"
        >
          <Activity className="size-4" />
          Prometheus metrics
        </a>
        <a
          href={REPO_URL}
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-2.5 rounded-xl px-3 py-2 text-zinc-400 transition hover:bg-white/5 hover:text-zinc-200"
        >
          <GitHubIcon className="size-4" />
          Source on GitHub
        </a>
      </div>
    </aside>
  );
}
