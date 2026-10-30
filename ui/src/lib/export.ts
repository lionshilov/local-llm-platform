import type { Conversation } from "./types";

/** Render a conversation as Markdown, with the metrics of every reply. */
export function conversationToMarkdown(
  conversation: Conversation,
  labelFor: (id?: string) => string,
): string {
  const lines = [`# ${conversation.title}`, ""];
  lines.push(`_Exported from Local LLM on ${new Date().toISOString().slice(0, 10)}_`, "");
  for (const message of conversation.messages) {
    if (message.role === "user") {
      lines.push("## You", "", message.content, "");
      continue;
    }
    const stats = message.stats;
    const details = [
      labelFor(stats?.servedBy ?? message.model),
      stats?.ttftMs != null ? `TTFT ${Math.round(stats.ttftMs)} ms` : null,
      stats?.tokensPerSecond != null ? `${stats.tokensPerSecond.toFixed(1)} tok/s` : null,
      stats?.completionTokens != null ? `${stats.completionTokens} tokens` : null,
    ].filter(Boolean);
    lines.push(`## Assistant`, "", `_${details.join(" · ")}_`, "");
    if (message.reasoning) {
      lines.push(
        "<details><summary>Reasoning</summary>",
        "",
        message.reasoning,
        "",
        "</details>",
        "",
      );
    }
    lines.push(message.content || (message.error ? `> Error: ${message.error}` : ""), "");
  }
  return lines.join("\n");
}

export function downloadText(filename: string, text: string): void {
  const url = URL.createObjectURL(new Blob([text], { type: "text/markdown;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function slugify(text: string): string {
  return (
    text
      .toLowerCase()
      .replace(/[^\p{L}\p{N}]+/gu, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 60) || "chat"
  );
}
