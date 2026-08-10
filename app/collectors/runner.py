from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

import feedparser
import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import CollectionRun, NewsSource, Story
from app.seed import score_budget_relevance


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except (TypeError, ValueError, IndexError):
        return None


def _client() -> httpx.Client:
    return httpx.Client(
        timeout=15.0,
        follow_redirects=True,
        headers={"User-Agent": settings.user_agent},
    )


def upsert_story(
    db: Session,
    *,
    organization_id: int,
    source: NewsSource,
    title: str,
    summary: str | None,
    url: str,
    published_at: datetime | None,
    is_official: bool,
) -> bool:
    existing = db.scalar(select(Story).where(Story.url == url))
    if existing:
        return False
    topics, relevance = score_budget_relevance(title, summary)
    db.add(
        Story(
            organization_id=organization_id,
            source_id=source.id,
            title=title.strip()[:500],
            summary=(summary or "").strip()[:2000] or None,
            url=url.strip()[:700],
            published_at=published_at,
            topics=",".join(topics),
            budget_relevance=relevance,
            is_official=is_official,
        )
    )
    return True


def collect_rss(db: Session, source: NewsSource) -> int:
    added = 0
    with _client() as client:
        response = client.get(source.url)
        response.raise_for_status()
        feed = feedparser.parse(response.text)

    for entry in feed.entries[:40]:
        title = getattr(entry, "title", None) or ""
        if not title:
            continue
        link = getattr(entry, "link", None) or ""
        if not link:
            continue
        summary = getattr(entry, "summary", None) or getattr(entry, "description", None)
        if summary:
            summary_text = str(summary).strip()
            if "<" in summary_text and ">" in summary_text:
                summary = BeautifulSoup(summary_text, "lxml").get_text(" ", strip=True)
            else:
                summary = summary_text
            summary = summary[:2000] or None
        published = _parse_date(getattr(entry, "published", None) or getattr(entry, "updated", None))
        if upsert_story(
            db,
            organization_id=source.organization_id,
            source=source,
            title=title,
            summary=summary,
            url=link,
            published_at=published,
            is_official=False,
        ):
            added += 1
    return added


def collect_nhc_official(db: Session, source: NewsSource) -> int:
    added = 0
    with _client() as client:
        response = client.get(source.url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

    # CivicAlerts list pages and general news blocks
    candidates = soup.select("a[href*='CivicAlerts.aspx?AID='], .widgetNewsItem a, .fr-view a")
    seen: set[str] = set()
    for anchor in candidates:
        href = anchor.get("href")
        title = anchor.get_text(" ", strip=True)
        if not href or not title or len(title) < 12:
            continue
        url = urljoin(source.url, href)
        if url in seen:
            continue
        seen.add(url)
        parent = anchor.find_parent(["li", "div", "article"])
        summary = None
        if parent:
            text = parent.get_text(" ", strip=True)
            if text and text != title:
                summary = text.replace(title, "", 1).strip()[:500]
        if upsert_story(
            db,
            organization_id=source.organization_id,
            source=source,
            title=title,
            summary=summary,
            url=url,
            published_at=None,
            is_official=True,
        ):
            added += 1
        if added >= 30:
            break
    return added


def collect_whqr(db: Session, source: NewsSource) -> int:
    added = 0
    with _client() as client:
        response = client.get(source.url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

    for article in soup.select("article, .Node-article, .Promo")[:40]:
        anchor = article.select_one("a[href]")
        if not anchor:
            continue
        title = anchor.get_text(" ", strip=True)
        href = anchor.get("href")
        if not title or not href or len(title) < 16:
            continue
        url = urljoin(source.url, href)
        summary_el = article.select_one("p, .Teaser, .Promo-description")
        summary = summary_el.get_text(" ", strip=True) if summary_el else None
        # Prefer stories mentioning local government
        blob = f"{title} {summary or ''}".lower()
        if not any(
            token in blob
            for token in (
                "new hanover",
                "wilmington",
                "county",
                "budget",
                "commissioner",
                "school",
                "sheriff",
            )
        ):
            continue
        if upsert_story(
            db,
            organization_id=source.organization_id,
            source=source,
            title=title,
            summary=summary,
            url=url,
            published_at=None,
            is_official=False,
        ):
            added += 1
    return added


def collect_source(db: Session, source: NewsSource) -> int:
    if source.source_type == "rss":
        return collect_rss(db, source)
    if source.source_type == "official":
        return collect_nhc_official(db, source)
    if source.source_type == "scrape" and "whqr.org" in source.url:
        return collect_whqr(db, source)
    if source.source_type == "scrape":
        # Generic scrape: pull article-like links from the page
        return collect_nhc_official(db, source)
    return 0


def run_collection(db: Session) -> CollectionRun:
    run = CollectionRun(status="running", started_at=_now())
    db.add(run)
    db.commit()
    db.refresh(run)

    total_added = 0
    errors: list[str] = []
    sources = db.scalars(select(NewsSource).where(NewsSource.enabled.is_(True))).all()

    for source in sources:
        try:
            added = collect_source(db, source)
            total_added += added
            source.last_collected_at = _now()
            db.commit()
        except Exception as exc:  # noqa: BLE001 - collectors should not abort the whole run
            db.rollback()
            errors.append(f"{source.name}: {exc}")
            # re-attach run after rollback
            run = db.get(CollectionRun, run.id) or run

    run = db.get(CollectionRun, run.id)
    assert run is not None
    run.stories_added = total_added
    run.finished_at = _now()
    run.status = "completed" if not errors else "completed_with_errors"
    run.message = "; ".join(errors) if errors else f"Collected {total_added} new stories"
    db.commit()
    db.refresh(run)
    return run
