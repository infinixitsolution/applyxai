"""Conservative crawl and search budgets for outreach discovery."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.config import settings


@dataclass(frozen=True)
class OutreachScrapeBudgets:
    max_queries_per_job: int = 5
    max_results_per_query: int = 10
    max_pages_per_institute: int = 5
    max_pages_per_job: int = 40
    scrape_timeout_sec: float = 90.0
    max_markdown_chars: int = 24_000
    max_scrape_retries: int = 2
    stale_queued_job_minutes: int = 15


def budgets() -> OutreachScrapeBudgets:
    cap = min(max(settings.OUTREACH_MAX_LEADS_PER_JOB, 1), 50)
    return OutreachScrapeBudgets(
        max_queries_per_job=min(5, max(3, cap // 2)),
        max_results_per_query=min(10, max(3, cap // 2)),
        max_pages_per_institute=5,
        max_pages_per_job=min(40, cap * 4),
    )
