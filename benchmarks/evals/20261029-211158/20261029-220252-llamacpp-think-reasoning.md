**Hardware:** Apple M2 Pro · 16.0 GB · macOS-27.0.1  
**Date:** 2026-10-29 22:02 UTC · llm-evals 0.1.0  
**Suites:** reasoning (28 items, `05feca3ac12c`)

| Backend | Label | Model | Server | Request settings |
|---|---|---|---|---|
| `llamacpp-think` | llama.cpp · GGUF Q4_K_M · thinking on | `qwen3.5-4b` | llama.cpp b11960-8642541b2 | max_tokens 7168, temperature 0, `{"chat_template_kwargs": {"enable_thinking": true}}` |

### Accuracy

Pass rate with 95% Wilson interval. Request errors count as failures.

| Task | n | `llamacpp-think` |
|---|---:|---:|
| reasoning | 28 | 93% (77–98) |
| **Macro average** (1 shared task) |  | **93%** |

### Cost per item

Means per item. Latency is end-to-end at the run's concurrency, on a server that may
be shared: indicative only (llm-bench measures speed properly).

| Task | Backend | Latency s | Prompt tok | Completion tok | Errors |
|---|---|---:|---:|---:|---:|
| reasoning | `llamacpp-think` | 92.4 | 95 | 1,874 | 0/28 |

### Sub-checks

`format`: answer given in the requested `Answer:` form. `decision`/`function`/
`arguments`: whether to call, which tool, what arguments. Instructions: per-type
pass counts (instruction-level accuracy).

| Task | Check | `llamacpp-think` |
|---|---|---:|
| reasoning | format | 27/28 |

### Failures

<details><summary><code>llamacpp-think</code> · reasoning: 2 of 28 failed</summary>

| Item | Reason | Reply (excerpt) |
|---|---|---|
| `reasoning-07` | no answer letter in the reply [hit max_tokens] | *(no answer)*, reasoning ends `…, it displaces its full volume. ⏎ When it melts, it becomes water of volume $V` |
| `reasoning-20` | expected D, got B | `Here is the step-by-step breakdown: ⏎ 1.  **Identify the relationship:** Rita's mother has a brother. This brother is Rita's **uncle** (speci … ce** (or nephew). ⏎ Therefore, the brother's daughter is Rita's niece. ⏎ Answer: B` |

</details>
