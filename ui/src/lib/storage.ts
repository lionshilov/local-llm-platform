import type { Conversation, Settings } from "./types";

const CONVERSATIONS_KEY = "llp.conversations.v1";
const SETTINGS_KEY = "llp.settings.v1";

export const DEFAULT_SETTINGS: Settings = {
  systemPrompt: "",
  temperature: 0.7,
  maxTokens: 2048,
  thinking: false,
};

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

export function loadConversations(): Conversation[] {
  const conversations = read<Conversation[]>(CONVERSATIONS_KEY, []);
  // A reload mid-stream leaves messages marked as streaming; they were cut off.
  for (const conversation of conversations) {
    for (const message of conversation.messages) {
      if (message.status === "streaming") message.status = "stopped";
    }
  }
  return conversations;
}

export function saveConversations(conversations: Conversation[]): void {
  localStorage.setItem(CONVERSATIONS_KEY, JSON.stringify(conversations));
}

export function loadSettings(): Settings {
  return { ...DEFAULT_SETTINGS, ...read<Partial<Settings>>(SETTINGS_KEY, {}) };
}

export function saveSettings(settings: Settings): void {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
}

export function newId(): string {
  return crypto.randomUUID();
}
