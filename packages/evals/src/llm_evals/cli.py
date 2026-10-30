"""Command line interface: ``llm-evals list | run | report | rescore``."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import httpx
import typer
from llm_bench.sysinfo import probe_engine, system_info
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeElapsedColumn
from rich.table import Table

from llm_evals import __version__, runner
from llm_evals.config import Backend, EvalConfig, RequestOptions
from llm_evals.report import baseline_first, to_markdown, to_rich_table
from llm_evals.results import BackendInfo, EvalReport, ItemResult, SuiteInfo
from llm_evals.suite import SUITE_NAMES, load_suites
from llm_evals.tasks import Task, tasks_for

app = typer.Typer(
    help="Evaluate the output quality of OpenAI-compatible LLM servers.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()

DEFAULT_CONFIG = Path("configs/evals.yaml")


class OutputFormat(StrEnum):
    table = "table"
    markdown = "markdown"


def _http_client() -> httpx.AsyncClient:
    # No read timeout here: every request has its own deadline (see client.complete).
    return httpx.AsyncClient(
        timeout=httpx.Timeout(None, connect=10.0),
        limits=httpx.Limits(max_connections=64, max_keepalive_connections=64),
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


def _check_suites(names: list[str], where: str) -> None:
    if unknown := [name for name in names if name not in SUITE_NAMES]:
        raise typer.BadParameter(
            f"unknown suite in {where}: {', '.join(unknown)} (available: {', '.join(SUITE_NAMES)})"
        )


@app.command("list")
def list_suites() -> None:
    """Show the bundled suites, their tasks and item counts."""
    table = Table(header_style="bold cyan")
    for column in ("Suite", "Tasks", "Items", "Scoring", "Measures"):
        table.add_column(column, justify="right" if column == "Items" else "left")
    for name, suite in load_suites().items():
        tasks = tasks_for(suite)
        table.add_row(
            name,
            "\n".join(task.name for task in tasks),
            str(len(suite.items)),
            tasks[0].scoring,
            suite.description,
        )
    console.print(table)


@app.command()
def run(
    config: Annotated[
        Path,
        typer.Option("--config", "-c", exists=True, dir_okay=False, help="Eval config (YAML)."),
    ] = DEFAULT_CONFIG,
    backend: Annotated[
        list[str] | None, typer.Option("--backend", "-b", help="Backend(s) to run. Default: all.")
    ] = None,
    suite: Annotated[
        list[str] | None,
        typer.Option("--suite", "-s", help="Suite(s) to run. Default: the backend's list, or all."),
    ] = None,
    limit: Annotated[
        int | None, typer.Option(min=1, help="Only the first N items of each suite (smoke test).")
    ] = None,
    concurrency: Annotated[
        int | None, typer.Option(min=1, help="Override requests in flight per backend.")
    ] = None,
    output_dir: Annotated[Path, typer.Option(help="Where to write JSON + Markdown.")] = Path(
        "benchmarks/evals"
    ),
    tag: Annotated[str | None, typer.Option(help="Suffix for the result file name.")] = None,
    fail_on_error: Annotated[
        bool, typer.Option(help="Exit non-zero if a backend is down or any request fails.")
    ] = False,
) -> None:
    """Run suites against backends and save item-level results."""
    cfg = EvalConfig.load(config)
    backends = _select(cfg.backends, backend, "backend")
    _check_suites(suite or [], "--suite")
    for name, spec in backends.items():
        _check_suites(spec.suites or [], f"backend '{name}'")

    report, skipped = asyncio.run(_run_all(cfg, backends, suite, limit, concurrency))
    if not report.items:
        console.print("[red]Nothing was evaluated: no backend was reachable.[/]")
        raise typer.Exit(1)

    stem = f"{report.created_at:%Y%m%d-%H%M%S}" + (f"-{tag}" if tag else "")
    json_path = output_dir / f"{stem}.json"
    report.save(json_path)
    json_path.with_suffix(".md").write_text(to_markdown(report))

    console.print(to_rich_table(report))
    console.print(f"Saved [bold]{json_path}[/] and [bold]{json_path.with_suffix('.md')}[/]")

    errors = sum(item.error is not None for item in report.items)
    if fail_on_error and (errors or skipped):
        console.print(f"[red]{errors} failed request(s), skipped backends: {skipped or 'none'}[/]")
        raise typer.Exit(1)


async def _run_all(
    cfg: EvalConfig,
    backends: dict[str, Backend],
    suites_wanted: list[str] | None,
    limit: int | None,
    concurrency_override: int | None,
) -> tuple[EvalReport, list[str]]:
    report = EvalReport(
        created_at=datetime.now(UTC), tool_version=__version__, system=system_info()
    )
    skipped: list[str] = []

    async with _http_client() as client:
        for name, backend in backends.items():
            probed = await probe_engine(client, backend)
            if not probed.available:
                console.print(f"[yellow]Skipping {name}: {probed.error}[/]")
                skipped.append(name)
                continue

            suites = load_suites(suites_wanted or backend.suites)
            options = cfg.options_for(backend)
            report.backends[name] = BackendInfo(
                label=backend.label,
                model=backend.model,
                server=probed.server,
                extra_body=backend.extra_body,
                max_tokens=options.max_tokens,
                temperature=options.temperature,
            )
            for suite in suites.values():
                report.suites[suite.name] = SuiteInfo(
                    kind=suite.kind,
                    items=len(suite.items),
                    fingerprint=suite.fingerprint,
                    tasks=[task.name for task in tasks_for(suite)],
                )

            tasks = [task for suite in suites.values() for task in tasks_for(suite)]
            concurrency = concurrency_override or cfg.concurrency_for(backend)
            results = await _run_backend(
                client, name, backend, tasks, options, concurrency=concurrency, limit=limit
            )
            report.add(results)
            if errors := [r for r in results if r.error]:
                console.print(f"[red]  {len(errors)} request error(s), e.g. {errors[0].error}[/]")

    return report, skipped


async def _run_backend(
    client: httpx.AsyncClient,
    name: str,
    backend: Backend,
    tasks: list[Task[Any]],
    options: RequestOptions,
    *,
    concurrency: int,
    limit: int | None,
) -> list[ItemResult]:
    progress = Progress(
        TextColumn("{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    )
    with progress:
        bars = {
            task.name: progress.add_task(f"{name} · {task.name}", total=len(task.items[:limit]))
            for task in tasks
        }

        def advance(result: ItemResult) -> None:
            progress.advance(bars[result.task])

        return await runner.run_tasks(
            client,
            name,
            backend,
            tasks,
            options,
            concurrency=concurrency,
            limit=limit,
            on_result=advance,
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
    failures: Annotated[
        int, typer.Option(min=0, help="Failed items shown per backend and task.")
    ] = 3,
    baseline: Annotated[
        str | None, typer.Option(help="Backend the others are compared against. Default: first.")
    ] = None,
) -> None:
    """Render saved result files; several files are merged into one comparison."""
    try:
        data = baseline_first(EvalReport.merge([EvalReport.load(p) for p in paths]), baseline)
        markdown = to_markdown(data, failures)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if output is not None:
        output.write_text(markdown)
        console.print(f"Wrote [bold]{output}[/]")
    elif output_format is OutputFormat.markdown:
        typer.echo(markdown, nl=False)
    else:
        console.print(to_rich_table(data))


@app.command()
def rescore(
    paths: Annotated[
        list[Path],
        typer.Argument(exists=True, dir_okay=False, help="Result JSON files to update in place."),
    ],
) -> None:
    """Re-score stored replies with the current scorers (no model calls) and rewrite files."""
    for path in paths:
        before = EvalReport.load(path)
        try:
            after = runner.rescore(before)
        except ValueError as exc:
            raise typer.BadParameter(f"{path}: {exc}") from exc
        changed = sum(a.passed != b.passed for a, b in zip(before.items, after.items, strict=True))
        after.save(path)
        path.with_suffix(".md").write_text(to_markdown(after))
        console.print(f"{path}: {changed} verdict(s) changed")


@app.callback(invoke_without_command=True)
def _version(
    version: Annotated[bool, typer.Option("--version", help="Show version and exit.")] = False,
) -> None:
    if version:
        typer.echo(f"llm-evals {__version__}")
        raise typer.Exit
