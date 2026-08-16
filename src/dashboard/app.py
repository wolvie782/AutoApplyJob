"""
FastAPI dashboard — shows all job applications with stats.
Run: uvicorn src.dashboard.app:app --reload --port 8000
Then open: http://localhost:8000
"""

import asyncio
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..tracker import init_db, get_all_applications, get_stats

app = FastAPI(title="AutoApplyJob Dashboard")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@app.on_event("startup")
async def startup():
    await init_db()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, platform: str = "all"):
    stats = await get_stats()
    applications = await get_all_applications(limit=500, platform=platform)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "stats": stats,
            "applications": applications,
            "selected_platform": platform,
            "platforms": ["all", "linkedin", "instahyre", "indeed", "jobright", "uplers"],
        },
    )


@app.get("/api/stats")
async def api_stats():
    return await get_stats()


@app.get("/api/applications")
async def api_applications(platform: str = "all", limit: int = 200):
    return await get_all_applications(limit=limit, platform=platform)
