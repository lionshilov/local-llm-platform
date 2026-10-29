from __future__ import annotations

import json
from pathlib import Path

import pytest
from llm_bench import cli
from llm_bench.results import BenchReport
from llm_bench.testing import FakeServer
from typer.testing import CliRunner

CONFIG = """
engines:
  fake:
    base_url: http://fake/v1
    model: fake-model
    label: Fake engine
  down:
    base_url: http://127.0.0.1:9/v1
    model: nothing
scenarios:
  decode:
    prompt_words: 20
    max_tokens: 8
    concurrency: [1, 2]
    requests_per_level: 3
"""


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    path = tmp_path / "bench.yaml"
    path.write_text(CONFIG)
    return path


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def fake_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> FakeServer:
    server = FakeServer(tokens=6)
    monkeypatch.setattr(cli, "_http_client", server.client)
    return server


def test_run_writes_json_and_markdown(
    runner: CliRunner, config_file: Path, tmp_path: Path, fake_backend: FakeServer
) -> None:
    out = tmp_path / "results"
    result = runner.invoke(
        cli.app,
        ["run", "-c", str(config_file), "-e", "fake", "--output-dir", str(out), "--tag", "t"],
    )
    assert result.exit_code == 0, result.output

    [json_path] = out.glob("*-t.json")
    report = BenchReport.load(json_path)
    assert [(r.scenario, r.concurrency) for r in report.runs] == [("decode", 1), ("decode", 2)]
    assert all(r.summary.errors == 0 for r in report.runs)
    assert report.runs[0].requests[0].output_tokens == 6
    assert "chunk_gaps_s" not in json.loads(json_path.read_text())["runs"][0]["requests"][0]
    # 1 warm-up + 3 requests x 2 concurrency levels
    assert len(fake_backend.requests) == 7

    markdown = json_path.with_suffix(".md").read_text()
    assert "| Fake engine | decode | 2 |" in markdown


def test_unreachable_engine_fails_when_strict(
    runner: CliRunner, config_file: Path, tmp_path: Path, fake_backend: FakeServer
) -> None:
    args = ["run", "-c", str(config_file), "--output-dir", str(tmp_path), "--fail-on-error"]
    result = runner.invoke(cli.app, args)
    assert result.exit_code == 1
    assert "Skipping down" in result.output


def test_unknown_engine_is_rejected(runner: CliRunner, config_file: Path) -> None:
    result = runner.invoke(cli.app, ["run", "-c", str(config_file), "-e", "nope"])
    assert result.exit_code != 0
    assert "unknown engine" in result.output


def test_probe_and_report(
    runner: CliRunner, config_file: Path, tmp_path: Path, fake_backend: FakeServer
) -> None:
    probe = runner.invoke(cli.app, ["probe", "-c", str(config_file)])
    assert probe.exit_code == 0, probe.output
    assert "fake-model" in probe.output

    runner.invoke(
        cli.app, ["run", "-c", str(config_file), "-e", "fake", "--output-dir", str(tmp_path)]
    )
    [json_path] = tmp_path.glob("*.json")
    rendered = runner.invoke(cli.app, ["report", str(json_path), "--format", "markdown"])
    assert rendered.exit_code == 0
    assert rendered.output.startswith("**Hardware:**")


def test_report_merges_files(
    runner: CliRunner, config_file: Path, tmp_path: Path, fake_backend: FakeServer
) -> None:
    for tag in ("a", "b"):
        args = ["run", "-c", str(config_file), "-e", "fake", "--output-dir", str(tmp_path)]
        assert runner.invoke(cli.app, [*args, "--tag", tag]).exit_code == 0
    files = sorted(str(p) for p in tmp_path.glob("*.json"))
    merged_md = tmp_path / "merged.md"

    result = runner.invoke(cli.app, ["report", *files, "--output", str(merged_md)])

    assert result.exit_code == 0, result.output
    assert merged_md.read_text().count("| Fake engine | decode |") == 4


def test_version(runner: CliRunner) -> None:
    result = runner.invoke(cli.app, ["--version"])
    assert result.exit_code == 0
    assert result.output.startswith("llm-bench ")
