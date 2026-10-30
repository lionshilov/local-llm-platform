# llm-evals

The **quality** half of "quality vs speed vs memory". [`llm-bench`](../llm-bench) tells you
how fast an engine serves a model; `llm-evals` tells you whether what comes back is any
good, and whether that changes when you switch engines, quantizations (Q4_K_M vs Q8_0) or
turn thinking on.

It talks to any OpenAI-compatible endpoint, runs small, original task suites, scores every
reply in code, and reports pass rates with confidence intervals honest enough for the
sample sizes involved.

## Suites

| Suite | Task(s) | Items | Measures | Scoring |
|---|---|---:|---|---|
| `math` | `math` | 32 | Multi-step grade-school word problems | Final number (`Answer:` line, else `\boxed{}`, else last number), handles `$`, `1,234.50`, `3/4`, `2 1/2` |
| `reasoning` | `reasoning` | 28 | Multiple-choice deduction, ordering, spatial and common-sense questions | Answer letter from `Answer: X`, "option X" or a bare letter; never guessed from prose |
| `json` | `json/prompted`, `json/constrained` | 24 | Structured output against a JSON Schema: extraction, transformation, light computation, generation | Parses as JSON **and** validates against the schema **and** key facts match (JSON Pointer → value) |
| `tools` | `tools` | 30 | Single-turn function calling over 10 tools; 3 items need parallel calls, 7 need **no** call | Exact set of calls (any order); arguments schema-valid and equal after normalization |
| `instructions` | `instructions` | 32 | Verifiable instructions, IFEval-style: bullet/list counts, case, keywords, word limits, exact start/end, tables, sections, … (19 types) | Every instruction checked in code; pass only if all hold |

`llm-evals list` prints the same overview from the installed package. Suites live in
[`src/llm_evals/suites/`](src/llm_evals/suites) as YAML.

## Usage

```bash
llm-evals list                                    # suites, tasks, item counts
llm-evals run                                     # every backend in configs/evals.yaml
llm-evals run -b llamacpp -s math -s tools        # some backends, some suites
llm-evals run --limit 3                           # smoke test: first 3 items per suite
llm-evals report benchmarks/evals/<ts>/*.json     # merge runs into one comparison
llm-evals report <files> -o README.md --failures 5 --baseline llamacpp
llm-evals rescore benchmarks/evals/<ts>/*.json    # re-apply scorers, no model calls
```

`run` writes `<timestamp>[-tag].json` (every item: prompt, raw reply including reasoning and
tool calls, extracted answer, verdict, reason, latency, tokens) and a Markdown report next
to it. Backends are configured like llm-bench engines, in
[`configs/evals.yaml`](../../configs/evals.yaml):

```yaml
defaults:
  concurrency: 2        # requests in flight per backend
  max_tokens: 1024
  temperature: 0
  timeout_s: 300        # per request; a timeout is a failed item
  retries: 2            # connection errors only

backends:
  llamacpp:
    label: llama.cpp · GGUF Q4_K_M · thinking off
    base_url: http://127.0.0.1:8080/v1
    model: qwen3.5-4b
    extra_body: {chat_template_kwargs: {enable_thinking: false}}
  llamacpp-think:                     # same weights, reasoning on
    base_url: http://127.0.0.1:8080/v1
    model: qwen3.5-4b
    max_tokens: 7168                  # per-backend overrides: max_tokens,
    timeout_s: 900                    # temperature, timeout_s, concurrency
    suites: [math, reasoning]         # default suites for this backend
    extra_body: {chat_template_kwargs: {enable_thinking: true}}
```

## Design

```
src/llm_evals/
├── suites/*.yaml   # data: questions, answer keys, schemas, tools, instructions
├── suite.py        # typed models; malformed items fail at load time
├── tasks.py        # suite → prompt + scorer (the json suite runs twice)
├── scoring/        # pure, total functions: reply → Score (numeric, choice, structured,
│                   #   tools, instructions, value matching, JSON Schema facade)
├── client.py       # raw OpenAI HTTP: per-request deadline, retries on connection errors only
├── runner.py       # bounded concurrency, one record per item, rescore
├── results.py      # versioned JSON schema, summaries, merge that refuses unsafe mixes
├── stats.py        # Wilson interval, exact McNemar test
├── report.py       # Markdown and Rich rendering
└── testing.py      # scripted in-process OpenAI server for tests (httpx.MockTransport)
```

Generation and scoring are separate steps joined by the stored reply, so every number in a
report can be traced back to the exact text the model produced.

## Methodology

**Programmatic scoring, not LLM-as-judge.** Every suite here has a checkable answer, so a
judge would only add cost, latency, its own biases (position, verbosity, self-preference)
and run-to-run noise. When the evaluated model is a 4B model on a laptop, there is usually
no stronger local judge either. A judge earns its place for open-ended quality (summaries,
helpfulness), and only after being calibrated against human labels; that is listed under
next steps.

