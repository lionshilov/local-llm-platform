from __future__ import annotations

from datetime import UTC, datetime

import pytest
from llm_evals.config import Backend, RequestOptions
from llm_evals.results import EvalReport, ItemResult, SuiteInfo
from llm_evals.runner import rescore, run_tasks
from llm_evals.suite import MathSuite, Suite, load_suite, parse_suite
from llm_evals.tasks import tasks_for
from llm_evals.testing import Scripted, ScriptedServer, by_prompt

MATH = """
name: math
kind: math
description: tiny
items:
  - {id: m1, question: "What is 2 + 2?", answer: 4}
  - {id: m2, question: "What is 3 * 3?", answer: 9}
  - {id: m3, question: "What is 10 / 2?", answer: 5}
"""

TOOLS = """
name: tools
kind: tools
description: tiny
system: Today is Tuesday.
tools:
  - name: get_weather
    description: Weather in a city.
    parameters:
      type: object
      properties: {city: {type: string}}
      required: [city]
      additionalProperties: false
items:
  - id: t1
    prompt: What's the weather in Rome?
    calls: [{name: get_weather, arguments: {city: Rome}}]
  - id: t2
    prompt: What's the capital of Canada?
    calls: []
"""

JSON = """
name: json
kind: json
description: tiny
items:
  - id: j1
    task: Describe a cat named Tom.
    json_schema: {type: object, properties: {name: {type: string}}, required: [name]}
    expected: {/name: Tom}
    reference: {name: Tom}
"""

SCRIPT = by_prompt(
    {
        "2 + 2": "Step: 2 + 2 = 4.\nAnswer: 4",
        "3 * 3": Scripted(content="Answer: 6", finish_reason="length"),
        "10 / 2": Scripted(status=500),
        "weather in Rome": Scripted(tool_calls=[("get_weather", {"city": "Rome"})]),
        "capital of Canada": "Ottawa.",
        "cat named Tom": '{"name": "Tom"}',
    }
)


def _suites() -> list[Suite]:
    return [parse_suite(text) for text in (MATH, TOOLS, JSON)]


async def test_end_to_end(backend: Backend, options: RequestOptions) -> None:
    server = ScriptedServer(SCRIPT)
    tasks = [task for suite in _suites() for task in tasks_for(suite)]
    seen: list[ItemResult] = []

    async with server.client() as client:
        results = await run_tasks(
            client, "fake", backend, tasks, options, concurrency=2, on_result=seen.append
        )

    assert [(r.task, r.item_id, r.passed) for r in results] == [
        ("math", "m1", True),
        ("math", "m2", False),
        ("math", "m3", False),
        ("tools", "t1", True),
        ("tools", "t2", True),
        ("json/prompted", "j1", True),
        ("json/constrained", "j1", True),
    ]
    assert len(seen) == len(results)
    by_id = {(r.task, r.item_id): r for r in results}

    m2 = by_id["math", "m2"]
    assert m2.reason == "expected 9, got 6 (from answer_line) [hit max_tokens]"
    assert m2.extracted == 6

    m3 = by_id["math", "m3"]
    assert m3.reply is None
    assert m3.error is not None
    assert m3.error.startswith("HTTP 500")
    assert m3.reason == m3.error

    t1 = by_id["tools", "t1"]
    assert t1.reply is not None
    assert t1.reply.tool_calls[0].name == "get_weather"
    assert t1.checks == {"decision": True, "function": True, "arguments": True}
    assert t1.prompt == "What's the weather in Rome?"
    assert all(r.latency_s >= 0 for r in results)

    bodies = {body["messages"][-1]["content"][:20]: body for body in server.requests}
    tool_body = bodies["What's the weather i"]
    assert tool_body["messages"][0] == {"role": "system", "content": "Today is Tuesday."}
    assert tool_body["tools"][0]["function"]["name"] == "get_weather"
    assert all(body["temperature"] == 0 for body in server.requests)
    assert all(body["max_tokens"] == 64 for body in server.requests)
    json_bodies = [b for b in server.requests if "cat named Tom" in b["messages"][-1]["content"]]
    assert [("response_format" in body) for body in json_bodies] == [False, True]
    assert json_bodies[1]["response_format"]["json_schema"]["schema"]["required"] == ["name"]


async def test_summaries(backend: Backend, options: RequestOptions) -> None:
    server = ScriptedServer(SCRIPT)
    async with server.client() as client:
        results = await run_tasks(
            client, "fake", backend, tasks_for(_suites()[0]), options, concurrency=1
        )
    report = EvalReport(created_at=datetime.now(UTC), tool_version="t", system={})
    report.add(results)

    summary = report.summary("fake", "math")
    assert summary is not None
    assert (summary.n, summary.passed, summary.errors) == (3, 1, 1)
    assert summary.accuracy == pytest.approx(1 / 3)
    assert summary.ci_low < 1 / 3 < summary.ci_high
    assert summary.checks["format"].model_dump() == {"passed": 2, "total": 2}
    assert summary.completion_tokens_mean is not None


async def test_concurrency_is_bounded_and_limit_applies(
    backend: Backend, options: RequestOptions
) -> None:
    server = ScriptedServer(lambda _: Scripted(content="Answer: 1", delay_s=0.01))
    suite = load_suite("math")
    async with server.client() as client:
        results = await run_tasks(
            client, "fake", backend, tasks_for(suite), options, concurrency=3, limit=9
        )
    assert [r.item_id for r in results] == [item.id for item in suite.items[:9]]
    assert server.peak_in_flight == 3


async def _math_report(backend: Backend, options: RequestOptions) -> EvalReport:
    suite = load_suite("math")
    assert isinstance(suite, MathSuite)
    answers = {item.question[:40]: f"Answer: {item.answer:g}" for item in suite.items}
    server = ScriptedServer(by_prompt(answers))
    async with server.client() as client:
        results = await run_tasks(
            client, "fake", backend, tasks_for(suite), options, concurrency=4, limit=3
        )
    report = EvalReport(
        created_at=datetime.now(UTC),
        tool_version="t",
        system={},
        suites={
            "math": SuiteInfo(
                kind="math", items=len(suite.items), fingerprint=suite.fingerprint, tasks=["math"]
            )
        },
    )
    report.add(results)
    return report


async def test_rescore_reapplies_current_scorers(backend: Backend, options: RequestOptions) -> None:
    report = await _math_report(backend, options)
    assert all(item.passed for item in report.items)

    tampered = report.model_copy(
        update={"items": [i.model_copy(update={"passed": False}) for i in report.items]}
    )
    restored = rescore(tampered)
    assert all(item.passed for item in restored.items)
    assert restored.summaries == report.summaries


async def test_rescore_refuses_a_changed_suite(backend: Backend, options: RequestOptions) -> None:
    report = await _math_report(backend, options)
    report.suites["math"].fingerprint = "000000000000"
    with pytest.raises(ValueError, match="changed since this run"):
        rescore(report)
