import { ArrowUp, Brain, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";

export function Composer({
  streaming,
  disabled,
  thinking,
  onToggleThinking,
  onSend,
  onStop,
}: {
  streaming: boolean;
  disabled: boolean;
  thinking: boolean;
  onToggleThinking: () => void;
  onSend: (text: string) => void;
  onStop: () => void;
}) {
  const [text, setText] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 240)}px`;
  }, [text]);

  useEffect(() => {
    if (!streaming) ref.current?.focus();
  }, [streaming]);

  const canSend = text.trim().length > 0 && !disabled && !streaming;
  const submit = () => {
    if (!canSend) return;
    onSend(text.trim());
    setText("");
  };

  return (
    <div className="rounded-[28px] border border-white/10 bg-zinc-900/90 p-2 shadow-2xl shadow-black/40 backdrop-blur transition focus-within:border-white/20">
      <textarea
        ref={ref}
        rows={1}
        value={text}
        autoFocus
        placeholder={disabled ? "Start an engine to chat…" : "Message your local model…"}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            submit();
          }
        }}
        className="block max-h-60 w-full resize-none bg-transparent px-3 pt-2 pb-1 text-[15px] leading-6 text-zinc-100 placeholder:text-zinc-500 focus:outline-none"
      />
      <div className="flex items-center justify-between px-1 pt-1">
        <button
          type="button"
          onClick={onToggleThinking}
          aria-pressed={thinking}
          title="Let the model reason before answering (slower, better on hard problems)"
          className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition ${
            thinking
              ? "border-violet-400/40 bg-violet-500/15 text-violet-200"
              : "border-white/10 text-zinc-400 hover:bg-white/5 hover:text-zinc-200"
          }`}
        >
          <Brain className="size-4" />
          Think
        </button>
        {streaming ? (
          <button
            type="button"
            onClick={onStop}
            title="Stop generating"
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
            className="flex size-9 items-center justify-center rounded-full bg-zinc-100 text-zinc-900 transition hover:bg-white disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-500"
          >
            <ArrowUp className="size-5" />
          </button>
        )}
      </div>
    </div>
  );
}
