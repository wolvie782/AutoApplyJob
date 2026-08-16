"""
AutoApplyJob CLI

Commands:
  start       — run the full job application loop across all enabled platforms
  dashboard   — launch the web dashboard at http://localhost:8000
  stats       — print application stats in the terminal
  test-login  — open a platform in the browser to verify login
"""

import asyncio
import os
import subprocess
from pathlib import Path

import click
import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

console = Console()

PROJECT_ROOT = Path(__file__).parent.parent


def _load_config() -> dict:
    with open(PROJECT_ROOT / "config" / "config.yaml") as f:
        config = yaml.safe_load(f)

    # Merge personal data from env into config (keeps .yaml clean for git)
    config.setdefault("profile", {}).update({
        "name":              os.getenv("PROFILE_NAME", ""),
        "email":             os.getenv("PROFILE_EMAIL", ""),
        "phone":             os.getenv("PROFILE_PHONE", ""),
        "phone_with_code":   os.getenv("PROFILE_PHONE_WITH_CODE", ""),
        "gender":            os.getenv("PROFILE_GENDER", "Male"),
        "nationality":       os.getenv("PROFILE_NATIONALITY", "Indian"),
        "location":          os.getenv("PROFILE_LOCATION", "India"),
        "linkedin_url":      os.getenv("PROFILE_LINKEDIN", ""),
        "github_url":        os.getenv("PROFILE_GITHUB", ""),
        "portfolio_url":     os.getenv("PROFILE_PORTFOLIO", ""),
    })

    config.setdefault("experience", {}).update({
        "years":                int(os.getenv("EXP_YEARS", "4")),
        "current_ctc":          os.getenv("EXP_CURRENT_CTC", ""),
        "expected_ctc":         os.getenv("EXP_EXPECTED_CTC", ""),
        "notice_period":        os.getenv("EXP_NOTICE_PERIOD", "30 days"),
        "current_company":      os.getenv("EXP_CURRENT_COMPANY", ""),
        "current_designation":  os.getenv("EXP_CURRENT_DESIGNATION", ""),
    })

    config.setdefault("education", {}).update({
        "degree":          os.getenv("EDU_DEGREE", ""),
        "field":           os.getenv("EDU_FIELD", ""),
        "college":         os.getenv("EDU_COLLEGE", ""),
        "graduation_year": int(os.getenv("EDU_GRADUATION_YEAR", "2022")),
    })

    return config


def _get_bots(config: dict, platforms: tuple[str]) -> list:
    from .bots.linkedin import LinkedInBot
    from .bots.instahyre import InstahyreBot
    from .bots.indeed import IndeedBot
    from .bots.jobright import JobRightBot
    from .bots.uplers import UplerBot

    all_bots = {
        "linkedin": LinkedInBot,
        "instahyre": InstahyreBot,
        "indeed": IndeedBot,
        "jobright": JobRightBot,
        "uplers": UplerBot,
    }

    selected = set(platforms) if platforms else set(all_bots.keys())
    bots = []
    for name, cls in all_bots.items():
        if name in selected and config["platforms"].get(name, {}).get("enabled", True):
            bots.append(cls(config))
    return bots


@click.group()
def cli():
    pass


@cli.command()
@click.option("--platforms", "-p", multiple=True,
              help="Platforms to apply on. Repeat for multiple: -p linkedin -p indeed. Default: all enabled.")
@click.option("--max", "max_apps", default=None, type=int,
              help="Max applications per run (overrides config)")
