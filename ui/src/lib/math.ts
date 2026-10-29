/**
 * Prepare model output for remark-math.
 *
 * Models write math as `\( \)`, `\[ \]`, `$ $` or `$$ $$`, and also write prices like
 * "$1.10". remark-math only knows dollar delimiters and happily turns
 * "costs $1.00 and the total is $1.10" into one formula, so we:
 *   1. leave fenced and inline code untouched,
 *   2. convert `\[...\]` / `\(...\)` to dollar delimiters,
 *   3. keep line breaks inside multi-line display math (models put one equation per line),
 *   4. escape a `$` before a digit unless it opens a span that looks like math. A closing
 *      `$` must not be escaped and must not be followed by a digit (Pandoc's rule), so
 *      "$1.05 - $0.05" is two prices, not a formula.
 */

const CODE = /(```[\s\S]*?(?:```|$)|`[^`\n]*`)/g;
const CURRENCY_DOLLAR = /(?<![\\$])\$(?=\d)/g;
const MATH_HINT = /[\\^_{}=]/;
const DISPLAY_MATH = /\$\$([\s\S]+?)\$\$/g;
const DISPLAY_MATH_SPLIT = /(\$\$[\s\S]+?\$\$)/g;

function closingDollar(line: string, from: number): number {
  for (let i = line.indexOf("$", from); i !== -1; i = line.indexOf("$", i + 1)) {
    const escaped = line[i - 1] === "\\";
    const beforeDigit = /\d/.test(line[i + 1] ?? "");
    if (!escaped && !beforeDigit) return i;
  }
  return -1;
}

function escapeCurrency(line: string): string {
  let out = "";
  let last = 0;
  for (const match of line.matchAll(CURRENCY_DOLLAR)) {
    const start = match.index;
    const close = closingDollar(line, start + 1);
    const looksLikeMath = close !== -1 && MATH_HINT.test(line.slice(start + 1, close));
    if (!looksLikeMath) {
      out += `${line.slice(last, start)}\\$`;
      last = start + 1;
    }
  }
  return out + line.slice(last);
}

function keepDisplayLineBreaks(body: string): string {
  const lines = body
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
  if (lines.length < 2 || /\\\\|\\begin/.test(body)) return body;
  return `\n\\begin{gathered}\n${lines.join(" \\\\\n")}\n\\end{gathered}\n`;
}

function transformProse(text: string): string {
  const delimited = text
    .replace(/\\\[([\s\S]*?)\\\]/g, (_, body: string) => `$$${body}$$`)
    .replace(/\\\(([\s\S]*?)\\\)/g, (_, body: string) => `$${body}$`)
    .replace(DISPLAY_MATH, (_, body: string) => `$$${keepDisplayLineBreaks(body)}$$`);
  // Prices only occur in ordinary prose; display math blocks are left as they are.
  return delimited
    .split(DISPLAY_MATH_SPLIT)
    .map((part, index) =>
      index % 2 === 1 ? part : part.split("\n").map(escapeCurrency).join("\n"),
    )
    .join("");
}


export function preprocessMath(markdown: string): string {
  return markdown
    .split(CODE)
    .map((part, index) => (index % 2 === 1 ? part : transformProse(part)))
    .join("");
}
