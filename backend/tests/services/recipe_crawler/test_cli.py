from unittest.mock import patch

import pytest

from app.models import CrawlStatus
from app.services.recipe_crawler import __main__ as cli
from app.services.recipe_crawler.crawler import CrawlReport, Outcome


def _report() -> CrawlReport:
    return CrawlReport(
        pages_fetched=3,
        outcomes=[
            Outcome(
                "marmiton", "https://m/1", CrawlStatus.QUALIFIED, "Tiramisu", score=4.7
            ),
            Outcome(
                "marmiton", "https://m/2", CrawlStatus.REJECTED, reason="no rating"
            ),
        ],
    )


def test_dry_run_judges_without_importing(capsys: pytest.CaptureFixture[str]) -> None:
    with (
        patch("sys.argv", ["recipe_crawler", "--dry-run"]),
        patch.object(cli, "crawl", return_value=_report()) as crawl,
        patch.object(cli, "run_crawl") as run_crawl,
    ):
        cli.main()

    assert crawl.call_args.kwargs["dry_run"] is True
    run_crawl.assert_not_called()
    out = capsys.readouterr().out
    assert "3 pages read" in out
    assert "qualified  4.70  marmiton" in out
    assert "no rating" in out


def test_run_explains_when_there_is_nothing_to_do(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with (
        patch("sys.argv", ["recipe_crawler"]),
        patch.object(cli, "run_crawl", return_value=None),
    ):
        cli.main()

    assert "Nothing to do" in capsys.readouterr().out
