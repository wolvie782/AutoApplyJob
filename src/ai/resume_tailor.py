"""
Analyzes a job description against the candidate's resume and returns:
- Which skills from the JD match the candidate's background
- Suggested emphasis points for the application
- Whether the candidate is a good fit (to decide if we should apply)
"""

from .client import complete

FIT_PROMPT = """You are evaluating whether Monu Mahto should apply for this job.

Monu's profile:
- 4+ years Full Stack Engineer (Node.js, NestJS, TypeScript, React)
- Specialties: backend systems, event-driven architecture, BullMQ/Kafka queues, Redis, MongoDB/PostgreSQL
- Cloud: AWS (Lambda, S3, Step Functions), GCP (GKE, Cloud Functions), Docker, Kubernetes
- AI/LLM: Claude Code, OpenAI Codex, LLM integration, agentic workflows
- Target roles: SDE2, SDE3, Senior Software Engineer, Senior Backend/Full Stack
- Experience range matching: 3-6 years required is ideal

Job:
Title: {job_title}
Company: {company}
Description: {job_description}

Respond in this exact JSON format:
{{
  "should_apply": true or false,
  "fit_score": 1-10,
  "matching_skills": ["skill1", "skill2"],
  "missing_skills": ["skill1"],
  "emphasis_points": ["what to highlight in cover letter"],
  "reason": "one sentence why apply or skip"
}}

Apply if fit_score >= 6. Skip if the job requires >8 years, is for a manager/director role, is clearly frontend-only with no backend, or is for Java/.NET/Go with no JS/TS."""

TAILOR_PROMPT = """Based on this job description, identify the 3-4 most relevant things from Monu Mahto's background to emphasize.

Monu's key achievements:
1. Built WhatsApp campaign system processing 1M+ messages — BullMQ, Redis batching, idempotency
2. HRMS automation saving ₹1 Cr/year — Kafka pub-sub, Zoho/Oracle integrations
3. Redis-backed search boosting performance 50% on GCP with Kubernetes
4. AI agentic workflows with Claude Code and OpenAI Codex
5. Policy workflow engine — 30% customer satisfaction increase, 20% processing time reduction
6. OTP-based 2FA — 60% login time reduction
7. PDF preview feature — 25% productivity boost, 40% faster verification
8. Graph View with React Flow for schema/workflow visualization

Job description:
{job_description}

Return a JSON list of 3-4 bullet points (plain text, no em-dashes) that best match this specific job.
Format: {{"emphasis": ["bullet1", "bullet2", "bullet3"]}}"""


async def assess_fit(
    job_title: str,
    company: str,
    job_description: str,
    client,
    model: str,
) -> dict:
    import json

    prompt = FIT_PROMPT.format(
        job_title=job_title,
        company=company,
        job_description=job_description[:2500],
    )

    text = await complete(client=client, model=model, system="", user=prompt, max_tokens=400)
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return {"should_apply": True, "fit_score": 7, "reason": "parse error - applying anyway"}


async def get_emphasis_points(
    job_description: str,
    client,
    model: str,
) -> list[str]:
    import json

    prompt = TAILOR_PROMPT.format(job_description=job_description[:2500])
    text = await complete(client=client, model=model, system="", user=prompt, max_tokens=300)
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        data = json.loads(text[start:end])
        return data.get("emphasis", [])
    except Exception:
        return []
