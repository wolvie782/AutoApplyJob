"""
Base bot — connects to your existing Chrome session via CDP.
All platform bots inherit from this.

Prerequisites:
  Launch Chrome with remote debugging ONCE before running the bot:
    /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
        --remote-debugging-port=9222 \
        --user-data-dir="$HOME/.config/chrome-autoapply"

  Then log in to LinkedIn, Instahyre, Indeed, JobRight, Uplers in that window.
  Keep Chrome open while the bot runs.
"""

import asyncio
import os
import random
from abc import ABC, abstractmethod
from pathlib import Path

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from rich.console import Console

from ..tracker import init_db, is_applied, record_application
from ..ai.cover_letter import generate_cover_letter
from ..ai.resume_tailor import assess_fit
from ..ai.client import get_ai_config, build_client

console = Console()

CHROME_DEBUG_URL = f"http://localhost:{os.getenv('CHROME_DEBUG_PORT', '9222')}"
PROJECT_ROOT = Path(__file__).parent.parent.parent


class BaseBot(ABC):
    platform_name: str = "base"

    def __init__(self, config: dict):
        self.config = config
        self.profile = config["profile"]
        self.experience = config["experience"]
        self.job_search = config["job_search"]
        self.platform_config = config["platforms"].get(self.platform_name, {})
        self.resume_path = PROJECT_ROOT / config["profile"]["resume_path"]
        self.cover_letters_dir = PROJECT_ROOT / "cover_letters"
        self.cover_letters_dir.mkdir(exist_ok=True)

        ai_cfg = get_ai_config(config)
        self.ai_client = build_client(ai_cfg)
        self.ai_model = ai_cfg.model

        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.applied_count = 0
        self.max_applications = config["job_search"].get("max_applications_per_run", 30)

    async def setup(self):
        await init_db()
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.connect_over_cdp(CHROME_DEBUG_URL)
        # Reuse existing context (already logged-in session)
        contexts = self.browser.contexts
        if contexts:
            self.context = contexts[0]
        else:
            self.context = await self.browser.new_context()
        console.print(f"[green]Connected to Chrome — {self.platform_name}[/green]")

    async def teardown(self):
        # Don't close browser — user still needs it
        pass

    async def get_page(self) -> Page:
        page = await self.context.new_page()
        await page.set_viewport_size({"width": 1280, "height": 800})
        return page

    async def delay(self, min_s: float = 1.0, max_s: float = 3.0):
        await asyncio.sleep(random.uniform(min_s, max_s))

    async def safe_fill(self, page: Page, selector: str, value: str):
        try:
            await page.wait_for_selector(selector, timeout=5000)
            await page.fill(selector, "")
            await self.delay(0.2, 0.5)
            await page.type(selector, value, delay=random.randint(40, 100))
        except Exception:
            pass

    async def safe_click(self, page: Page, selector: str, timeout: int = 5000):
        try:
            await page.wait_for_selector(selector, timeout=timeout)
            await self.delay(0.3, 0.8)
            await page.click(selector)
            return True
        except Exception:
            return False

    async def already_applied(self, job_id: str) -> bool:
        return await is_applied(self.platform_name, job_id)

    async def save_application(self, job_id, job_title, company, url, location="", cover_letter_path=""):
        await record_application(
            platform=self.platform_name,
            job_id=job_id,
            job_title=job_title,
            company=company,
            url=url,
            location=location,
            cover_letter_path=cover_letter_path,
        )
        self.applied_count += 1
        console.print(
            f"[bold green]✓ Applied[/bold green] [{self.platform_name}] "
            f"[cyan]{job_title}[/cyan] @ [yellow]{company}[/yellow] — {location}"
        )

    async def generate_cover_letter_for_job(
        self, job_title: str, company: str, location: str, job_description: str
    ) -> str:
        if not self.ai_client:
            return ""

        safe_name = f"{company}_{job_title}".replace(" ", "_").replace("/", "-")[:60]
        cl_path = self.cover_letters_dir / f"{safe_name}.txt"

        text = await generate_cover_letter(
            job_title=job_title,
            company=company,
            location=location,
            job_description=job_description,
            config=self.config,
            client=self.ai_client,
            model=self.ai_model,
        )

        cl_path.write_text(text, encoding="utf-8")
        return text

    async def should_apply(self, job_title: str, company: str, job_description: str) -> bool:
        title_lower = job_title.lower()
        blacklisted_keywords = self.platform_config.get("blacklisted_keywords", [])
        blacklisted_companies = self.platform_config.get("blacklisted_companies", [])

        for kw in blacklisted_keywords:
            if kw.lower() in title_lower:
                return False

        for co in blacklisted_companies:
            if co.lower() in company.lower():
                return False

        if self.ai_client and job_description:
            fit = await assess_fit(job_title, company, job_description, self.ai_client, self.ai_model)
            score = fit.get("fit_score", 7)
            if score < 6:
                console.print(f"[dim]Skipping {job_title} @ {company} — fit score {score}/10[/dim]")
                return False

        return True

    def is_preferred_location(self, location: str) -> bool:
        if not location:
            return True
        loc_lower = location.lower()
        priority = [l.lower() for l in self.job_search.get("location_priority", [])]
        return any(p in loc_lower for p in priority)

    @abstractmethod
    async def search_jobs(self, page: Page) -> list[dict]:
        """Return list of dicts: {job_id, job_title, company, url, location, description}"""

    @abstractmethod
    async def apply_to_job(self, page: Page, job: dict) -> bool:
        """Apply to a single job. Return True if successful."""

    async def run(self):
        await self.setup()
        page = await self.get_page()

        try:
            jobs = await self.search_jobs(page)
            console.print(f"[bold]{self.platform_name}[/bold]: Found {len(jobs)} jobs")

            for job in jobs:
                if self.applied_count >= self.max_applications:
                    console.print(f"[yellow]Reached max {self.max_applications} applications[/yellow]")
                    break

                job_id = job.get("job_id", "")
                if not job_id:
                    continue

                if await self.already_applied(job_id):
                    continue

                if not self.is_preferred_location(job.get("location", "")):
                    continue

                can_apply = await self.should_apply(
                    job.get("job_title", ""),
                    job.get("company", ""),
                    job.get("description", ""),
                )
                if not can_apply:
                    continue

                try:
                    success = await self.apply_to_job(page, job)
                    if success:
                        cl_path = str(self.cover_letters_dir / f"{job.get('company', '')}_{job.get('job_title', '')}".replace(" ", "_")[:60]) + ".txt"
                        await self.save_application(
                            job_id=job_id,
                            job_title=job.get("job_title", ""),
                            company=job.get("company", ""),
                            url=job.get("url", ""),
                            location=job.get("location", ""),
                            cover_letter_path=cl_path,
                        )
                except Exception as exc:
                    console.print(f"[red]Error applying to {job.get('job_title')} @ {job.get('company')}: {exc}[/red]")
                    continue

                await self.delay(2.0, 5.0)

        finally:
            await page.close()
            await self.teardown()

        console.print(f"[bold green]{self.platform_name}: Applied to {self.applied_count} jobs[/bold green]")
        return self.applied_count
