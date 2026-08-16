"""
Instahyre bot — profile-based apply.
Most Instahyre applications use your saved profile, so it's mostly one-click.
"""

import hashlib
from playwright.async_api import Page
from rich.console import Console

from .base_bot import BaseBot
from ..qa_bank import get_answer

console = Console()


class InstahyreBot(BaseBot):
    platform_name = "instahyre"
    BASE_URL = "https://www.instahyre.com"

    async def search_jobs(self, page: Page) -> list[dict]:
        jobs = []
        keywords = self.job_search.get("keywords", ["Senior Software Engineer"])

        for keyword in keywords[:2]:
            url = f"{self.BASE_URL}/jobs/?q={keyword.replace(' ', '+')}&location=India&experience=4-8"
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
            await page.wait_for_selector(".job-item, .job-card, [data-job-id]", timeout=8000)
        except Exception:
            return jobs

        cards = await page.query_selector_all(".job-item, .job-card, [data-job-id]")
        for card in cards[:20]:
            try:
                title_el = await card.query_selector(".job-title, h2, h3")
                company_el = await card.query_selector(".company-name, .employer-name")
                location_el = await card.query_selector(".location, .job-location")
                link_el = await card.query_selector("a[href*='/jobs/']")

                if not title_el:
                    continue

                title = (await title_el.inner_text()).strip()
                company = (await company_el.inner_text()).strip() if company_el else ""
                location = (await location_el.inner_text()).strip() if location_el else "India"
                href = await link_el.get_attribute("href") if link_el else ""
                job_url = self.BASE_URL + href if href.startswith("/") else href

                job_id_attr = await card.get_attribute("data-job-id")
                job_id = job_id_attr or hashlib.md5(job_url.encode()).hexdigest()[:16]

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
            desc_el = await page.query_selector(".job-description, .jd-content")
            job["description"] = (await desc_el.inner_text()).strip()[:3000] if desc_el else ""
        except Exception:
            pass

        # Try one-click apply first
        apply_btn = await page.query_selector("button:has-text('Apply'), a:has-text('Apply Now'), .apply-btn")
        if not apply_btn:
            return False

        await apply_btn.click()
        await self.delay(1.5, 3)

        # If a form appears, fill it
        form = await page.query_selector("form.application-form, .apply-modal form")
        if form:
            await self._fill_application_form(page)
            submit = await page.query_selector("button[type='submit'], button:has-text('Submit')")
            if submit:
                await submit.click()
                await self.delay(2, 3)

        # Check for success
        success_el = await page.query_selector(".success-message, .application-submitted, :has-text('Application submitted')")
        return success_el is not None

    async def _fill_application_form(self, page: Page):
        fields = {
            "input[name*='phone'], input[placeholder*='phone']": self.profile["phone"],
            "input[name*='name'], input[placeholder*='name']": self.profile["name"],
            "input[name*='email'], input[placeholder*='email']": self.profile["email"],
            "input[name*='experience'], input[placeholder*='experience']": str(self.experience["years"]),
            "input[name*='ctc'], input[placeholder*='current ctc']": self.experience["current_ctc"],
            "input[name*='expected'], input[placeholder*='expected']": self.experience["expected_ctc"],
            "input[name*='notice'], input[placeholder*='notice']": self.experience["notice_period"],
        }

        for selector, value in fields.items():
            try:
                el = await page.query_selector(selector)
                if el:
                    current = await el.input_value()
                    if not current:
                        await el.fill(value)
            except Exception:
                continue

        # Cover letter / message
        cl_area = await page.query_selector("textarea[name*='cover'], textarea[placeholder*='message']")
        if cl_area and self.ai_client:
            cover = await self.generate_cover_letter_for_job(
                "Software Engineer", "Company", "India", ""
            )
            await cl_area.fill(cover)