**Greedy decoding, plus the vendor's sampler where it matters.** `temperature: 0` asks for
the model's single most likely answer, which removes sampling noise and the engines'
different sampler defaults from the comparison. It is not bit-exact determinism: llama.cpp
batches concurrent requests together, and batch composition changes floating-point
reduction order, so an item that is a near-tie can flip between runs. Treat single-item
differences as noise; that is what the statistics are for. Thinking mode is the exception
worth testing both ways: the
[Qwen3.5 model card](https://huggingface.co/Qwen/Qwen3.5-4B#best-practices) recommends
sampling for it (`temperature 1.0, top_p 0.95, top_k 20, presence_penalty 1.5`, the
penalty being there to reduce endless repetitions), so `configs/evals.yaml` has a greedy
and a sampled thinking backend. A sampled run is one draw, not a measurement of the mean.

**Small n needs intervals.** With 30 items, one item is 3.3 points and the 95% interval
around 80% (24/30) runs from 63% to 90%. Every accuracy is reported with a **Wilson score
interval**, which stays inside [0, 1] and keeps near-nominal coverage at small n and at
0% or 100%, where the textbook normal interval collapses to zero width. Two backends run on
the *same* items are compared with **McNemar's exact test**, which uses only the items where
they disagree. Paired testing is much more sensitive than checking whether two independent
intervals overlap, and is the right test for "did quantization change anything?".

**Original items.** Every item was written for this repo. Copying GSM8K, IFEval or MMLU
would raise licensing questions and, worse, test memorization: those sets are in most
models' training data. Some items follow classic puzzle archetypes (knights and knaves, a
snail in a well) with new wording and numbers; those are marked in the suite files. Being
public, these items will eventually be scraped too, so treat the suites as a regression
and comparison tool, not a leaderboard.

**Suites are tested like code.** Each item ships a reference answer (or one is derived
from the answer key), and the test suite checks that every reference passes its own scorer.
This caught a real authoring bug while writing the suites (a reference answer whose
highlighted phrase wrapped across a line break, which the checker rightly refuses to count)
before any model could be blamed for it. Item ids are unique, multiple-choice answer
letters are balanced so always guessing one letter scores about 25%, and each suite's
content hash is stored in every result file; merging results from different suite versions
is refused.

**Constrained vs. unconstrained JSON.** The `json` suite runs twice with identical prompts
(schema in the prompt). `json/prompted` relies on the model alone; `json/constrained` also
sends the schema as `response_format: {"type": "json_schema", ...}`, which llama.cpp
compiles into a grammar that masks invalid tokens during decoding. The difference is the
value of constrained decoding. Because constrained decoding makes schema validity almost
free, items also pin key values (`/total: 88.47`), so the suite measures whether the
*content* survives the constraint, not just the syntax. A reply that is a single fenced
code block is unwrapped (every client does this); JSON inside prose fails.

**Tool calls.** A call passes when the function names match exactly, the arguments validate
against the tool's JSON Schema (which rejects hallucinated parameters and bad enums), and
every argument the request determines matches after normalization: case and whitespace for
strings, value for numbers (`600 == 600.0`, but never `true == 1`), order for lists.
Arguments the request leaves open (an optional `unit`) are not judged. Sub-checks separate
*deciding* to call, *choosing* the tool and *filling* the arguments.

**Instructions.** Each instruction type renders its own prompt sentence from the same object
that verifies it, so the text can never ask for something the checker does not test.
Checks are strict, like IFEval's strict mode, with one exception: curly and straight
quotes are treated as equal in exact-phrase checks. The report gives prompt-level accuracy
(all instructions followed) and per-type counts (instruction-level accuracy).

**Failures are results.** A timeout, an HTTP error or a reply cut off by `max_tokens`
counts as a failed item, never a skipped one; errors are also counted separately, and
truncation is flagged in the failure reason. Only connection-level errors are retried.

**Scoring is decoupled from generation.** Raw replies are stored, so `llm-evals rescore`
re-applies fixed or improved scorers to old runs in seconds, without touching a model.

**Latency here is indicative only.** It is measured end to end under the run's concurrency,
possibly on a shared server. Use llm-bench for speed claims.

## Results on Qwen3.5-4B Q4_K_M

llama.cpp b11960 on an Apple M2 Pro (16 GB): GGUF Q4_K_M, 4 slots with 8k context each,
2 requests in flight, October 2026. The full report, with paired tests, sub-checks and every
failed item next to the model's reply, is in
[`benchmarks/evals/20261029-211158`](../../benchmarks/evals/20261029-211158/README.md).

