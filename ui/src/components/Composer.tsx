import { ArrowUp, Brain, Square } from "lucide-react";
import { type ReactNode, type Ref, useEffect, useImperativeHandle, useRef, useState } from "react";

export interface ComposerHandle {
  focus: () => void;
}

export function Composer({
  streaming,
  disabled,
  disabledReason,
  thinking,
  onToggleThinking,
  onSend,
  onStop,
  placeholder = "Message your local model…",
  accessory,
  ref,
}: {
  streaming: boolean;
  disabled: boolean;
  disabledReason?: string;
  thinking: boolean;
  onToggleThinking: () => void;
  onSend: (text: string) => void;
  onStop: () => void;
  placeholder?: string;
  accessory?: ReactNode;
  ref?: Ref<ComposerHandle>;
}) {
  const [text, setText] = useState("");
  const textarea = useRef<HTMLTextAreaElement>(null);

  useImperativeHandle(ref, () => ({ focus: () => textarea.current?.focus() }), []);

  useEffect(() => {
    const el = textarea.current;
    if (!el) return;
    el.style.height = "auto";
    // Hidden (display: none) composers measure 0; keep "auto" until they are shown.
    if (el.scrollHeight > 0) el.style.height = `${Math.min(el.scrollHeight, 240)}px`;
  }, [text]);

  useEffect(() => {
    if (!streaming && !disabled) textarea.current?.focus();
  }, [streaming, disabled]);

  const canSend = text.trim().length > 0 && !disabled && !streaming;
  const submit = () => {
    if (!canSend) return;
    onSend(text.trim());
    setText("");
  };

  return (
    <div
      className={`group/composer relative rounded-[26px] p-px transition ${
        disabled
          ? "bg-white/[0.06]"
          : "bg-gradient-to-b from-white/[0.12] to-white/[0.04] focus-within:from-violet-400/50 focus-within:to-fuchsia-400/20"
      }`}
    >
      <div className="rounded-[25px] bg-zinc-900/95 p-2 shadow-2xl shadow-black/50 backdrop-blur-xl">
        <textarea
          ref={textarea}
          rows={1}
          value={text}
          disabled={disabled}
          placeholder={disabled ? (disabledReason ?? "Unavailable") : placeholder}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              submit();
            }
          }}
          className="block max-h-60 w-full resize-none bg-transparent px-3 pt-2 pb-1 text-[15px] leading-6 text-zinc-100 placeholder:text-zinc-500 focus:outline-none disabled:cursor-not-allowed"
        />
        <div className="flex items-center gap-2 px-1 pt-1">
          <button
            type="button"
            onClick={onToggleThinking}
            aria-pressed={thinking}
            title="Let the model reason before answering (slower, better on hard problems)"
            className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition ${
              thinking
                ? "border-violet-400/40 bg-violet-500/15 text-violet-200 shadow-[0_0_20px_-6px] shadow-violet-500/60"
                : "border-white/10 text-zinc-400 hover:bg-white/5 hover:text-zinc-200"
            }`}
          >
            <Brain className="size-4" />
            Think
          </button>
          {accessory}
          <div className="flex-1" />
          <span className="hidden font-mono text-[11px] text-zinc-600 sm:inline">
            {streaming ? "esc to stop" : "↵ send · ⇧↵ newline"}
          </span>
          {streaming ? (
            <button
              type="button"
              onClick={onStop}
              title="Stop generating (Esc)"
              aria-label="Stop generating"
              className="flex size-9 items-center justify-center rounded-full bg-zinc-100 text-zinc-900 transition hover:bg-white"
            >
              <Square className="size-3.5 fill-current" />
            </button>
          ) : (
            <button
              type="button"
              onClick={submit}
              disabled={!canSend}
              title="Send (Enter)"
              aria-label="Send"
              className="flex size-9 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white shadow-lg shadow-violet-500/30 transition hover:brightness-110 disabled:cursor-not-allowed disabled:from-zinc-700 disabled:to-zinc-700 disabled:text-zinc-500 disabled:shadow-none"
            >
              <ArrowUp className="size-5" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
