import { type ComponentProps, lazy, Suspense } from "react";

// Markdown, KaTeX and highlight.js are most of the bundle; load them with the first reply.
const Markdown = lazy(() => import("./Markdown"));

export function LazyMarkdown(props: ComponentProps<typeof Markdown>) {
  return (
    <Suspense fallback={<div className="leading-7 whitespace-pre-wrap">{props.text}</div>}>
      <Markdown {...props} />
    </Suspense>
  );
}
