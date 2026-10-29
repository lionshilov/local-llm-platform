import "highlight.js/styles/github-dark.css";
import "katex/dist/katex.min.css";
import { memo } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import { preprocessMath } from "../lib/math";
import { CopyButton } from "./CopyButton";

/** Collect the raw text of a hast subtree (code blocks are split into spans by highlighting). */
function hastText(node: unknown): string {
  if (!node || typeof node !== "object") return "";
  const { value, children } = node as { value?: unknown; children?: unknown[] };
  if (typeof value === "string") return value;
  return Array.isArray(children) ? children.map(hastText).join("") : "";
}

function languageOf(node: unknown): string {
  const code = (node as { children?: { properties?: { className?: unknown } }[] })?.children?.[0];
  const classes = code?.properties?.className;
  const match = Array.isArray(classes)
    ? classes.map(String).find((c) => c.startsWith("language-"))
    : undefined;
  return match ? match.slice("language-".length) : "text";
}

const components: Components = {
  pre({ node, children }) {
    return (
      <div className="not-prose my-4 overflow-hidden rounded-xl border border-white/10 bg-[#0d1117]">
        <div className="flex items-center justify-between border-b border-white/5 bg-white/[0.03] px-4 py-1.5 text-xs text-zinc-400">
          <span className="font-mono">{languageOf(node)}</span>
          <CopyButton text={hastText(node)} label="Copy code" />
        </div>
        <pre className="overflow-x-auto p-4 text-[13px] leading-relaxed">{children}</pre>
      </div>
    );
  },
  a({ children, href }) {
    return (
      <a href={href} target="_blank" rel="noreferrer">
        {children}
      </a>
    );
  },
  table({ children }) {
    return (
      <div className="overflow-x-auto">
        <table>{children}</table>
      </div>
    );
  },
};

const remarkPlugins = [remarkGfm, remarkMath];
const rehypePlugins = [rehypeKatex, rehypeHighlight];

const STYLES = {
  default:
    "prose prose-invert max-w-none prose-pre:p-0 prose-code:before:content-none prose-code:after:content-none prose-p:leading-7 prose-headings:font-semibold prose-a:text-violet-300",
  muted:
    "prose prose-sm prose-invert max-w-none text-zinc-400 prose-p:my-1.5 prose-p:text-zinc-400 prose-li:text-zinc-400 prose-strong:text-zinc-300 prose-headings:text-zinc-300 prose-code:before:content-none prose-code:after:content-none",
};

function Markdown({
  text,
  streaming = false,
  variant = "default",
}: {
  text: string;
  streaming?: boolean;
  variant?: keyof typeof STYLES;
}) {
  return (
    <div className={`${streaming ? "is-streaming " : ""}${STYLES[variant]}`}>
      <ReactMarkdown
        remarkPlugins={remarkPlugins}
        rehypePlugins={rehypePlugins}
        components={components}
      >
        {preprocessMath(text)}
      </ReactMarkdown>
    </div>
  );
}

export default memo(Markdown);
