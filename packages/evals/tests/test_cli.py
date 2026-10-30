from __future__ import annotations

from pathlib import Path

import pytest
from llm_evals import cli
from llm_evals.results import EvalReport
from llm_evals.suite import MathSuite, load_suite
from llm_evals.testing import Scripted, ScriptedServer, by_prompt
from typer.testing import CliRunner

CONFIG = """
defaults:
  concurrency: 4
  max_tokens: 32
backends:
  fake:
    label: Fake backend
    base_url: http://fake/v1
    model: fake-model
    extra_body: {chat_template_kwargs: {enable_thinking: false}}
  fake-think:
    base_url: http://fake/v1
    model: fake-model
    max_tokens: 256
    temperature: 0.6
    suites: [math]
  down:
    base_url: http://127.0.0.1:9/v1
    model: nothing
"""


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    path = tmp_path / "evals.yaml"
    path.write_text(CONFIG)
    return path


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def fake_backend(monkeypatch: pytest.MonkeyPatch) -> ScriptedServer:
    """Answers every math item correctly and everything else with an empty reply."""
    suite = load_suite("math")
    assert isinstance(suite, MathSuite)
    answers = {item.question[:40]: f"Answer: {item.answer:g}" for item in suite.items}
    server = ScriptedServer(by_prompt(answers, default=Scripted(content="")))
    monkeypatch.setattr(cli, "_http_client", server.client)
    monkeypatch.setattr(cli, "system_info", lambda: {"cpu": "Test CPU", "memory_gb": 16.0})
    return server


def _text(output: str) -> str:
    """Console output with Rich's line wrapping undone."""
    return " ".join(output.split())


def _run(runner: CliRunner, config: Path, out: Path, *args: str) -> Path:
    result = runner.invoke(
        cli.app, ["run", "-c", str(config), "--output-dir", str(out), "--limit", "2", *args]
    )
    assert result.exit_code == 0, result.output
    return max(out.glob("*.json"))


def test_list_shows_every_suite(runner: CliRunner) -> None:
    result = runner.invoke(cli.app, ["list"])
    assert result.exit_code == 0, result.output
    for name in ("math", "reasoning", "json/prompted", "json/constrained", "tools", "instructions"):
        assert name in result.output


def test_run_writes_json_and_markdown(
    runner: CliRunner, config_file: Path, tmp_path: Path, fake_backend: ScriptedServer
) -> None:
    out = tmp_path / "results"
    json_path = _run(
        runner, config_file, out, "-b", "fake", "-s", "math", "-s", "json", "--tag", "t"
    )

    assert json_path.name.endswith("-t.json")
    report = EvalReport.load(json_path)
    assert {s.task: (s.passed, s.n) for s in report.summaries} == {
        "math": (2, 2),
        "json/prompted": (0, 2),
        "json/constrained": (0, 2),
    }
    assert report.backends["fake"].server is None
    assert report.backends["fake"].max_tokens == 32
    assert set(report.suites) == {"math", "json"}
    assert len(fake_backend.requests) == 6
    assert all(body["max_tokens"] == 32 for body in fake_backend.requests)

    markdown = json_path.with_suffix(".md").read_text()
    assert "| math | 2 | 100% (34\u2013100) |" in markdown


def test_backend_default_suites_and_overrides(
    runner: CliRunner, config_file: Path, tmp_path: Path, fake_backend: ScriptedServer
) -> None:
    json_path = _run(runner, config_file, tmp_path, "-b", "fake-think", "--concurrency", "1")
    report = EvalReport.load(json_path)
    assert {s.task for s in report.summaries} == {"math"}
    assert report.backends["fake-think"].max_tokens == 256
    assert report.backends["fake-think"].temperature == 0.6
    assert {body["temperature"] for body in fake_backend.requests} == {0.6}
    assert fake_backend.peak_in_flight == 1


def test_unreachable_backend_fails_when_strict(
    runner: CliRunner, config_file: Path, tmp_path: Path, fake_backend: ScriptedServer
) -> None:
    args = ["run", "-c", str(config_file), "-b", "down", "--output-dir", str(tmp_path)]
    result = runner.invoke(cli.app, args)
    assert result.exit_code == 1
    assert "Skipping down" in _text(result.output)
    assert "Nothing was evaluated" in _text(result.output)

    args = ["run", "-c", str(config_file), "-b", "fake-think", "-b", "down", "--limit", "1"]
    result = runner.invoke(cli.app, [*args, "--output-dir", str(tmp_path), "--fail-on-error"])
    assert result.exit_code == 1
    assert "skipped backends: ['down']" in _text(result.output)


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["-b", "nope"], "unknown backend: nope"),
        (["-s", "poetry"], "unknown suite in --suite: poetry"),
    ],
)
def test_bad_selection_is_rejected(
    runner: CliRunner, config_file: Path, args: list[str], message: str
) -> None:
    result = runner.invoke(cli.app, ["run", "-c", str(config_file), *args])
    assert result.exit_code != 0
    assert message in _text(result.output)


def test_report_merges_and_rescore_is_idempotent(
    runner: CliRunner, config_file: Path, tmp_path: Path, fake_backend: ScriptedServer
) -> None:
    first = _run(runner, config_file, tmp_path / "a", "-b", "fake", "-s", "math")
    second = _run(runner, config_file, tmp_path / "b", "-b", "fake-think")

    merged = tmp_path / "README.md"
    result = runner.invoke(cli.app, ["report", str(first), str(second), "-o", str(merged)])
    assert result.exit_code == 0, result.output
    text = merged.read_text()
    assert "| math | 2 | 100% (34\u2013100) | 100% (34\u2013100) |" in text
    assert "### Paired comparison vs `fake`" in text

    args = ["report", str(first), str(second), "--format", "markdown", "--baseline", "fake-think"]
    flipped = runner.invoke(cli.app, args)
    assert "### Paired comparison vs `fake-think`" in flipped.output
    bad_baseline = runner.invoke(cli.app, [*args[:-1], "nope"])
    assert bad_baseline.exit_code != 0
    assert "unknown baseline 'nope'" in _text(bad_baseline.output)

    rendered = runner.invoke(cli.app, ["report", str(first), "--format", "markdown"])
    assert rendered.exit_code == 0
    assert rendered.output.startswith("**Hardware:**")

    duplicate = runner.invoke(cli.app, ["report", str(first), str(first)])
    assert duplicate.exit_code != 0
    assert "appear twice" in _text(duplicate.output)

    rescored = runner.invoke(cli.app, ["rescore", str(first)])
    assert rescored.exit_code == 0, rescored.output
    assert "0 verdict(s) changed" in _text(rescored.output)


def test_version(runner: CliRunner) -> None:
    result = runner.invoke(cli.app, ["--version"])
    assert result.exit_code == 0
    assert result.output.startswith("llm-evals ")