def start(platforms, max_apps):
    """Run the auto job application loop."""
    load_dotenv(PROJECT_ROOT / ".env")
    config = _load_config()

    if max_apps:
        config["job_search"]["max_applications_per_run"] = max_apps

    if not (PROJECT_ROOT / "resume" / "resume.pdf").exists():
        console.print("[red]Resume not found at resume/resume.pdf — add your resume first.[/red]")
        return

    if not os.getenv("ANTHROPIC_API_KEY"):
        console.print("[yellow]Warning: ANTHROPIC_API_KEY not set — AI cover letters disabled.[/yellow]")

    console.print("[bold blue]AutoApplyJob starting...[/bold blue]")
    console.print(f"[dim]Target: Remote > Pune/Mumbai > Hyderabad > Bangalore[/dim]")
    console.print(f"[dim]Roles: {', '.join(config['job_search']['target_roles'][:3])}...[/dim]")
    console.print(f"[dim]Max applications: {config['job_search']['max_applications_per_run']}[/dim]\n")

    bots = _get_bots(config, platforms)
    if not bots:
        console.print("[red]No platforms selected or all disabled.[/red]")
        return

    async def run_all():
        total = 0
        for bot in bots:
            try:
                count = await bot.run()
                total += count
            except Exception as e:
                console.print(f"[red]{bot.platform_name} failed: {e}[/red]")
        return total

    total = asyncio.run(run_all())
    console.print(f"\n[bold green]Done! Applied to {total} jobs total.[/bold green]")


@cli.command()
@click.option("--port", default=8000, help="Dashboard port (default 8000)")
def dashboard(port):
    """Launch the web dashboard."""
    load_dotenv(PROJECT_ROOT / ".env")
    console.print(f"[bold blue]Dashboard running at http://localhost:{port}[/bold blue]")
    console.print("[dim]Press Ctrl+C to stop.[/dim]")
    os.chdir(PROJECT_ROOT)
    subprocess.run(
        ["uvicorn", "src.dashboard.app:app", "--reload", f"--port={port}"],
        cwd=PROJECT_ROOT,
    )


@cli.command()
def stats():
    """Print application statistics."""
    load_dotenv(PROJECT_ROOT / ".env")

    async def _stats():
        from .tracker import init_db, get_stats, get_all_applications
        await init_db()
        return await get_stats(), await get_all_applications(limit=10)

    data, recent = asyncio.run(_stats())

    console.print("\n[bold]AutoApplyJob — Application Stats[/bold]\n")

    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Metric")
    table.add_column("Count", justify="right")
    table.add_row("[bold]Total Applications[/bold]", str(data["total"]))
    for platform, count in sorted(data["by_platform"].items(), key=lambda x: -x[1]):
        table.add_row(f"  {platform}", str(count))
    console.print(table)

    if data["by_day"]:
        console.print("\n[bold]Last 7 Days[/bold]")
        for day, count in list(data["by_day"].items())[:7]:
            bar = "█" * min(count, 40)
            console.print(f"  {day}  {bar} {count}")

    if recent:
        console.print("\n[bold]10 Most Recent[/bold]")
        rtable = Table(show_header=True, header_style="bold")
        rtable.add_column("Platform")
        rtable.add_column("Role")
        rtable.add_column("Company")
        rtable.add_column("Applied At")
        for app in recent:
            rtable.add_row(
                app["platform"],
                app["job_title"] or "",
                app["company"] or "",
                (app["applied_at"] or "")[:16].replace("T", " "),
            )
        console.print(rtable)


@cli.command("test-login")
@click.option("--platform", "-p", required=True,
              type=click.Choice(["linkedin", "instahyre", "indeed", "jobright", "uplers"]))
def test_login(platform):
    """Open a platform in the connected Chrome to verify you're logged in."""
    load_dotenv(PROJECT_ROOT / ".env")
    urls = {
        "linkedin": "https://www.linkedin.com/feed/",
        "instahyre": "https://www.instahyre.com/",
        "indeed": "https://in.indeed.com/",
        "jobright": "https://jobright.ai/",
        "uplers": "https://www.uplers.com/",
    }

    async def _check():
        from playwright.async_api import async_playwright
        chrome_url = f"http://localhost:{os.getenv('CHROME_DEBUG_PORT', '9222')}"
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(chrome_url)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = await context.new_page()
            await page.goto(urls[platform])
            await asyncio.sleep(3)
            console.print(f"[green]Opened {platform} — check the browser window.[/green]")
            console.print(f"[dim]URL: {page.url}[/dim]")

    asyncio.run(_check())


def main():
    load_dotenv(PROJECT_ROOT / ".env")
    cli()


if __name__ == "__main__":
    main()
