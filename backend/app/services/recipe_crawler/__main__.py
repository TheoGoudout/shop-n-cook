"""Run one recipe crawl now: ``python -m app.services.recipe_crawler [--dry-run]``.

Uses the ``RECIPE_CRAWL_*`` limits, but ignores ``RECIPE_CRAWL_HOURS``: this is
how to try the crawler, or top up the catalogue, without turning the schedule on.
"""

from __future__ import annotations

import argparse
import logging
import sys

from sqlmodel import Session

from app.core.config import settings
from app.core.db import engine
from app.services.recipe_crawler.crawler import CrawlReport, crawl, run_crawl
from app.services.recipe_crawler.sites import SITES


def _print(report: CrawlReport) -> None:
    sys.stdout.write(f"{report.pages_fetched} pages read\n")
    for outcome in sorted(
        report.outcomes, key=lambda o: (o.site, -(o.score or 0), o.url)
    ):
        status = outcome.status.value
        score = f"{outcome.score:.2f}" if outcome.score is not None else "    "
        detail = outcome.reason or outcome.title or ""
        sys.stdout.write(
            f"{status:>9}  {score}  {outcome.site:<16} {outcome.url}  {detail}\n"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="judge recipes, but neither record nor import anything",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    with Session(engine) as session:
        if args.dry_run:
            report: CrawlReport | None = crawl(
                session,
                sites=SITES,
                max_imports=settings.RECIPE_CRAWL_MAX_IMPORTS,
                max_pages_per_site=settings.RECIPE_CRAWL_MAX_PAGES_PER_SITE,
                delay_seconds=settings.RECIPE_CRAWL_DELAY_SECONDS,
                dry_run=True,
            )
        else:
            report = run_crawl(session)
    if report is None:
        sys.stdout.write(
            "Nothing to do: RECIPE_CRAWL_MAX_IMPORTS is 0 or no AI provider is set.\n"
        )
    else:
        _print(report)


if __name__ == "__main__":
    main()
