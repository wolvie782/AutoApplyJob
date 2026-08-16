"""
JobRight.ai bot.
"""

import hashlib
from playwright.async_api import Page
from rich.console import Console

from .base_bot import BaseBot
from ..qa_bank import get_answer

console = Console()


class JobRightBot(BaseBot):
    platform_name = "jobright"
    BASE_URL = "https://jobright.ai"

    async def search_jobs(self, page: Page) -> list[dict]:
        jobs = []
        keywords = self.job_search.get("keywords", ["Senior Software Engineer"])

        for keyword in keywords[:2]:
            url = f"{self.BASE_URL}/jobs?q={keyword.replace(' ', '%20')}&country=India"
            await page.goto(url, wait_until="domcontentloaded")
            await self.delay(2, 4)
            jobs.extend(await self._collect_jobs(page))

        seen = set()
        unique = []
        for j in jobs:
            if j["job_id"] not in seen:
                seen.add(j["job_id"])
                unique.append(j)
        return unique

    async def _collect_jobs(self, page: Page) -> list[dict]:
        jobs = []
        try:
            await page.wait_for_selector("[data-job-id], .job-card, .job-listing", timeout=8000)
        except Exception:
            return jobs

        cards = await page.query_selector_all("[data-job-id], .job-card, .job-listing")
        for card in cards[:20]:
            try:
                title_el = await card.query_selector(".job-title, h2, h3, [class*='title']")
                company_el = await card.query_selector(".company, [class*='company']")
                location_el = await card.query_selector(".location, [class*='location']")
                link_el = await card.query_selector("a[href*='/job']")

                if not title_el:
                    continue

                title = (await title_el.inner_text()).strip()
                company = (await company_el.inner_text()).strip() if company_el else ""
                location = (await location_el.inner_text()).strip() if location_el else ""
                href = await link_el.get_attribute("href") if link_el else ""
                job_url = self.BASE_URL + href if href and href.startswith("/") else href

                job_id_attr = await card.get_attribute("data-job-id")
                job_id = job_id_attr or hashlib.md5((title + company).encode()).hexdigest()[:16]

                jobs.append({
                    "job_id": job_id,
                    "job_title": title,
                    "company": company,
                    "location": location,
                    "url": job_url,
                    "description": "",
                })
            except Exception:
                continue

        return jobs

    async def apply_to_job(self, page: Page, job: dict) -> bool:
        if job["url"]:
            await page.goto(job["url"], wait_until="domcontentloaded")
            await self.delay(2, 3)

        try:
            desc_el = await page.query_selector(".job-description, [class*='description']")
            job["description"] = (await desc_el.inner_text()).strip()[:3000] if desc_el else ""
        except Exception:
            pass

        apply_btn = await page.query_selector(
            "button:has-text('Apply'), button:has-text('Easy Apply'), a:has-text('Apply Now')"
        )
        if not apply_btn:
            return False

        await apply_btn.click()
        await self.delay(1.5, 3)

        # Fill any form that appears
        form = await page.query_selector("form, .apply-form, [class*='application']")
        if form:
            await self._fill_form(page)
            submit = await page.query_selector("button[type='submit'], button:has-text('Submit'), button:has-text('Apply')")
            if submit:
                await submit.click()
                await self.delay(2, 3)
                return True

        # Check success
        success = await page.query_selector(":has-text('Application submitted'), :has-text('Successfully applied')")
        return success is not None

    async def _fill_form(self, page: Page):
        fields = {
            "input[name*='phone']": self.profile["phone"],
            "input[name*='name']": self.profile["name"],
            "input[name*='email']": self.profile["email"],
            "input[name*='linkedin']": self.profile["linkedin_url"],
            "input[name*='github']": self.profile["github_url"],
            "input[name*='experience']": str(self.experience["years"]),
            "input[name*='current_ctc'], input[name*='currentCTC']": self.experience["current_ctc"],
            "input[name*='expected_ctc'], input[name*='expectedCTC']": self.experience["expected_ctc"],
            "input[name*='notice']": self.experience["notice_period"],
        }
        for selector, value in fields.items():
            try:
                el = await page.query_selector(selector)
                if el and not await el.input_value():
                    await el.fill(value)
            except Exception:
                continue

        resume_input = await page.query_selector("input[type='file']")
        if resume_input and self.resume_path.exists():
            await resume_input.set_input_files(str(self.resume_path))
            await self.delay(1, 2)
