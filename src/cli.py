"""Entry point: `patent-screener screen idea.txt` or `patent-screener serve`"""
from __future__ import annotations

import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.theme import Theme

from pipeline import run_pipeline
from report import build_html_report, build_markdown_report
from theme import BANNER, CYAN, PINK, TEXT

console = Console(theme=Theme({"pink": PINK, "cyan": CYAN, "text": TEXT}))


def _print_banner() -> None:
    console.print(f"[pink]{BANNER}[/pink]")
    console.print("[cyan]patent-screener.exe[/cyan] [text]-- idea screening pipeline[/text]\n")


@click.group()
def main() -> None:
    """Screen a product idea against existing patents."""


@main.command()
@click.argument("idea_path", type=click.Path(exists=True, path_type=Path))
@click.option("--out", "out_dir", type=click.Path(path_type=Path), default=Path("reports"))
@click.option("--html/--no-html", default=True, help="Also write a styled HTML report.")
def screen(idea_path: Path, out_dir: Path, html: bool) -> None:
    """Screen IDEA_PATH (a text file) against existing patents."""
    load_dotenv()
    _print_banner()
    out_dir.mkdir(parents=True, exist_ok=True)

    idea_text = idea_path.read_text()
    result = run_pipeline(idea_text, on_event=console.print)

    if not result.sources_searched:
        console.print("[pink]No sources are configured. Set API keys in .env and retry.[/pink]")
        sys.exit(1)

    console.print("Writing report...")
    markdown = build_markdown_report(result.idea, result.entries, result.sources_searched)
    md_path = out_dir / f"{idea_path.stem}.md"
    md_path.write_text(markdown)
    console.print(f"  wrote {md_path}")

    if html:
        html_report = build_html_report(result.idea, result.entries, result.sources_searched)
        html_path = out_dir / f"{idea_path.stem}.html"
        html_path.write_text(html_report)
        console.print(f"  wrote {html_path}")

    usage = result.usage.summary()
    console.print(
        f"\n[cyan]tokens:[/cyan] {usage['input_tokens']} in / {usage['output_tokens']} out  "
        f"[cyan]est. cost:[/cyan] ${usage['estimated_cost_usd']:.4f}"
    )
    console.print("\n[pink]done.[/pink] Screening aid only. Not legal advice.")


@main.command()
@click.option("--host", default="127.0.0.1", help="Bind address. Keep this local-only.")
@click.option("--port", default=8000)
def serve(host: str, port: int) -> None:
    """Run the local web UI (textarea in, ranked matches out)."""
    load_dotenv()
    import uvicorn

    from web import app

    _print_banner()
    console.print(f"[cyan]Serving locally at[/cyan] http://{host}:{port}")
    console.print("[text]This is a local-only server. Do not expose it to the internet.[/text]\n")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
