**Hardware:** Apple M2 Pro · 16.0 GB · macOS-27.0.1  
**Date:** 2026-10-29 23:35 UTC · llm-evals 0.1.0  
**Suites:** math (32 items, `ddc70523da80`)

| Backend | Label | Model | Server | Request settings |
|---|---|---|---|---|
| `llamacpp-think-sampled` | llama.cpp · GGUF Q4_K_M · thinking on · model-card sampling | `qwen3.5-4b` | llama.cpp b11960-8642541b2 | max_tokens 7168, temperature 1, `{"chat_template_kwargs": {"enable_thinking": true}, "top_p": 0.95, "top_k": 20, "min_p": 0.0, "presence_penalty": 1.5}` |

### Accuracy

Pass rate with 95% Wilson interval. Request errors count as failures.

| Task | n | `llamacpp-think-sampled` |
|---|---:|---:|
| math | 32 | 94% (80–98) |
| **Macro average** (1 shared task) |  | **94%** |

### Cost per item

Means per item. Latency is end-to-end at the run's concurrency, on a server that may
be shared: indicative only (llm-bench measures speed properly).

| Task | Backend | Latency s | Prompt tok | Completion tok | Errors |
|---|---|---:|---:|---:|---:|
| math | `llamacpp-think-sampled` | 147.2 | 86 | 2,783 | 0/32 |

### Sub-checks

`format`: answer given in the requested `Answer:` form. `decision`/`function`/
`arguments`: whether to call, which tool, what arguments. Instructions: per-type
pass counts (instruction-level accuracy).

| Task | Check | `llamacpp-think-sampled` |
|---|---|---:|
| math | format | 30/32 |

### Failures

<details><summary><code>llamacpp-think-sampled</code> · math: 2 of 32 failed</summary>

| Item | Reason | Reply (excerpt) |
|---|---|---|
| `math-21` | no number in the reply [hit max_tokens] | *(no answer)*, reasoning ends `…ructure works like this: ⏎ You pay for the first hour ($4). ⏎ Then you pay for every` |
| `math-24` | no number in the reply [hit max_tokens] | *(no answer)*, reasoning ends `… ⏎ 4.  **Calculate Real Elapsed Time ($t_{real}$):** ⏎ *` |

</details>
