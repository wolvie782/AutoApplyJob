import aiosqlite
import asyncio
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "applications.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                job_id TEXT NOT NULL,
                job_title TEXT,
                company TEXT,
                url TEXT,
                location TEXT,
                status TEXT DEFAULT 'applied',
                cover_letter_path TEXT,
                applied_at TEXT NOT NULL,
                UNIQUE(platform, job_id)
            )
        """)
        await db.commit()


async def is_applied(platform: str, job_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT 1 FROM applications WHERE platform=? AND job_id=?",
            (platform, job_id)
        )
        return await cursor.fetchone() is not None


async def record_application(
    platform: str,
    job_id: str,
    job_title: str,
    company: str,
    url: str,
    location: str = "",
    status: str = "applied",
    cover_letter_path: str = "",
):
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                """INSERT INTO applications
                   (platform, job_id, job_title, company, url, location, status, cover_letter_path, applied_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (platform, job_id, job_title, company, url, location, status,
                 cover_letter_path, datetime.now().isoformat()),
            )
            await db.commit()
        except aiosqlite.IntegrityError:
            pass  # already applied


async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("SELECT COUNT(*) as total FROM applications")
        total = (await cursor.fetchone())["total"]

        cursor = await db.execute(
            "SELECT platform, COUNT(*) as count FROM applications GROUP BY platform"
        )
        by_platform = {row["platform"]: row["count"] for row in await cursor.fetchall()}

        cursor = await db.execute(
            "SELECT DATE(applied_at) as day, COUNT(*) as count FROM applications "
            "GROUP BY day ORDER BY day DESC LIMIT 7"
        )
        by_day = {row["day"]: row["count"] for row in await cursor.fetchall()}

        return {"total": total, "by_platform": by_platform, "by_day": by_day}


async def get_all_applications(limit: int = 200, platform: str = None) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if platform and platform != "all":
            cursor = await db.execute(
                "SELECT * FROM applications WHERE platform=? ORDER BY applied_at DESC LIMIT ?",
                (platform, limit),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM applications ORDER BY applied_at DESC LIMIT ?", (limit,)
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
