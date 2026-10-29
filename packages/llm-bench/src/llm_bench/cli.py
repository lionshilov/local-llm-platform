"""Command line interface: ``llm-bench probe | run | report``."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import httpx
import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from llm_bench import __version__
from llm_bench.client import RequestResult
from llm_bench.config import BenchConfig, Engine, Scenario
from llm_bench.metrics import summarize
from llm_bench.report import to_markdown, to_rich_table
from llm_bench.results import BenchReport, RunRecord
from llm_bench.runner import run_level, warm_up
from llm_bench.sysinfo import EngineProbe, probe_engine, system_info

app = typer.Typer(
    help="Benchmark OpenAI-compatible LLM inference servers.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()

ConfigOption = Annotated[
    Path,
    typer.Option("--config", "-c", exists=True, dir_okay=False, help="Benchmark config (YAML)."),
]
DEFAULT_CONFIG = Path("configs/bench.yaml")


class OutputFormat(StrEnum):
    table = "table"
    markdown = "markdown"


def _http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(600.0, connect=10.0),
        limits=httpx.Limits(max_connections=256, max_keepalive_connections=256),
    )


def _select[T](available: dict[str, T], wanted: list[str] | None, kind: str) -> dict[str, T]:
    if not wanted:
        return dict(available)
    unknown = [name for name in wanted if name not in available]
    if unknown:
        raise typer.BadParameter(
            f"unknown {kind}: {', '.join(unknown)} (configured: {', '.join(available)})"
        )
    return {name: available[name] for name in wanted}


@app.command()
def probe(config: ConfigOption = DEFAULT_CONFIG) -> None:
    """Check which configured engines are reachable and what they serve."""
    cfg = BenchConfig.load(config)

    async def probe_all() -> list[EngineProbe]:
        async with _http_client() as client:
            return await asyncio.gather(*(probe_engine(client, e) for e in cfg.engines.values()))

    table = Table(header_style="bold cyan")
    for column in ("Engine", "URL", "Status", "Server", "Models"):
        table.add_column(column)
    for (name, engine), result in zip(cfg.engines.items(), asyncio.run(probe_all()), strict=True):
        status = "[green]up[/]" if result.available else "[red]down[/]"
        models = ", ".join(result.models) if result.available else (result.error or "")
        table.add_row(name, engine.base_url, status, result.server or "-", models)
    console.print(table)


@app.command()
def run(
    config: ConfigOption = DEFAULT_CONFIG,
    engine: Annotated[
        list[str] | None, typer.Option("--engine", "-e", help="Engine(s) to run. Default: all.")
    ] = None,
    scenario: Annotated[
        list[str] | None, typer.Option("--scenario", "-s", help="Scenario(s) to run. Default: all.")
    ] = None,
    requests: Annotated[
        int | None, typer.Option(min=1, help="Override requests per concurrency level.")
    ] = None,
    warmup: Annotated[int, typer.Option(min=0, help="Warm-up requests per engine.")] = 1,
    output_dir: Annotated[Path, typer.Option(help="Where to write JSON + Markdown.")] = Path(
        "benchmarks/results"
    ),
    tag: Annotated[str | None, typer.Option(help="Suffix for the result file name.")] = None,
    fail_on_error: Annotated[
        bool, typer.Option(help="Exit non-zero if an engine is down or any request fails.")
    ] = False,
) -> None:
    """Run the benchmark matrix: engines x scenarios x concurrency levels."""
    cfg = BenchConfig.load(config)
    engines = _select(cfg.engines, engine, "engine")
    scenarios = _select(cfg.scenarios, scenario, "scenario")

    report, skipped = asyncio.run(_run_matrix(engines, scenarios, requests, warmup))
    if not report.runs:
        console.print("[red]Nothing was measured: no engine was reachable.[/]")
        raise typer.Exit(1)

    stem = f"{report.created_at:%Y%m%d-%H%M%S}" + (f"-{tag}" if tag else "")
    json_path = output_dir / f"{stem}.json"
    report.save(json_path)
    json_path.with_suffix(".md").write_text(to_markdown(report))

    console.print(to_rich_table(report))
    console.print(f"Saved [bold]{json_path}[/] and [bold]{json_path.with_suffix('.md')}[/]")

    failed = sum(r.summary.errors for r in report.runs)
    if fail_on_error and (failed or skipped):
        console.print(f"[red]{failed} failed request(s), skipped engines: {skipped or 'none'}[/]")
        raise typer.Exit(1)


async def _run_matrix(
    engines: dict[str, Engine],
    scenarios: dict[str, Scenario],
    requests_override: int | None,
    warmup_rounds: int,
) -> tuple[BenchReport, list[str]]:
    report = BenchReport(
        created_at=datetime.now(UTC),
        tool_version=__version__,
        system=system_info(),
        engines={},
    )
    skipped: list[str] = []

    async with _http_client() as client:
        for name, engine in engines.items():
            probed = await probe_engine(client, engine)
            if not probed.available:
                console.print(f"[yellow]Skipping {name}: {probed.error}[/]")
                skipped.append(name)
                continue

            with console.status(f"Warming up {name}…"):
                warm = await warm_up(client, engine, warmup_rounds)
            if any(not w.ok for w in warm):
                error = next(w.error for w in warm if not w.ok)
                console.print(f"[yellow]Skipping {name}: warm-up failed: {error}[/]")
                skipped.append(name)
                continue

            report.engines[name] = {
                "label": engine.label,
                "model": engine.model,
                "server": probed.server,
                "extra_body": engine.extra_body,
            }
            await _run_engine(client, name, engine, scenarios, requests_override, report)

    return report, skipped


async def _run_engine(
    client: httpx.AsyncClient,
    name: str,
    engine: Engine,
    scenarios: dict[str, Scenario],
    requests_override: int | None,
    report: BenchReport,
) -> None:
    progress = Progress(
        TextColumn("{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    )
    with progress:
        for scenario_name, scenario in scenarios.items():
            for concurrency in scenario.concurrency:
                total = requests_override or scenario.requests_for(concurrency)
                task = progress.add_task(
                    f"{name} · {scenario_name} · {concurrency} user(s)", total=total
                )

                def advance(_result: RequestResult, task_id: TaskID = task) -> None:
                    progress.advance(task_id)

                results, wall_s = await run_level(
                    client, engine, scenario, concurrency, total, on_request_done=advance
                )
                summary = summarize(results, wall_s)
                report.runs.append(
                    RunRecord(
                        engine=name,
                        label=engine.label,
                        model=engine.model,
                        scenario=scenario_name,
                        prompt_words=scenario.prompt_words,
                        max_tokens=scenario.max_tokens,
                        concurrency=concurrency,
                        summary=summary,
                        requests=results,
                    )
                )
                if summary.errors:
                    first_error = next(r.error for r in results if not r.ok)
                    progress.console.print(
                        f"[red]  {summary.errors} error(s), e.g. {first_error}[/]"
                    )


@app.command()
def report(
    paths: Annotated[
        list[Path],
        typer.Argument(exists=True, dir_okay=False, help="One or more result JSON files."),
    ],
    output_format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.table,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write Markdown to this file.")
    ] = None,
) -> None:
    """Render saved result files; several files are merged into one table."""
    data = BenchReport.merge([BenchReport.load(path) for path in paths])
    if output is not None:
        output.write_text(to_markdown(data))
        console.print(f"Wrote [bold]{output}[/]")
    elif output_format is OutputFormat.markdown:
        typer.echo(to_markdown(data), nl=False)
    else:
        console.print(to_rich_table(data))


@app.callback(invoke_without_command=True)
def _version(
    version: Annotated[bool, typer.Option("--version", help="Show version and exit.")] = False,
) -> None:
    if version:
        typer.echo(f"llm-bench {__version__}")
        raise typer.Exit
