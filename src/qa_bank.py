"""
Common job application form questions and their answers.
The bot matches form field labels against these patterns and fills them automatically.
"""
import re


def get_answer(question: str, config: dict) -> str | None:
    """
    Match a form question label to the right answer from config.
    Returns None if no confident match found.
    """
    q = question.lower().strip()
    p = config.get("profile", {})
    e = config.get("experience", {})
    edu = config.get("education", {})
    prefs = config.get("work_preferences", {})

    # --- Personal info ---
    if _match(q, ["full name", "your name", "candidate name", "name *"]):
        return p.get("name", "")

    if _match(q, ["email", "e-mail", "email address"]):
        return p.get("email", "")

    if _match(q, ["phone", "mobile", "contact number", "phone number"]):
        return p.get("phone", "")

    if _match(q, ["phone with country", "phone (with country", "country code"]):
        return p.get("phone_with_code", "")

    if _match(q, ["gender"]):
        return p.get("gender", "Male")

    if _match(q, ["nationality", "citizenship"]):
        return p.get("nationality", "Indian")

    if _match(q, ["current location", "current city", "city", "where are you"]):
        return p.get("location", "India")

    if _match(q, ["linkedin", "linkedin url", "linkedin profile"]):
        return p.get("linkedin_url", "")

    if _match(q, ["github", "github url", "github profile"]):
        return p.get("github_url", "")

    if _match(q, ["portfolio", "website", "personal website"]):
        return p.get("portfolio_url", "")

    # --- Experience ---
    if _match(q, ["total years", "total experience", "how many years of experience",
                   "years of experience", "years of work experience", "overall experience"]):
        return str(e.get("years", "4"))

    if _match(q, ["current ctc", "current salary", "current package", "current annual",
                   "present ctc", "present salary", "existing ctc"]):
        return e.get("current_ctc", "16 LPA")

    if _match(q, ["expected ctc", "expected salary", "expected package", "expected annual",
                   "desired salary", "salary expectation", "what salary are you"]):
        return e.get("expected_ctc", "35 LPA")

    if _match(q, ["notice period", "notice", "when can you join", "joining period",
                   "how soon can you", "availability to join", "start date"]):
        return e.get("notice_period", "30 days")

    if _match(q, ["current company", "present company", "employer", "current employer",
                   "where do you work", "current organization"]):
        return e.get("current_company", "")

    if _match(q, ["current designation", "current role", "current title", "job title",
                   "current position"]):
        return e.get("current_designation", "Software Engineer")

    # --- Education ---
    if _match(q, ["highest qualification", "education", "degree", "highest degree"]):
        return edu.get("degree", "B.E. / B.Tech")

    if _match(q, ["field of study", "branch", "specialization", "major"]):
        return edu.get("field", "Computer Science")

    if _match(q, ["college", "university", "institution", "school name"]):
        return edu.get("college", "")

    if _match(q, ["graduation year", "year of graduation", "passed out", "batch"]):
        return str(edu.get("graduation_year", "2020"))

    # --- Work preferences / authorizations ---
    if _match(q, ["work authorization", "authorized to work", "eligible to work",
                   "right to work", "work permit"]):
        return "Yes" if prefs.get("work_authorization", True) else "No"

    if _match(q, ["willing to relocate", "open to relocation", "relocation"]):
        return "Yes" if prefs.get("willing_to_relocate", True) else "No"

    if _match(q, ["currently employed", "are you currently", "do you have a job",
                   "employed", "working currently"]):
        return "Yes" if e.get("currently_employed", True) else "No"

    if _match(q, ["visa sponsorship", "require sponsorship", "need visa"]):
        return "No" if not prefs.get("visa_sponsorship_required", False) else "Yes"

    if _match(q, ["prefer remote", "work from home", "remote work"]):
        return "Yes" if prefs.get("prefer_remote", True) else "No"

    if _match(q, ["hybrid", "open to hybrid"]):
        return "Yes" if prefs.get("open_to_hybrid", True) else "No"

    # --- Common yes/no ---
    if _match(q, ["are you indian", "indian citizen", "citizen of india"]):
        return "Yes"

    if _match(q, ["how did you hear", "source", "referred by", "referral"]):
        return "LinkedIn"

    return None


def get_boolean_answer(question: str, config: dict) -> bool | None:
    """Return True/False for yes-no questions, or None if unknown."""
    answer = get_answer(question, config)
    if answer is None:
        return None
    return answer.lower() in ("yes", "true", "1")


def _match(question: str, patterns: list[str]) -> bool:
    for p in patterns:
        if p in question:
            return True
    return False


# Full list of questions that may appear on application forms
# This is a reference list — the bot uses get_answer() at runtime
COMMON_QUESTIONS = [
    # Personal
    "Full Name",
    "Email Address",
    "Phone Number",
    "Phone Number (with country code)",
    "Gender",
    "Nationality / Citizenship",
    "Current Location / City",
    "LinkedIn Profile URL",
    "GitHub Profile URL",
    "Portfolio / Website URL",

    # Experience
    "Total Years of Experience",
    "Years of Experience in [Technology]",
    "Current CTC (Annual)",
    "Expected CTC (Annual)",
    "Notice Period / Availability to Join",
    "Current Company / Employer",
    "Current Designation / Job Title",

    # Education
    "Highest Qualification / Degree",
    "Field of Study / Branch",
    "College / University Name",
    "Year of Graduation",

    # Work Preferences
    "Are you authorized to work in India?",
    "Are you currently employed?",
    "Are you willing to relocate?",
    "Do you require visa sponsorship?",
    "Are you open to remote work?",
    "Are you open to hybrid work?",
    "When can you join? (Notice Period)",

    # Optional / EEO
    "How did you hear about this position?",
    "Are you an Indian citizen?",
    "Do you have any disability?",
    "Are you a veteran?",
]
