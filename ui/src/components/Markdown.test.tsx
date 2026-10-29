import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import Markdown from "./Markdown";

const render = (text: string) => renderToStaticMarkup(<Markdown text={text} />);

describe("Markdown", () => {
  it("renders LaTeX with KaTeX", () => {
    const html = render("Euler: $e^{i\\pi} + 1 = 0$");
    expect(html).toContain('class="katex"');
  });

  it("renders multi-line display math line by line without errors", () => {
    const html = render("$$\nx + (x + 1.00) = 1.10\n2x = 0.10\n$$");
    expect(html).toContain("katex-display");
    expect(html).not.toContain("katex-error");
  });

  it("keeps prices as plain text", () => {
    const html = render("The bat costs $1.00 more and the total is $1.10.");
    expect(html).not.toContain("katex");
    expect(html).toContain("$1.00 more and the total is $1.10.");
  });

  it("highlights code blocks and adds a copy button with the raw code", () => {
    const html = render("```python\nprint('hi')\n```");
    expect(html).toContain("hljs");
    expect(html).toContain(">python<");
    expect(html).toContain('aria-label="Copy code"');
  });

  it("renders GitHub-flavored tables", () => {
    const html = render("| a | b |\n|---|---|\n| 1 | 2 |");
    expect(html).toContain("<table>");
  });
});
