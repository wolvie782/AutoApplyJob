"""
Indeed Easy Apply bot.
"""

import re
import hashlib
from playwright.async_api import Page
from rich.console import Console

from .base_bot import BaseBot
from ..qa_bank import get_answer, get_boolean_answer

console = Console()


def _job_id_from_url(url: str) -> str:
    m = re.search(r"jk=([a-f0-9]+)", url)
    if m:
        return m.group(1)
    return hashlib.md5(url.encode()).hexdigest()[:16]


class IndeedBot(BaseBot):
    platform_name = "indeed"
    BASE_URL = "https://in.indeed.com"

    async def search_jobs(self, page: Page) -> list[dict]:
        jobs = []
        keywords = self.job_search.get("keywords", ["Senior Software Engineer"])
        locations = self.job_search.get("location_priority", ["Remote", "Mumbai"])

        for keyword in keywords[:2]:
            for location in locations[:3]:
                url = (
                    f"{self.BASE_URL}/jobs"
                    f"?q={keyword.replace(' ', '+')}"
                    f"&l={location.replace(' ', '+')}"
                    f"&fromage=7"
                    f"&iafilter=1"
                )
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
            await page.wait_for_selector(".job_seen_beacon, .jobsearch-ResultsList li", timeout=8000)
        except Exception:
            return jobs

        cards = await page.query_selector_all(".job_seen_beacon, [data-jk]")
        for card in cards[:20]:
            try:
                title_el = await card.query_selector("h2 a span, .jcs-JobTitle span")
                company_el = await card.query_selector("[data-testid='company-name'], .companyName")
                location_el = await card.query_selector("[data-testid='text-location'], .companyLocation")
                link_el = await card.query_selector("h2 a")

                if not title_el or not link_el:
                    continue

                title = (await title_el.inner_text()).strip()
                company = (await company_el.inner_text()).strip() if company_el else ""
                location = (await location_el.inner_text()).strip() if location_el else ""
                href = await link_el.get_attribute("href")
                job_url = self.BASE_URL + href if href.startswith("/") else href
                job_id = _job_id_from_url(job_url)

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
        await page.goto(job["url"], wait_until="domcontentloaded")
        await self.delay(2, 3)

        try:
            desc_el = await page.query_selector("#jobDescriptionText, .jobsearch-jobDescriptionText")
            job["description"] = (await desc_el.inner_text()).strip()[:3000] if desc_el else ""
        except Exception:
            pass

        # Check for Easy Apply button
        apply_btn = await page.query_selector(
            "button[id*='indeedApplyButton'], .ia-IndeedApplyButton, button:has-text('Easily apply')"
        )
        if not apply_btn:
            return False

        cover_letter = ""
        if self.ai_client and job.get("description"):
            cover_letter = await self.generate_cover_letter_for_job(
                job["job_title"], job["company"], job["location"], job["description"]
            )

        await apply_btn.click()
        await self.delay(2, 4)

        # Indeed opens a new page/popup for apply
        pages = self.context.pages
        apply_page = pages[-1] if len(pages) > 1 else page
        return await self._handle_apply_flow(apply_page, job, cover_letter)

    async def _handle_apply_flow(self, page: Page, job: dict, cover_letter: str) -> bool:
        for step in range(10):
            await self.delay(1, 2)

            # Success check
            if await page.query_selector(".ia-BasePage-heading:has-text('Application submitted'), .ia-JobActionConfirmationHeader"):
                return True

            # Fill all visible form fields
            await self._fill_step(page, cover_letter)

            # Continue / Next
            cont = await page.query_selector("button[data-testid='IndeedApplyButton'], button:has-text('Continue'), button:has-text('Next')")
            if cont:
                await cont.click()
            else:
                submit = await page.query_selector("button:has-text('Submit'), button[type='submit']")
                if submit:
                    await submit.click()
                    await self.delay(2, 3)
                    return True
                break

        return False

    async def _fill_step(self, page: Page, cover_letter: str):
        # Resume upload if needed
        resume_input = await page.query_selector("input[type='file'][accept*='pdf'], input[type='file']")
        if resume_input and self.resume_path.exists():
            await resume_input.set_input_files(str(self.resume_path))
            await self.delay(1, 2)

        # Cover letter
        if cover_letter:
            cl_area = await page.query_selector("textarea[id*='cover'], textarea[name*='cover'], textarea[placeholder*='cover']")
            if cl_area:
                await cl_area.fill(cover_letter)

        # Text inputs via label matching
        labels = await page.query_selector_all("label[for]")
        for label in labels:
            try:
                label_text = (await label.inner_text()).strip()
                label_for = await label.get_attribute("for")
                answer = get_answer(label_text, self.config)
                if not answer:
                    continue
                el = await page.query_selector(f"#{label_for}")
                if el:
                    tag = await el.evaluate("e => e.tagName.toLowerCase()")
                    if tag == "input":
                        await el.fill(answer)
                    elif tag == "select":
                        await el.select_option(label=answer)
                    elif tag == "textarea":
                        await el.fill(answer)
            except Exception:
                continue
