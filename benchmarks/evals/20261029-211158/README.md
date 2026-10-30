**Hardware:** Apple M2 Pro · 16.0 GB · macOS-27.0.1  
**Date:** 2026-10-29 22:02 UTC · llm-evals 0.1.0  
**Suites:** math (32 items, `ddc70523da80`), reasoning (28 items, `05feca3ac12c`), json (24 items, `089d27cbb9ee`), tools (30 items, `59d574a95816`), instructions (32 items, `99e30a81a268`)

| Backend | Label | Model | Server | Request settings |
|---|---|---|---|---|
| `llamacpp` | llama.cpp · GGUF Q4_K_M · thinking off | `qwen3.5-4b` | llama.cpp b11960-8642541b2 | max_tokens 1024, temperature 0, `{"chat_template_kwargs": {"enable_thinking": false}}` |
| `llamacpp-think` | llama.cpp · GGUF Q4_K_M · thinking on | `qwen3.5-4b` | llama.cpp b11960-8642541b2 | max_tokens 7168, temperature 0, `{"chat_template_kwargs": {"enable_thinking": true}}` |
| `llamacpp-think-sampled` | llama.cpp · GGUF Q4_K_M · thinking on · model-card sampling | `qwen3.5-4b` | llama.cpp b11960-8642541b2 | max_tokens 7168, temperature 1, `{"chat_template_kwargs": {"enable_thinking": true}, "top_p": 0.95, "top_k": 20, "min_p": 0.0, "presence_penalty": 1.5}` |

### Accuracy

Pass rate with 95% Wilson interval. Request errors count as failures.

| Task | n | `llamacpp` | `llamacpp-think` | `llamacpp-think-sampled` |
|---|---:|---:|---:|---:|
| math | 32 | 97% (84–99) | 88% (72–95) | 94% (80–98) |
| reasoning | 28 | 100% (88–100) | 93% (77–98) | - |
| json/prompted | 24 | 92% (74–98) | - | - |
| json/constrained | 24 | 92% (74–98) | - | - |
| tools | 30 | 100% (89–100) | - | - |
| instructions | 32 | 94% (80–98) | - | - |
| **Macro average** (1 shared task) |  | **97%** | **88%** | **94%** |

### Cost per item

Means per item. Latency is end-to-end at the run's concurrency, on a server that may
be shared: indicative only (llm-bench measures speed properly).

| Task | Backend | Latency s | Prompt tok | Completion tok | Errors |
|---|---|---:|---:|---:|---:|
| math | `llamacpp` | 22.5 | 88 | 469 | 0/32 |
| math | `llamacpp-think` | 131.7 | 86 | 2,710 | 0/32 |
| math | `llamacpp-think-sampled` | 147.2 | 86 | 2,783 | 0/32 |
| reasoning | `llamacpp` | 21.6 | 97 | 424 | 0/28 |
| reasoning | `llamacpp-think` | 92.4 | 95 | 1,874 | 0/28 |
| json/prompted | `llamacpp` | 6.2 | 260 | 94 | 0/24 |
| json/constrained | `llamacpp` | 4.7 | 260 | 94 | 0/24 |
| tools | `llamacpp` | 2.9 | 1,496 | 52 | 0/30 |
| instructions | `llamacpp` | 5.7 | 54 | 101 | 0/32 |

### Paired comparison vs `llamacpp`

Same items, so only disagreements carry information: *wins* are items only this
backend passed, *losses* items only the baseline passed. p: two-sided exact McNemar.

| Task | Backend | Items | Δ | Wins | Losses | p |
|---|---|---:|---:|---:|---:|---:|
| math | `llamacpp-think` | 32 | -9 pp | 1 | 4 | 0.38 |
| math | `llamacpp-think-sampled` | 32 | -3 pp | 0 | 1 | 1 |
| reasoning | `llamacpp-think` | 28 | -7 pp | 0 | 2 | 0.5 |

### Sub-checks

`format`: answer given in the requested `Answer:` form. `decision`/`function`/
`arguments`: whether to call, which tool, what arguments. Instructions: per-type
pass counts (instruction-level accuracy).

| Task | Check | `llamacpp` | `llamacpp-think` | `llamacpp-think-sampled` |
|---|---|---:|---:|---:|
| math | format | 31/32 | 28/32 | 30/32 |
| reasoning | format | 28/28 | 27/28 | - |
| json/prompted | valid_json | 24/24 | - | - |
| json/prompted | schema_valid | 24/24 | - | - |
| json/prompted | values_correct | 21/23 | - | - |
| json/constrained | valid_json | 24/24 | - | - |
| json/constrained | schema_valid | 24/24 | - | - |
| json/constrained | values_correct | 21/23 | - | - |
| tools | decision | 30/30 | - | - |
| tools | function | 23/23 | - | - |
| tools | arguments | 23/23 | - | - |
| instructions | bullet_points | 3/4 | - | - |
| instructions | lowercase | 4/4 | - | - |
| instructions | max_words | 9/9 | - | - |
| instructions | no_commas | 6/6 | - | - |
| instructions | quoted | 3/3 | - | - |
| instructions | markdown_table | 2/3 | - | - |
| instructions | postscript | 3/3 | - | - |
| instructions | keyword_count | 4/4 | - | - |
| instructions | ends_with | 5/5 | - | - |
| instructions | paragraphs | 3/3 | - | - |
| instructions | forbidden_words | 3/3 | - | - |
| instructions | title | 3/3 | - | - |
| instructions | placeholders | 3/3 | - | - |
| instructions | uppercase | 3/3 | - | - |
| instructions | numbered_list | 3/3 | - | - |
| instructions | starts_with | 3/3 | - | - |
| instructions | sections | 3/3 | - | - |
| instructions | min_words | 3/3 | - | - |
| instructions | highlights | 3/3 | - | - |

