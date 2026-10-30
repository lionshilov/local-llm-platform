import { describe, expect, it } from "vitest";
import { preprocessMath } from "./math";

describe("preprocessMath", () => {
  it("escapes prices so they are not parsed as math", () => {
    expect(preprocessMath("The bat costs $1.00 more and the total is $1.10.")).toBe(
      "The bat costs \\$1.00 more and the total is \\$1.10.",
    );
    expect(preprocessMath("Costs $5 and $10 respectively")).toBe(
      "Costs \\$5 and \\$10 respectively",
    );
  });

  it("keeps math that starts with a digit", () => {
    expect(preprocessMath("Complexity is $2^n$ here")).toBe("Complexity is $2^n$ here");
    expect(preprocessMath("Subtract $1.00$ from both sides")).toBe(
      "Subtract $1.00$ from both sides",
    );
    expect(preprocessMath("$$2B = 0.10$$")).toBe("$$2B = 0.10$$");
  });

  it("converts LaTeX bracket delimiters", () => {
    expect(preprocessMath("inline \\(x^2\\) and block \\[\\frac{a}{b}\\]")).toBe(
      "inline $x^2$ and block $$\\frac{a}{b}$$",
    );
  });

  it("never touches code", () => {
    const text = "Use `echo $1` or\n```bash\nprice=$5\n```\nthen pay $5";
    expect(preprocessMath(text)).toBe("Use `echo $1` or\n```bash\nprice=$5\n```\nthen pay \\$5");
  });

  it("treats price arithmetic as prices, including model-escaped dollars", () => {
    expect(preprocessMath("Difference: $1.05 - $0.05 = \\$1.00")).toBe(
      "Difference: \\$1.05 - \\$0.05 = \\$1.00",
    );
    expect(preprocessMath("$1.05 - $0.05 = $1.00")).toBe("\\$1.05 - \\$0.05 = \\$1.00");
  });

  it("keeps one equation per line in multi-line display math", () => {
    expect(preprocessMath("$$\nx + 1 = 2\nx = 1\n$$")).toBe(
      "$$\n\\begin{gathered}\nx + 1 = 2 \\\\\nx = 1\n\\end{gathered}\n$$",
    );
    expect(preprocessMath("$$\na \\\\\nb\n$$")).toBe("$$\na \\\\\nb\n$$");
  });

  it("does not escape numbers inside display math", () => {
    expect(preprocessMath("$$2x = 0.10$$ costs $5")).toBe("$$2x = 0.10$$ costs \\$5");
  });

  it("leaves variables and already escaped dollars alone", () => {
    expect(preprocessMath("Let $B$ be the ball, it costs \\$3")).toBe(
      "Let $B$ be the ball, it costs \\$3",
    );
  });
});