| Task | n | Thinking off | Thinking on, greedy | Thinking on, model-card sampling |
|---|---:|---:|---:|---:|
| math | 32 | **97%** (84–99) | 88% (72–95) | 94% (80–98) |
| reasoning | 28 | **100%** (88–100) | 93% (77–98) | - |
| json/prompted | 24 | 92% (74–98) | - | - |
| json/constrained | 24 | 92% (74–98) | - | - |
| tools | 30 | 100% (89–100) | - | - |
| instructions | 32 | 94% (80–98) | - | - |
| *math: output tokens per item* | | *469* | *2,710* | *2,783* |
| *math: latency per item* | | *23 s* | *132 s* | *147 s* |

95% Wilson intervals in brackets. Latency was measured with two requests in flight on a
shared laptop, so treat it as indicative only.

1. **Thinking bought nothing measurable here and cost about 6× the tokens and time.**
   Thinking off is already near the ceiling on these problems. Seven of the eight
   thinking-mode failures are the same failure: the 7,168-token budget ran out
   mid-reasoning, sometimes after the right answer had appeared (`math-06` computes 64, then
   keeps re-checking). The eighth (`reasoning-20`) reasons its way to "niece" for a cousin,
   which thinking off gets right. How the budget runs out depends on decoding: greedy
   truncations are mostly loops (`math-26` and `math-14` repeat 73% and 58% of their
   reasoning lines), while with the model card's sampler `presence_penalty` breaks the
   loops and the two remaining truncations are long but not repetitive. No difference is
   significant (paired McNemar p = 0.38, 1.0 and 0.5), so the finding is "no gain at 6×
   the cost", not "thinking hurts". The budget is a confound: Qwen recommends 32k output
   tokens, and llama.cpp's 8k context per slot caps it here.
2. **Constrained decoding changed nothing because the model never broke the schema.**
   Prompted JSON was already 24/24 valid and schema-valid; the grammar made that guaranteed,
   not better, at no measurable latency cost. The same two items fail in both modes, and
   both are content errors no grammar can prevent: an order total of 104.49 instead of
   88.47, and a missed second overlap window. This is why the suite checks values, not only
   validity.
3. **Tool calling was perfect at 4-bit**: 30/30, including all 7 items where the right move
   is *not* to call (general knowledge, small talk, a capability the toolbox lacks, a
   missing required argument) and 3 parallel calls. Still, the interval's lower bound is
   89%: 30 items cannot show the model is better than that.
4. **Instruction misses are counting errors**: 3 table rows instead of 4, and 6 bullets
   *per section* (12) instead of 6 in total. Instruction-level accuracy is 70/72 (97%),
   prompt-level 30/32 (94%).
5. **Greedy is not deterministic under batching.** Across three thinking-off runs of the
   same 169 prompts, 160 replies were byte-identical. The 9 that differed were all long
   free-text answers (JSON and tool calls never changed), and one verdict flipped:
   `math-21` passed twice, then ran out of tokens in the final run. One item is 3 points,
   which is why reports pair items and test, rather than compare headline numbers.

**Items fixed along the way.** Reviewing failures found two item problems. Both were fixed
and every affected run was redone (results from different suite versions refuse to merge):

- `math-03`: the model assumed classes must travel as whole units. The first fix
  ("students from different classes may share a bus") still left that open; the thinking
  trace debated it explicitly ("why specify the class sizes? … If the answer is 4, the
  problem is trivial"). The final wording says classes do not need to stay together.
  Thinking off and sampled thinking now solve it; greedy thinking still deliberates until
  the budget runs out.
- `json-10`: the answer key wanted bare task names, but copying the due date along with the
  name is equally correct and is now accepted.

## Limitations and next steps

- **One configuration measured so far.** The quantization comparison (Q4_K_M vs Q8_0) and
  the cross-engine one are configured in `configs/evals.yaml` but not run yet; they need a
  second server, and this run had to share one.
- **Small suites.** 24–32 items per suite resolve differences of roughly 15–20 points, not
  2–3. Detecting a subtle quantization loss needs hundreds of items per task or many paired
  runs; the tooling scales, the hand-written items don't.
- **Thinking budget capped at 7k tokens** by llama.cpp's per-slot context (32k / 4 slots).
  A fair verdict on thinking needs a server started with a larger context per slot.
- **English only, short contexts, single turn.** No long-context retrieval, multi-turn tool
  use or multilingual items yet.
- **LLM-as-judge with calibration** for open-ended quality: label a sample by hand, measure
  judge agreement (Cohen's κ), and only then trust it.
- **lm-evaluation-harness integration** for standard benchmarks (GSM8K, IFEval, MMLU-Pro)
  through the same backends, to anchor these numbers against published ones.
- **Coding with unit tests and RAG faithfulness** suites, as planned in the roadmap.
- **CI regression gate**: run a fixed subset against the CI model and fail when a paired
  test shows a significant drop against a stored baseline.
- **Repeat runs as a feature**: run each backend k times and report per-item flakiness
  (done by hand above, from three thinking-off runs).