### Failures

<details><summary><code>llamacpp</code> · math: 1 of 32 failed</summary>

| Item | Reason | Reply (excerpt) |
|---|---|---|
| `math-21` | expected 14, got 2 (from last_number) [hit max_tokens] | `To find the total cost for parking for 4 hours and 20 minutes, we need to break down the time into the first hour and the additional hours. ⏎ …  Remaining = 1.016 hours. Ceiling(1.016) = 2. Correct. ⏎ Applying to our problem:` |

</details>

<details><summary><code>llamacpp</code> · json/prompted: 2 of 24 failed</summary>

| Item | Reason | Reply (excerpt) |
|---|---|---|
| `json-02` | /total: expected 88.47, got 104.49 | `{"items":[{"name":"USB-C cable","quantity":3,"unit_price":9.99},{"name":"laptop stand","quantity":1,"unit_price":34.5},{"name":"HDMI adapter","quantity":2,"unit_price":12.0}],"total":104.49}` |
| `json-12` | /windows: expected 2 element(s), got 1 | `{"windows":[{"start":"10:00","end":"11:00"}]}` |

</details>

<details><summary><code>llamacpp</code> · json/constrained: 2 of 24 failed</summary>

| Item | Reason | Reply (excerpt) |
|---|---|---|
| `json-02` | /total: expected 88.47, got 104.49 | `{"items":[{"name":"USB-C cable","quantity":3,"unit_price":9.99},{"name":"laptop stand","quantity":1,"unit_price":34.5},{"name":"HDMI adapter","quantity":2,"unit_price":12.0}],"total":104.49}` |
| `json-12` | /windows: expected 2 element(s), got 1 | `{"windows":[{"start":"10:00","end":"11:00"}]}` |

</details>

<details><summary><code>llamacpp</code> · instructions: 2 of 32 failed</summary>

| Item | Reason | Reply (excerpt) |
|---|---|---|
| `if-16` | markdown_table: 3 data rows, expected 4 | `<<Trains vs Planes for 500 km>> ⏎ \| Factor \| Train \| Plane \| ⏎ \| :--- \| :--- \| :--- \| ⏎ \| Travel Time \| Approximately 5–6 hours \| Approximately 1 … more space, no security lines \| Faster but cramped, strict security procedures \|` |
| `if-30` | bullet_points: 12 bullet points, expected 6 | `SECTION 1 ⏎ Arguments for working from home include: ⏎ - Increased flexibility allows employees to better manage personal schedules and family c … ty risks associated with accessing company networks from unsecured home devices.` |

</details>

<details><summary><code>llamacpp-think</code> · math: 4 of 32 failed</summary>

| Item | Reason | Reply (excerpt) |
|---|---|---|
| `math-03` | no number in the reply [hit max_tokens] | *(no answer)*, reasoning ends `…ion of "Classes do not need to stay together". ⏎ *   Could it mean that we don` |
| `math-06` | no number in the reply [hit max_tokens] | *(no answer)*, reasoning ends `… because of the corners. ⏎ Corners add $4 \times (1 \times 1) = 4$. ⏎ $60 + 4 = 64$.` |
| `math-14` | no number in the reply [hit max_tokens] | *(no answer)*, reasoning ends `…*   Wait, I should check if the runner is running 10 km in 30 minutes? Yes, that` |
| `math-26` | no number in the reply [hit max_tokens] | *(no answer)*, reasoning ends `…d to check the Day 17 calculation again. ⏎ Start Day 17: 16m. ⏎ Climb 3m ->` |

</details>

<details><summary><code>llamacpp-think</code> · reasoning: 2 of 28 failed</summary>

| Item | Reason | Reply (excerpt) |
|---|---|---|
| `reasoning-07` | no answer letter in the reply [hit max_tokens] | *(no answer)*, reasoning ends `…, it displaces its full volume. ⏎ When it melts, it becomes water of volume $V` |
| `reasoning-20` | expected D, got B | `Here is the step-by-step breakdown: ⏎ 1.  **Identify the relationship:** Rita's mother has a brother. This brother is Rita's **uncle** (speci … ce** (or nephew). ⏎ Therefore, the brother's daughter is Rita's niece. ⏎ Answer: B` |

</details>

<details><summary><code>llamacpp-think-sampled</code> · math: 2 of 32 failed</summary>

| Item | Reason | Reply (excerpt) |
|---|---|---|
| `math-21` | no number in the reply [hit max_tokens] | *(no answer)*, reasoning ends `…ructure works like this: ⏎ You pay for the first hour ($4). ⏎ Then you pay for every` |
| `math-24` | no number in the reply [hit max_tokens] | *(no answer)*, reasoning ends `… ⏎ 4.  **Calculate Real Elapsed Time ($t_{real}$):** ⏎ *` |

</details>
