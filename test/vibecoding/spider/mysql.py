import os
import sqlite3
from pathlib import Path
from typing import Optional


class MySql:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            env_path = os.getenv("SPIDER_DB_PATH")
            if env_path:
                db_path = env_path
            else:
                repo_root = Path(__file__).resolve().parents[1]
                db_path = str(repo_root / "job-application-agent" / "data" / "processed_jobs" / "jobs.db")

        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._conn = sqlite3.connect(self._db_path)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT,
                category TEXT,
                sub_category TEXT,
                job_title TEXT,
                job_location TEXT,
                job_company TEXT,
                job_scale TEXT,
                job_salary_range TEXT,
                job_education TEXT,
                job_experience TEXT,
                job_industry TEXT,
                job_skills TEXT,
                job_welfare TEXT,
                job_url TEXT,
                jd_text TEXT,
                create_time TEXT,
                UNIQUE(source, sub_category, job_title, job_company, job_location, job_salary_range)
            );
            """
        )
        self._conn.commit()

    def saveData(
        self,
        job_name: str,
        job_place: str,
        job_company: str,
        job_scale: str,
        job_salary: str,
        job_education: str,
        job_experience: str,
        job_label: str,
        job_skill: str,
        job_welfare: str,
        job_type: str,
        job_url: str = "",
        jd_text: str = "",
        create_time: str = "",
    ) -> None:
        self._conn.execute(
            """
            INSERT OR IGNORE INTO job_info(
                source, category, sub_category, job_title, job_location, job_company, job_scale,
                job_salary_range, job_education, job_experience, job_industry, job_skills, job_welfare,
                job_url, jd_text, create_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "spider.bosszp_spider",
                "search",
                job_type,
                job_name,
                job_place,
                job_company,
                job_scale,
                job_salary,
                job_education,
                job_experience,
                job_label,
                job_skill,
                job_welfare,
                job_url,
                jd_text,
                create_time,
            ),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

