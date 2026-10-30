import { AlertTriangle, Check, Pencil, RotateCcw, X } from "lucide-react";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { engineMeta, splitLabel } from "../lib/engines";
import type { ChatMessage, ModelInfo } from "../lib/types";
import { CopyButton } from "./CopyButton";
import { EngineAvatar } from "./EngineAvatar";
import { LazyMarkdown } from "./LazyMarkdown";
import { MetricChips } from "./MetricChips";
import { ThinkingBlock } from "./ThinkingBlock";

function IconButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      onClick={onClick}
      className="rounded-md p-1.5 text-zinc-500 transition hover:bg-white/10 hover:text-zinc-100"
    >
      {children}
    </button>
  );
}

function UserMessage({
  message,
  canEdit,
  onEdit,
}: {
  message: ChatMessage;
  canEdit: boolean;
  onEdit?: (text: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(message.content);
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!editing || !ref.current) return;
    ref.current.focus();
    ref.current.style.height = "auto";
    ref.current.style.height = `${ref.current.scrollHeight}px`;
  }, [editing, draft]);

  if (editing) {
    const save = () => {
      if (draft.trim() && draft.trim() !== message.content) onEdit?.(draft.trim());
      setEditing(false);
    };
    return (
      <div className="ml-auto w-full max-w-[85%] animate-fade-in rounded-3xl border border-violet-400/30 bg-zinc-900 p-3">
        <textarea
          ref={ref}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              save();
            }
            if (e.key === "Escape") setEditing(false);
          }}
          className="block w-full resize-none bg-transparent px-2 leading-7 text-zinc-100 focus:outline-none"
        />
        <div className="mt-2 flex justify-end gap-2">
          <button
            type="button"
            onClick={() => setEditing(false)}
            className="inline-flex items-center gap-1 rounded-full px-3 py-1.5 text-sm text-zinc-400 hover:bg-white/5"
          >
            <X className="size-3.5" /> Cancel
          </button>
          <button
            type="button"
            onClick={save}
            className="inline-flex items-center gap-1 rounded-full bg-zinc-100 px-3 py-1.5 text-sm font-medium text-zinc-900 hover:bg-white"
          >
            <Check className="size-3.5" /> Send
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="group flex animate-fade-up flex-col items-end gap-1">
      <div className="max-w-[85%] rounded-3xl rounded-br-lg border border-white/[0.06] bg-gradient-to-b from-zinc-800/90 to-zinc-800/60 px-5 py-2.5 leading-7 whitespace-pre-wrap text-zinc-100 shadow-lg shadow-black/20">
        {message.content}
      </div>
      <div className="flex items-center opacity-0 transition group-hover:opacity-100 focus-within:opacity-100">
        <CopyButton text={message.content} />
        {canEdit && (
          <IconButton
            label="Edit and resend"
            onClick={() => {
              setDraft(message.content);
              setEditing(true);
            }}
          >
            <Pencil className="size-3.5" />
          </IconButton>
        )}
      </div>
    </div>
  );
}

export function MessageView({
  message,
  model,
  labelFor,
  canRegenerate = false,
  onRegenerate,
  canEdit = false,
  onEdit,
  compact = false,
}: {
  message: ChatMessage;
  model: ModelInfo | undefined;
  labelFor: (id: string) => string;
  canRegenerate?: boolean;
  onRegenerate?: () => void;
  canEdit?: boolean;
  onEdit?: (text: string) => void;
  compact?: boolean;
}) {
  if (message.role === "user") {
    return <UserMessage message={message} canEdit={canEdit} onEdit={onEdit} />;
  }

  const streaming = message.status === "streaming";
  const waiting = streaming && !message.content && !message.reasoning;
  const thinkingActive = streaming && !!message.reasoning && !message.content;
  const meta = engineMeta(model?.owned_by);
  const { model: modelName } = splitLabel(model?.label ?? message.model ?? "model");

  return (
    <div className="group flex animate-fade-up gap-3.5">
      {!compact && <EngineAvatar engine={model?.owned_by} pulse={streaming} />}
      <div className="min-w-0 flex-1">
        {!compact && (
          <div className="mb-1.5 flex items-center gap-2 text-[13px]">
            <span className={`font-medium ${meta.text}`}>{meta.name}</span>
            <span className="text-zinc-600">·</span>
            <span className="text-zinc-500">{modelName}</span>
          </div>
        )}

        {message.reasoning ? (
          <ThinkingBlock
            text={message.reasoning}
            active={thinkingActive}
            durationMs={message.stats?.thinkingMs ?? null}
          />
        ) : null}

        {waiting ? (
          <div className="flex h-8 items-center gap-1.5">
            <span className="typing-dot" />
            <span className="typing-dot [animation-delay:150ms]" />
            <span className="typing-dot [animation-delay:300ms]" />
          </div>
        ) : (
          message.content && <LazyMarkdown text={message.content} streaming={streaming} />
        )}

        {message.status === "error" && (
          <div className="mt-2 flex items-start gap-2 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-200">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" />
            <span className="break-words">{message.error}</span>
          </div>
        )}

        <div className="mt-2.5 flex flex-wrap items-center gap-2">
          {!streaming && (
            <div className="flex items-center">
              {message.content && <CopyButton text={message.content} />}
              {canRegenerate && onRegenerate && (
                <IconButton label="Regenerate" onClick={onRegenerate}>
                  <RotateCcw className="size-3.5" />
                </IconButton>
              )}
            </div>
          )}
          <MetricChips message={message} labelFor={labelFor} />
        </div>
      </div>
    </div>
  );
}
