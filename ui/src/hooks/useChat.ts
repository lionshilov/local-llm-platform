import { useCallback, useEffect, useRef, useState } from "react";
import { streamReply } from "../lib/reply";
import { loadConversations, newId, saveConversations } from "../lib/storage";
import type { ChatMessage, Conversation, Settings } from "../lib/types";

function titleFrom(text: string): string {
  const line = text.trim().split("\n")[0] ?? "";
  return line.length > 48 ? `${line.slice(0, 45)}…` : line || "New chat";
}

export function useChat(settings: Settings) {
  const [conversations, setConversations] = useState<Conversation[]>(loadConversations);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  // Persist, but not on every token: debounce while text is streaming in.
  useEffect(() => {
    const timer = setTimeout(() => saveConversations(conversations), streaming ? 1000 : 0);
    return () => clearTimeout(timer);
  }, [conversations, streaming]);

  const active = conversations.find((c) => c.id === activeId) ?? null;

  const patchMessage = useCallback(
    (conversationId: string, messageId: string, patch: Partial<ChatMessage>) => {
      setConversations((all) =>
        all.map((c) =>
          c.id !== conversationId
            ? c
            : {
                ...c,
                updatedAt: Date.now(),
                messages: c.messages.map((m) => (m.id === messageId ? { ...m, ...patch } : m)),
              },
        ),
      );
    },
    [],
  );

  const generate = useCallback(
    async (conversationId: string, history: ChatMessage[], model: string) => {
      const reply: ChatMessage = {
        id: newId(),
        role: "assistant",
        content: "",
        reasoning: "",
        model,
        status: "streaming",
      };
      setConversations((all) =>
        all.map((c) =>
          c.id === conversationId
            ? { ...c, model, updatedAt: Date.now(), messages: [...history, reply] }
            : c,
        ),
      );

      const controller = new AbortController();
      abortRef.current = controller;
      setStreaming(true);
      const result = await streamReply({
        model,
        history,
        settings,
        signal: controller.signal,
        onProgress: (partial) => patchMessage(conversationId, reply.id, partial),
      });
      patchMessage(conversationId, reply.id, result);
      abortRef.current = null;
      setStreaming(false);
    },
    [patchMessage, settings],
  );

  const send = useCallback(
    (text: string, model: string) => {
      const userMessage: ChatMessage = { id: newId(), role: "user", content: text };
      let conversation = active;
      if (!conversation) {
        const now = Date.now();
        conversation = {
          id: newId(),
          title: titleFrom(text),
          model,
          messages: [],
          createdAt: now,
          updatedAt: now,
        };
        const created = conversation;
        setConversations((all) => [created, ...all]);
        setActiveId(created.id);
      }
      void generate(conversation.id, [...conversation.messages, userMessage], model);
    },
    [active, generate],
  );

  const regenerate = useCallback(
    (model: string) => {
      if (!active) return;
      const lastUser = active.messages.findLastIndex((m) => m.role === "user");
      if (lastUser === -1) return;
      void generate(active.id, active.messages.slice(0, lastUser + 1), model);
    },
    [active, generate],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  const newChat = useCallback(() => setActiveId(null), []);

  const remove = useCallback(
    (id: string) => {
      if (id === activeId) setActiveId(null);
      setConversations((all) => all.filter((c) => c.id !== id));
    },
    [activeId],
  );

  return {
    conversations,
    active,
    activeId,
    streaming,
    send,
    regenerate,
    stop,
    newChat,
    select: setActiveId,
    remove,
  };
}
