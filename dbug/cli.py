"""D-BUG CLI — Beautiful terminal interface with Rich."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from dbug import __version__

app = typer.Typer(
    name="dbug",
    help="🐛 D-BUG: AI-Powered Autonomous Debugging Platform",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_time=False, show_path=False)],
    )


def _banner() -> None:
    banner = Text()
    banner.append("╔══════════════════════════════════════╗\n", style="bold cyan")
    banner.append("║  ", style="bold cyan")
    banner.append("🐛 D-BUG", style="bold white")
    banner.append(f" v{__version__}", style="dim")
    banner.append("                    ║\n", style="bold cyan")
    banner.append("║  ", style="bold cyan")
    banner.append("Autonomous Debugging Platform", style="italic")
    banner.append("      ║\n", style="bold cyan")
    banner.append("╚══════════════════════════════════════╝", style="bold cyan")
    console.print(banner)


@app.command()
def chat(
    path: str = typer.Argument(".", help="Working directory"),
) -> None:
    """💬 Interactive mode — chat with D-BUG like an AI assistant."""
    _banner()
    from dbug.agents.chat import chat_loop

    target = Path(path).resolve()
    asyncio.run(chat_loop(cwd=str(target)))


@app.command()
def scan(
    path: str = typer.Argument(".", help="Path to scan"),
    max_bugs: int = typer.Option(10, "--max-bugs", "-m", help="Max bugs to analyze"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="LLM provider: groq|ollama|huggingface"),
) -> None:
    """🔍 Scan a codebase for bugs using AI-powered analysis."""
    _setup_logging(verbose)
    _banner()

    target = Path(path).resolve()
    if not target.exists():
        console.print(f"[red]Error:[/red] Path not found: {target}")
        raise typer.Exit(1)

    console.print(f"\n[bold]Target:[/bold] {target}")
    console.print(f"[bold]Max bugs:[/bold] {max_bugs}\n")

    # Set provider if specified
    if provider:
        import os
        os.environ["DBUG_LLM_PROVIDER"] = provider

    asyncio.run(_run_scan(target, max_bugs))


async def _run_scan(target: Path, max_bugs: int) -> None:
    from dbug.orchestrator.graph import DebugPipeline

    messages: list[str] = []

    def on_progress(msg: str) -> None:
        messages.append(msg)
        console.print(f"  [dim]→[/dim] {msg}")

    pipeline = DebugPipeline(on_progress=on_progress)

    with console.status("[bold green]Running D-BUG pipeline...", spinner="dots"):
        state = await pipeline.run(str(target), max_bugs=max_bugs)

    # Results
    console.print()
    _print_scan_summary(state)

    if state.bugs:
        _print_bugs_table(state)

    if state.errors:
        console.print(f"\n[yellow]⚠ {len(state.errors)} warnings during scan[/yellow]")


def _print_scan_summary(state: Any) -> None:
    from dbug.orchestrator.state import PipelineState

    summary = Table(show_header=False, box=None, padding=(0, 2))
    summary.add_column(style="bold")
    summary.add_column()
    summary.add_row("📁 Files scanned", str(state.total_files))
    summary.add_row("📦 Code chunks", str(state.total_chunks))
    summary.add_row("🔤 Languages", ", ".join(state.languages) if state.languages else "—")
    summary.add_row("🐛 Bugs found", str(state.bugs_found))
    summary.add_row("✅ Auto-fixed", str(state.bugs_fixed))
    summary.add_row("📊 Status", state.stage.value)

    console.print(Panel(summary, title="[bold]Scan Results[/bold]", border_style="green"))


def _print_bugs_table(state: Any) -> None:
    table = Table(title="🐛 Bugs Found", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Severity", width=10)
    table.add_column("File", style="cyan")
    table.add_column("Lines", width=10)
    table.add_column("Category", width=14)
    table.add_column("Title")
    table.add_column("Fixed?", width=7)

    severity_colors = {
        "critical": "red bold",
        "high": "red",
        "medium": "yellow",
        "low": "dim",
    }

    for i, bug in enumerate(state.bugs, 1):
        color = severity_colors.get(bug.severity, "white")
        table.add_row(
            str(i),
            f"[{color}]{bug.severity.upper()}[/{color}]",
            Path(bug.file_path).name,
            f"{bug.start_line}-{bug.end_line}",
            bug.category,
            bug.title[:60],
            "✅" if bug.fix_validated else "❌",
        )

    console.print(table)


@app.command()
def analyze(
    file: str = typer.Argument(..., help="File to analyze"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """🔬 Analyze a single file for bugs."""
    _setup_logging(verbose)
    _banner()
    target = Path(file).resolve()
    if not target.is_file():
        console.print(f"[red]Error:[/red] File not found: {target}")
        raise typer.Exit(1)

    asyncio.run(_run_scan(target.parent, max_bugs=5))


@app.command(name="test-gen")
def test_gen(
    file: str = typer.Argument(..., help="File to generate tests for"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """⚔️ Generate adversarial tests for a file."""
    _setup_logging(verbose)
    _banner()

    target = Path(file).resolve()
    if not target.is_file():
        console.print(f"[red]Error:[/red] File not found: {target}")
        raise typer.Exit(1)

    asyncio.run(_gen_tests(target, output))


async def _gen_tests(target: Path, output: Optional[str]) -> None:
    from dbug.agents.adversarial import AdversarialAgent
    from dbug.rag.parser import CodeParser

    parser = CodeParser()
    language = parser.detect_language(target)
    if not language:
        console.print(f"[red]Unsupported file type:[/red] {target.suffix}")
        return

    code = target.read_text()
    agent = AdversarialAgent()

    with console.status("[bold green]Generating adversarial tests..."):
        result = await agent.run(code=code, file_path=str(target), language=language)

    console.print(f"\n[bold green]Generated {len(result.tests)} adversarial tests[/bold green]\n")

    all_tests = "\n\n".join(t.test_code for t in result.tests)

    if output:
        Path(output).write_text(all_tests)
        console.print(f"[green]Written to {output}[/green]")
    else:
        console.print(all_tests)


@app.command()
def summary(
    path: str = typer.Argument(".", help="Path to summarize"),
    no_ai: bool = typer.Option(False, "--no-ai", help="Skip AI summary, only heuristics"),
) -> None:
    """📝 Get an AI-powered summary of your codebase."""
    _banner()

    target = Path(path).resolve()
    if not target.exists():
        console.print(f"[red]Error:[/red] Path not found: {target}")
        raise typer.Exit(1)

    console.print(f"\n[bold]Analyzing:[/bold] {target}\n")

    asyncio.run(_run_summary(target, use_ai=not no_ai))


async def _run_summary(target: Path, use_ai: bool) -> None:
    from dbug.agents.summarizer import Summarizer

    summarizer = Summarizer()

    with console.status("[bold green]Analyzing codebase..."):
        result = await summarizer.summarize(target, use_ai=use_ai)

    console.print(Panel(result, title="[bold]Codebase Summary[/bold]", border_style="cyan"))


@app.command()
def health(
    path: str = typer.Argument(".", help="Path to analyze"),
) -> None:
    """💊 Get a health score (A-F grade) for your codebase."""
    _banner()
    from dbug.agents.health_scorer import HealthScorer

    target = Path(path).resolve()
    scorer = HealthScorer()
    report = scorer.score(target)

    # Grade display
    grade_colors = {"A": "green bold", "B": "green", "C": "yellow", "D": "red", "F": "red bold"}
    gc = grade_colors.get(report.grade, "white")

    console.print()
    console.print(Panel(
        f"[{gc}]  {report.grade}  [/{gc}] — [bold]{report.score}/100[/bold]",
        title="[bold]Code Health Grade[/bold]",
        border_style="cyan",
        padding=(1, 4),
    ))

    # Breakdown table
    table = Table(title="📊 Score Breakdown", show_lines=True)
    table.add_column("Category", style="bold")
    table.add_column("Score", width=8)
    table.add_column("Bar", width=20)

    for name, score in [
        ("🔒 Security", report.security_score),
        ("🧩 Complexity", report.complexity_score),
        ("✨ Quality", report.quality_score),
        ("📖 Documentation", report.documentation_score),
    ]:
        bar_len = int(score / 5)
        bar = f"[green]{'█' * bar_len}[/green][dim]{'░' * (20 - bar_len)}[/dim]"
        table.add_row(name, f"{score:.0f}/100", bar)

    console.print(table)

    # Issues
    console.print(f"\n[red]🔴 Critical: {report.critical_issues}[/red]  "
                  f"[yellow]🟠 High: {report.high_issues}[/yellow]  "
                  f"🟡 Medium: {report.medium_issues}  "
                  f"[dim]🟢 Low: {report.low_issues}[/dim]")

    # Recommendations
    if report.top_recommendations:
        console.print("\n[bold]Recommendations:[/bold]")
        for rec in report.top_recommendations:
            console.print(f"  {rec}")

    # Badge URL
    console.print(f"\n[dim]Shield badge: {report.to_badge_url()}[/dim]")


@app.command()
def watch(
    path: str = typer.Argument(".", help="Path to watch"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """👁️ Watch for file changes and auto-scan in real-time."""
    _setup_logging(verbose)
    _banner()

    from dbug.agents.watcher import FileWatcher
    from dbug.agents.health_scorer import HealthScorer

    console.print(f"\n[bold cyan]Watching:[/bold cyan] {Path(path).resolve()}")
    console.print("[dim]Ctrl+C to stop[/dim]\n")

    scorer = HealthScorer()

    async def on_change(changed_files: list[str]) -> None:
        console.print(f"\n[bold yellow]📝 Changed:[/bold yellow] {', '.join(Path(f).name for f in changed_files[:3])}")
        report = scorer.score(Path(path))
        gc = "green" if report.score >= 80 else "yellow" if report.score >= 60 else "red"
        console.print(f"  Health: [{gc}]{report.grade}[/{gc}] ({report.score:.0f}/100)")

    watcher = FileWatcher(path=path, on_change=on_change)
    try:
        asyncio.run(watcher.watch())
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped watching.[/dim]")


@app.command()
def report(
    path: str = typer.Argument(".", help="Path to scan"),
    format: str = typer.Option("html", "--format", "-f", help="Output format: html|md|json"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file name"),
    max_bugs: int = typer.Option(5, "--max-bugs", "-m"),
) -> None:
    """📄 Generate a scan report (HTML/Markdown/JSON)."""
    _setup_logging(False)
    _banner()
    asyncio.run(_generate_report(path, format, output, max_bugs))


async def _generate_report(path: str, fmt: str, output: Optional[str], max_bugs: int) -> None:
    from dbug.orchestrator.graph import DebugPipeline
    from dbug.agents.reporter import ReportGenerator

    pipeline = DebugPipeline(on_progress=lambda m: console.print(f"  [dim]→[/dim] {m}"))

    with console.status("[bold green]Scanning for report..."):
        state = await pipeline.run(path, max_bugs=max_bugs)

    gen = ReportGenerator()
    if fmt == "html":
        out = gen.generate_html(state, output or "dbug_report.html")
    elif fmt == "md":
        out = gen.generate_markdown(state, output or "dbug_report.md")
    else:
        out = gen.generate_json(state, output or "dbug_report.json")

    console.print(f"\n[bold green]✅ Report generated:[/bold green] {out}")


@app.command()
def heal(
    path: str = typer.Argument(".", help="Path to scan and auto-fix"),
    dry_run: bool = typer.Option(True, "--dry-run/--apply", help="Preview fixes without applying"),
    max_bugs: int = typer.Option(5, "--max-bugs", "-m"),
) -> None:
    """🩹 Auto-fix bugs and commit changes (self-healing mode)."""
    _setup_logging(False)
    _banner()

    if not dry_run:
        console.print("[bold yellow]⚠️  LIVE MODE — fixes will be applied to source files![/bold yellow]\n")

    asyncio.run(_run_heal(path, dry_run, max_bugs))


async def _run_heal(path: str, dry_run: bool, max_bugs: int) -> None:
    from dbug.orchestrator.graph import DebugPipeline
    from dbug.agents.self_healer import SelfHealer

    pipeline = DebugPipeline(on_progress=lambda m: console.print(f"  [dim]→[/dim] {m}"))

    with console.status("[bold green]Scanning and generating fixes..."):
        state = await pipeline.run(path, max_bugs=max_bugs)

    healer = SelfHealer(repo_path=path)
    fixed_count = 0
    for bug in state.bugs:
        if bug.fix_validated and bug.fix_code:
            success = healer.apply_fix(bug, dry_run=dry_run)
            if success:
                fixed_count += 1
                mode = "[dim]DRY RUN[/dim]" if dry_run else "[green]APPLIED[/green]"
                console.print(f"  {mode} {Path(bug.file_path).name}:{bug.start_line} — {bug.title[:50]}")

    if dry_run:
        console.print(f"\n[cyan]Would fix {fixed_count} bug(s). Run with --apply to apply.[/cyan]")
    else:
        healer.commit_fixes(state.bugs)
        console.print(f"\n[bold green]✅ Applied and committed {fixed_count} fix(es)![/bold green]")


@app.command()
def config(
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Set LLM provider"),
    show: bool = typer.Option(False, "--show", "-s", help="Show current config"),
) -> None:
    """⚙️ Configure D-BUG settings."""
    _banner()

    if show or not provider:
        from dbug.config import get_settings

        settings = get_settings()
        table = Table(title="⚙️ Configuration", show_lines=True)
        table.add_column("Setting", style="bold")
        table.add_column("Value")
        table.add_row("LLM Provider", settings.llm_provider.value)
        table.add_row("Groq API Key", "✅ Set" if settings.has_groq else "❌ Not set")
        table.add_row("Web Search", "✅ DuckDuckGo (no key needed)")
        table.add_row("GitHub Token", "✅ Set" if settings.has_github else "❌ Not set")
        table.add_row("Sentry DSN", "✅ Set" if settings.has_sentry else "❌ Not set")
        table.add_row("Embedding Model", settings.embedding_model)
        table.add_row("ChromaDB Path", str(settings.chroma_db_path))
        console.print(table)

    if provider:
        console.print(f"[green]Set LLM provider to: {provider}[/green]")
        console.print(f"Run: [bold]export DBUG_LLM_PROVIDER={provider}[/bold]")


@app.command()
def version() -> None:
    """📋 Show version."""
    console.print(f"D-BUG v{__version__}")


if __name__ == "__main__":
    app()

