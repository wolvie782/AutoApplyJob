# AutoApplyJob

Auto-applies to jobs on LinkedIn, Instahyre, Indeed, JobRight, and Uplers using your existing logged-in Chrome session.
Tailors a cover letter per job using Claude AI. Tracks every application in a local database. Includes a live dashboard.

## Features

- Connects to your existing Chrome (no login code, no 2FA handling)
- AI cover letters tailored per job description via Claude API
- Humanization layer — cover letters don't read like AI output
- AI fit scoring — skips jobs you're clearly not a match for
- Location priority: Remote → Pune/Mumbai → Hyderabad → Bangalore
- SQLite tracker prevents re-applying to the same job
- Smart Q&A bank auto-fills common form fields (CTC, notice period, etc.)
- Web dashboard at `localhost:8000` showing all applications and stats
- Fully automated — run once, no intervention needed

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure credentials

```bash
cp .env.example .env
```

Edit `.env` and add your Anthropic API key:
```
ANTHROPIC_API_KEY=sk-ant-xxxxx
```

### 3. Configure job preferences

Edit `config/config.yaml` — fill in any blank fields:
- `profile.linkedin_url`, `profile.github_url`
- `experience.current_company`, `experience.current_designation`
- `education.college`

The important ones (CTC, experience, location priority) are already set.

### 4. Add your resume

Your resume is already copied to `resume/resume.pdf`.

### 5. Launch Chrome with remote debugging

Run this **once** and keep Chrome open:

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/.config/chrome-autoapply"
```

Then log in to LinkedIn, Instahyre, Indeed, JobRight, and Uplers in that window.

## Usage

### Start applying

```bash
# Apply on all platforms
python -m src.main start

# Apply only on LinkedIn + Indeed
python -m src.main start -p linkedin -p indeed

# Apply with a custom max limit
python -m src.main start --max 50
```

### Open dashboard

```bash
python -m src.main dashboard
# Then open http://localhost:8000
```

### Check stats in terminal

```bash
python -m src.main stats
```

### Test a platform login

```bash
python -m src.main test-login -p linkedin
```

## How it works

1. Connects to your running Chrome via Chrome DevTools Protocol (CDP)
2. For each platform, searches jobs matching your keywords + location priority
3. For each job, checks the SQLite DB — skips if already applied
4. If AI is enabled, scores job fit (skips if score < 6/10)
5. Generates a tailored, humanized cover letter via Claude API
6. Fills out the application form using the Q&A bank
7. Records the application in the database
8. You can view all applications on the dashboard

## Common form questions (pre-configured)

| Question | Answer |
|---|---|
| Total years of experience | 4 |
| Current CTC | 16 LPA |
| Expected CTC | 35 LPA |
| Notice period | 30 days |
| Current company | Fynd (Reliance Retail) |
| Current designation | Software Development Engineer I |
| Gender | Male |
| Nationality | Indian |
| Work authorization | Yes |
| Willing to relocate | Yes |

## Project structure

```
AutoApplyJob/
├── config/config.yaml       — job preferences, profile
├── src/
│   ├── main.py              — CLI
│   ├── tracker.py           — SQLite application tracker
│   ├── qa_bank.py           — form Q&A auto-fill
│   ├── ai/
│   │   ├── humanizer.py     — humanization skill
│   │   ├── cover_letter.py  — per-job cover letter generator
│   │   └── resume_tailor.py — job fit scorer
│   ├── bots/
│   │   ├── base_bot.py      — Chrome CDP connection + base logic
│   │   ├── linkedin.py      — LinkedIn Easy Apply
│   │   ├── instahyre.py     — Instahyre one-click apply
│   │   ├── indeed.py        — Indeed Easy Apply
│   │   ├── jobright.py      — JobRight apply
│   │   └── uplers.py        — Uplers apply
│   └── dashboard/
│       ├── app.py           — FastAPI server
│       └── templates/       — Dashboard HTML
├── resume/resume.pdf        — your resume
├── cover_letters/           — AI-generated cover letters (saved per job)
└── data/applications.db     — all application records
```

## Notes

- Keep the Chrome window open while the bot runs — it uses your existing session
- Cover letters are saved in `cover_letters/` so you can review them
- The bot runs one platform at a time, sequentially
- If a platform's apply flow changes (UI update), the selectors in the bot file may need updating
- This tool is for personal use — use responsibly and in accordance with each platform's terms of service
