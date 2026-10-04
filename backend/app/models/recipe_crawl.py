"""What the recipe crawler has seen, and when it last ran.

``CrawledRecipe`` is the crawler's memory: one row per recipe page it has ever
judged, keyed by the page's canonical URL. It is what keeps a recipe from being
imported twice, what keeps the crawler from re-reading, every day, a page it
already turned down, and — through its ``QUALIFIED`` rows — the backlog of good
recipes waiting to be imported.
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel

from app.models.base import get_datetime_utc, stored_enum


class CrawlStatus(str, Enum):
    #: Read, and good enough: waiting its turn in the import backlog, which
    #: each run takes from best ``score`` first.
    QUALIFIED = "qualified"
    #: Became a public recipe. Never fetched again, even if that recipe is later
    #: deleted: a deletion is an editorial decision the crawler must not undo.
    IMPORTED = "imported"
    #: Read and judged not good enough (rating, completeness, robots.txt).
    #: Re-judged after a while, since ratings move.
    REJECTED = "rejected"
    #: Qualified, but the import itself broke (model error, unusable output).
    #: Back in the backlog the next day, given up after a few attempts.
    FAILED = "failed"


class CrawledRecipe(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    #: Slug of the site in ``recipe_crawler.sites``.
    site: str = Field(max_length=64, index=True)
    #: Canonical URL: the page's own ``rel=canonical`` when it names one on the
    #: same site, without query string or fragment. Unique, so two workers or
    #: two listing pages can never import the same recipe twice.
    url: str = Field(max_length=2048, unique=True, index=True)
    status: CrawlStatus = Field(sa_type=stored_enum(CrawlStatus, 20))
    #: Why it was rejected or failed, for whoever reads the table.
    reason: str | None = Field(default=None, max_length=500)
    title: str | None = Field(default=None, max_length=255)
    #: The site's rating, normalised to a 0–5 scale, and how many people gave it.
    rating_value: float | None = None
    rating_count: int | None = None
    #: Rank in the import backlog (``quality.score``); set once qualified.
    score: float | None = None
    recipe_id: uuid.UUID | None = Field(
        default=None, foreign_key="recipe.id", nullable=True, ondelete="SET NULL"
    )
    #: Import attempts so far; judging a page is not one.
    attempts: int = Field(default=0)
    first_seen_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    last_attempt_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class RecipeCrawlRun(SQLModel, table=True):
    """One pass of the crawler. The latest one decides when the next is due."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    started_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    finished_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    pages_fetched: int = 0
    qualified_count: int = 0
    imported_count: int = 0
    rejected_count: int = 0
    failed_count: int = 0
