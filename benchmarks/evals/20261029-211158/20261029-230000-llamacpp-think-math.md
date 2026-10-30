**Hardware:** Apple M2 Pro · 16.0 GB · macOS-27.0.1  
**Date:** 2026-10-29 23:00 UTC · llm-evals 0.1.0  
**Suites:** math (32 items, `ddc70523da80`)

| Backend | Label | Model | Server | Request settings |
|---|---|---|---|---|
| `llamacpp-think` | llama.cpp · GGUF Q4_K_M · thinking on | `qwen3.5-4b` | llama.cpp b11960-8642541b2 | max_tokens 7168, temperature 0, `{"chat_template_kwargs": {"enable_thinking": true}}` |

### Accuracy

Pass rate with 95% Wilson interval. Request errors count as failures.

| Task | n | `llamacpp-think` |
|---|---:|---:|
| math | 32 | 88% (72–95) |
| **Macro average** (1 shared task) |  | **88%** |

### Cost per item

Means per item. Latency is end-to-end at the run's concurrency, on a server that may
be shared: indicative only (llm-bench measures speed properly).

| Task | Backend | Latency s | Prompt tok | Completion tok | Errors |
|---|---|---:|---:|---:|---:|
| math | `llamacpp-think` | 131.7 | 86 | 2,710 | 0/32 |

### Sub-checks

`format`: answer given in the requested `Answer:` form. `decision`/`function`/
`arguments`: whether to call, which tool, what arguments. Instructions: per-type
pass counts (instruction-level accuracy).

| Task | Check | `llamacpp-think` |
|---|---|---:|
| math | format | 28/32 |

### Failures

<details><summary><code>llamacpp-think</code> · math: 4 of 32 failed</summary>

| Item | Reason | Reply (excerpt) |
|---|---|---|
| `math-03` | no number in the reply [hit max_tokens] | *(no answer)*, reasoning ends `…ion of "Classes do not need to stay together". ⏎ *   Could it mean that we don` |
| `math-06` | no number in the reply [hit max_tokens] | *(no answer)*, reasoning ends `… because of the corners. ⏎ Corners add $4 \times (1 \times 1) = 4$. ⏎ $60 + 4 = 64$.` |
| `math-14` | no number in the reply [hit max_tokens] | *(no answer)*, reasoning ends `…*   Wait, I should check if the runner is running 10 km in 30 minutes? Yes, that` |
| `math-26` | no number in the reply [hit max_tokens] | *(no answer)*, reasoning ends `…d to check the Day 17 calculation again. ⏎ Start Day 17: 16m. ⏎ Climb 3m ->` |

</details>
