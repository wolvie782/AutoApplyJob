"""
Uplers bot.
"""

import hashlib
from playwright.async_api import Page
from rich.console import Console

from .base_bot import BaseBot

console = Console()


class UplerBot(BaseBot):
    platform_name = "uplers"
    BASE_URL = "https://www.uplers.com"

    async def search_jobs(self, page: Page) -> list[dict]:
        jobs = []
        keywords = self.job_search.get("keywords", ["Senior Software Engineer"])

        for keyword in keywords[:2]:
            url = f"{self.BASE_URL}/it-jobs/?s={keyword.replace(' ', '+')}"
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
            await page.wait_for_selector(".job-listing, .job-post, article", timeout=8000)
        except Exception:
            return jobs

        cards = await page.query_selector_all(".job-listing, .job-post, .jobs-listing article")
        for card in cards[:20]:
            try:
                title_el = await card.query_selector("h2, h3, .job-title")
                company_el = await card.query_selector(".company, .client-name")
                location_el = await card.query_selector(".location, .job-location")
                link_el = await card.query_selector("a")

                if not title_el:
                    continue

                title = (await title_el.inner_text()).strip()
                company = (await company_el.inner_text()).strip() if company_el else "Uplers Client"
                location = (await location_el.inner_text()).strip() if location_el else "Remote"
                href = await link_el.get_attribute("href") if link_el else ""
                job_url = self.BASE_URL + href if href and href.startswith("/") else href

                job_id = hashlib.md5((title + company).encode()).hexdigest()[:16]

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
            desc_el = await page.query_selector(".job-description, .entry-content")
            job["description"] = (await desc_el.inner_text()).strip()[:3000] if desc_el else ""
        except Exception:
            pass

        apply_btn = await page.query_selector(
            "a:has-text('Apply'), button:has-text('Apply'), .apply-btn"
        )
        if not apply_btn:
            return False

        await apply_btn.click()
        await self.delay(1.5, 3)

        form = await page.query_selector("form, .application-form")
        if form:
            await self._fill_application_form(page, job)
            submit = await page.query_selector("button[type='submit'], input[type='submit'], button:has-text('Submit')")
            if submit:
                await submit.click()
                await self.delay(2, 3)
                return True

        success = await page.query_selector(":has-text('Application received'), :has-text('Thank you for applying')")
        return success is not None

    async def _fill_application_form(self, page: Page, job: dict):
        fields = {
            "input[name='full_name'], input[name='name']": self.profile["name"],
            "input[name='email']": self.profile["email"],
            "input[name='phone'], input[name='mobile']": self.profile["phone"],
            "input[name='linkedin']": self.profile["linkedin_url"],
            "input[name='current_ctc']": self.experience["current_ctc"],
            "input[name='expected_ctc']": self.experience["expected_ctc"],
            "input[name='notice_period']": self.experience["notice_period"],
            "input[name='experience'], input[name='total_experience']": str(self.experience["years"]),
        }
        for selector, value in fields.items():
            try:
                el = await page.query_selector(selector)
                if el and value:
                    current = await el.input_value()
                    if not current:
                        await el.fill(value)
            except Exception:
                continue

        resume_input = await page.query_selector("input[type='file']")
        if resume_input and self.resume_path.exists():
            await resume_input.set_input_files(str(self.resume_path))
            await self.delay(1, 2)

        if self.ai_client and job.get("description"):
            cover = await self.generate_cover_letter_for_job(
                job["job_title"], job["company"], job["location"], job["description"]
            )
            cl_area = await page.query_selector("textarea[name='cover_letter'], textarea[name='message']")
            if cl_area and cover:
                await cl_area.fill(cover)
