export interface ModelInfo {
  id: string;
  label: string;
  owned_by: string;
  upstream_model: string;
  available: boolean;
}

export interface MessageStats {
  ttftMs: number | null;
  tokensPerSecond: number | null;
  completionTokens: number | null;
  promptTokens: number | null;
  thinkingMs: number | null;
  durationMs: number;
  finishReason: string | null;
}

export type MessageStatus = "streaming" | "done" | "stopped" | "error";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  reasoning?: string;
  model?: string;
  status?: MessageStatus;
  stats?: MessageStats;
  error?: string;
}

export interface Conversation {
  id: string;
  title: string;
  model: string;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
}

export interface Settings {
  systemPrompt: string;
  temperature: number;
  maxTokens: number;
  thinking: boolean;
}
