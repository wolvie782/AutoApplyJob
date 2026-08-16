"""
LinkedIn Easy Apply bot.
Navigates to LinkedIn Jobs, filters by Easy Apply + your keywords/locations,
and handles the multi-step Easy Apply modal automatically.
"""

import re
import hashlib
from playwright.async_api import Page
from rich.console import Console

from .base_bot import BaseBot
from ..qa_bank import get_answer, get_boolean_answer

console = Console()


def _job_id_from_url(url: str) -> str:
    m = re.search(r"/jobs/view/(\d+)", url)
    if m:
        return m.group(1)
    return hashlib.md5(url.encode()).hexdigest()[:16]


class LinkedInBot(BaseBot):
    platform_name = "linkedin"

    async def search_jobs(self, page: Page) -> list[dict]:
        jobs = []
        keywords = self.job_search.get("keywords", ["Senior Software Engineer"])
        locations = self.job_search.get("location_priority", ["Remote", "Mumbai"])

        for keyword in keywords[:2]:  # limit to 2 keywords to avoid spam
            for location in locations[:3]:
                url = (
                    f"https://www.linkedin.com/jobs/search/"
                    f"?keywords={keyword.replace(' ', '%20')}"
                    f"&location={location.replace(' ', '%20')}"
                    f"&f_AL=true"   # Easy Apply filter
                    f"&f_TPR=r604800"  # Past week
                    f"&sortBy=DD"
                )
                await page.goto(url, wait_until="domcontentloaded")
                await self.delay(2, 4)

                jobs.extend(await self._collect_jobs_from_list(page))

                if len(jobs) >= 60:
                    break

        # Deduplicate by job_id
        seen = set()
        unique = []
        for j in jobs:
            if j["job_id"] not in seen:
                seen.add(j["job_id"])
                unique.append(j)
        return unique

    async def _collect_jobs_from_list(self, page: Page) -> list[dict]:
        jobs = []
        try:
            await page.wait_for_selector(".jobs-search__results-list, .scaffold-layout__list", timeout=8000)
        except Exception:
            return jobs

        # Scroll to load more
        for _ in range(3):
            await page.evaluate("window.scrollBy(0, 800)")
            await self.delay(0.8, 1.5)

        cards = await page.query_selector_all(".job-card-container, .jobs-search-results__list-item")
        for card in cards[:20]:
            try:
                title_el = await card.query_selector(".job-card-list__title, .job-card-container__link")
                company_el = await card.query_selector(".job-card-container__company-name, .artdeco-entity-lockup__subtitle")
                location_el = await card.query_selector(".job-card-container__metadata-item, .job-card-container__metadata-wrapper li")
                link_el = await card.query_selector("a[href*='/jobs/view/']")

                if not title_el or not link_el:
                    continue

                title = (await title_el.inner_text()).strip()
                company = (await company_el.inner_text()).strip() if company_el else ""
                location = (await location_el.inner_text()).strip() if location_el else ""
                href = await link_el.get_attribute("href")
                job_url = "https://www.linkedin.com" + href if href.startswith("/") else href
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
        await self.delay(2, 4)

        # Get job description for cover letter / fit check
        try:
            desc_el = await page.query_selector(".jobs-description__content, .job-view-layout")
            job["description"] = (await desc_el.inner_text()).strip()[:3000] if desc_el else ""
        except Exception:
            job["description"] = ""

        # Click Easy Apply button
        easy_apply_btn = await page.query_selector("button.jobs-apply-button[aria-label*='Easy Apply'], .jobs-apply-button--top-card button")
        if not easy_apply_btn:
            return False

        await easy_apply_btn.click()
        await self.delay(1.5, 3)

        # Generate cover letter if AI available
        cover_letter = ""
        if self.ai_client and job.get("description"):
            cover_letter = await self.generate_cover_letter_for_job(
                job["job_title"], job["company"], job["location"], job["description"]
            )

        # Handle multi-step modal
        return await self._handle_easy_apply_modal(page, job, cover_letter)

    async def _handle_easy_apply_modal(self, page: Page, job: dict, cover_letter: str) -> bool:
        max_steps = 8
        for step in range(max_steps):
            await self.delay(1, 2)

            # Check for submit button
            submit_btn = await page.query_selector("button[aria-label='Submit application'], button[aria-label*='Submit']")
            if submit_btn:
                await submit_btn.click()
                await self.delay(2, 3)
                return True

            # Check for "Review" button (last step before submit)
            review_btn = await page.query_selector("button[aria-label='Review your application']")
            if review_btn:
                await review_btn.click()
                continue

            # Fill current step fields
            await self._fill_modal_fields(page, cover_letter)

            # Click Next
            next_btn = await page.query_selector("button[aria-label='Continue to next step'], button[aria-label*='Next']")
            if not next_btn:
                # Try generic next
                next_btn = await page.query_selector(".jobs-easy-apply-modal__action-bar button[data-easy-apply-next-button]")
            if next_btn:
                await next_btn.click()
            else:
                break

        # Dismiss if not submitted
        dismiss = await page.query_selector("button[aria-label='Dismiss']")
        if dismiss:
            await dismiss.click()
            await self.delay(0.5, 1)
            discard = await page.query_selector("button[data-control-name='discard_application_confirm_btn']")
            if discard:
                await discard.click()
        return False

    async def _fill_modal_fields(self, page: Page, cover_letter: str):
        # Phone number
        phone_input = await page.query_selector("input[id*='phoneNumber'], input[name*='phone']")
        if phone_input:
            val = await phone_input.input_value()
            if not val:
                await self.safe_fill(page, "input[id*='phoneNumber']", self.profile["phone"])

        # Cover letter textarea
        if cover_letter:
            cl_area = await page.query_selector("textarea[id*='coverLetter'], textarea[name*='cover']")
            if cl_area:
                await cl_area.fill(cover_letter)

        # Generic text inputs — match label to Q&A bank
        labels = await page.query_selector_all("label")
        for label in labels:
            try:
                label_text = (await label.inner_text()).strip()
                label_for = await label.get_attribute("for")
                if not label_for:
                    continue

                answer = get_answer(label_text, self.config)
                if not answer:
                    continue

                input_el = await page.query_selector(f"#{label_for}")
                if not input_el:
                    continue

                tag = await input_el.evaluate("el => el.tagName.toLowerCase()")
                input_type = await input_el.get_attribute("type") or "text"

                if tag == "input" and input_type in ("text", "number", "tel", "email"):
                    current = await input_el.input_value()
                    if not current:
                        await input_el.fill(answer)
                elif tag == "select":
                    await input_el.select_option(label=answer)
                elif tag == "textarea":
                    current = await input_el.input_value()
                    if not current:
                        await input_el.fill(answer)
            except Exception:
                continue

        # Yes/No radio buttons
        radios = await page.query_selector_all("fieldset")
        for fieldset in radios:
            try:
                legend = await fieldset.query_selector("legend span, legend")
                if not legend:
                    continue
                question = (await legend.inner_text()).strip()
                answer = get_boolean_answer(question, self.config)
                if answer is None:
                    continue
                value = "Yes" if answer else "No"
                radio = await fieldset.query_selector(f"input[type='radio'][value='{value}']")
                if not radio:
                    radio = await fieldset.query_selector(f"label:has-text('{value}') input")
                if radio:
                    await radio.click()
            except Exception:
                continue
