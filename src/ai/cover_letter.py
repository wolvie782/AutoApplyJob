"""
Generates a tailored, human-sounding cover letter for each job using the
candidate's resume + the job description.
"""

from .client import complete
from .humanizer import humanize, post_process

COVER_LETTER_PROMPT = """You are writing a cover letter for Monu Mahto, a Full Stack Engineer with 4+ years of experience.

Candidate background:
- Current role: Software Development Engineer I at Fynd (Reliance Retail), working on Boltic (workflow automation, 300+ enterprise customers)
- Key achievements: Built WhatsApp campaign system handling 1M+ messages, HRMS automation saving ₹1 Cr/year, 40-50% performance gains
- Stack: Node.js, NestJS, TypeScript, React, BullMQ, Kafka, Redis, MongoDB, PostgreSQL, AWS, GCP, Docker, Kubernetes
- AI experience: Claude Code, OpenAI Codex, LLM integration, agentic workflows
- Education: B.E. IT, St. John College of Engineering & Management, Mumbai, 2022
- LinkedIn: https://linkedin.com/in/monu-mahto | GitHub: https://github.com/wolvie782

Job to apply for:
Title: {job_title}
Company: {company}
Location: {location}
Description:
{job_description}

Write a cover letter that:
1. Opens with a specific reason why this role at this company appeals to Monu — reference something real from the job description
2. Highlights 2-3 achievements from his background that directly match what this job needs
3. Shows genuine understanding of what the company does (from the JD)
4. Ends with a clear, confident close — not a begging tone
5. Stays under 220 words
6. Reads like a real person wrote it — not like a template

Critical rules:
- NO em-dashes (—)
- NO: "I am excited/thrilled/passionate/eager to..."
- NO: "leverage", "utilize", "synergy", "cutting-edge", "Furthermore", "Moreover"
- USE contractions: I've, I'm, I'd, I'll
- START with something other than "I"
- Be specific — mention actual tech, actual numbers from his resume
- Professional but direct tone

Return only the cover letter text. No subject line. No "Dear Hiring Manager" needed (the platform adds it)."""


async def generate_cover_letter(
    job_title: str,
    company: str,
    location: str,
    job_description: str,
    config: dict,
    client,
    model: str,
) -> str:
    prompt = COVER_LETTER_PROMPT.format(
        job_title=job_title,
        company=company,
        location=location,
        job_description=job_description[:3000],
    )

    raw = await complete(
        client=client,
        model=model,
        system="",
        user=prompt,
        max_tokens=600,
    )

    if config.get("ai", {}).get("humanize", True):
        return await humanize(raw, client, model)
    return post_process(raw)
