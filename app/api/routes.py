from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.collectors.runner import run_collection
from app.database import get_db
from app.models import BudgetYear, CollectionRun, NewsSource, Organization, Story
from app.schemas import (
    BudgetYearOut,
    CollectionStatusOut,
    DashboardOut,
    OrganizationOut,
    StoryOut,
    TopicMentionOut,
)

router = APIRouter(prefix="/api")


def _get_org(db: Session, slug: str) -> Organization:
    org = db.scalar(select(Organization).where(Organization.slug == slug))
    if not org:
        raise HTTPException(status_code=404, detail=f"Organization '{slug}' not found")
    return org


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "government-tracker"}


@router.get("/organizations", response_model=list[OrganizationOut])
def list_organizations(db: Session = Depends(get_db)) -> list[Organization]:
    return list(db.scalars(select(Organization).order_by(Organization.name)).all())


@router.get("/organizations/{slug}", response_model=OrganizationOut)
def get_organization(slug: str, db: Session = Depends(get_db)) -> Organization:
    return _get_org(db, slug)


@router.get("/organizations/{slug}/budget", response_model=BudgetYearOut | None)
def get_budget(slug: str, db: Session = Depends(get_db)) -> BudgetYear | None:
    org = _get_org(db, slug)
    return db.scalar(
        select(BudgetYear)
        .where(BudgetYear.organization_id == org.id)
        .options(selectinload(BudgetYear.line_items))
        .order_by(desc(BudgetYear.fiscal_year))
    )


@router.get("/organizations/{slug}/stories", response_model=list[StoryOut])
def list_stories(
    slug: str,
    limit: int = 50,
    official_only: bool = False,
    budget_related: bool = False,
    db: Session = Depends(get_db),
) -> list[Story]:
    org = _get_org(db, slug)
    query = (
        select(Story)
        .where(Story.organization_id == org.id)
        .options(selectinload(Story.source))
        .order_by(desc(Story.published_at), desc(Story.collected_at))
        .limit(min(limit, 200))
    )
    if official_only:
        query = query.where(Story.is_official.is_(True))
    if budget_related:
        query = query.where(Story.budget_relevance > 0)
    return list(db.scalars(query).all())


@router.get("/organizations/{slug}/dashboard", response_model=DashboardOut)
def dashboard(slug: str, db: Session = Depends(get_db)) -> DashboardOut:
    org = _get_org(db, slug)
    budget = db.scalar(
        select(BudgetYear)
        .where(BudgetYear.organization_id == org.id)
        .options(selectinload(BudgetYear.line_items))
        .order_by(desc(BudgetYear.fiscal_year))
    )
    stories = list(
        db.scalars(
            select(Story)
            .where(Story.organization_id == org.id)
            .options(selectinload(Story.source))
            .order_by(desc(Story.published_at), desc(Story.collected_at))
            .limit(80)
        ).all()
    )
    sources = list(
        db.scalars(
            select(NewsSource)
            .where(NewsSource.organization_id == org.id)
            .order_by(NewsSource.name)
        ).all()
    )

    topic_counts: dict[str, int] = {}
    for story in stories:
        for topic in [t.strip() for t in (story.topics or "").split(",") if t.strip()]:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1

    budget_by_topic: dict[str, float] = {}
    total_exp = budget.total_expenditures if budget else 0
    if budget:
        for item in budget.line_items:
            if item.category != "expenditure":
                continue
            key = item.function_name.lower()
            if "education debt" in key:
                budget_by_topic["education"] = budget_by_topic.get("education", 0) + item.amount
            elif "education" in key:
                budget_by_topic["education"] = budget_by_topic.get("education", 0) + item.amount
            elif "public safety" in key:
                budget_by_topic["public safety"] = item.amount
            elif "human services" in key:
                budget_by_topic["human services"] = item.amount
            elif "general government" in key:
                budget_by_topic["general government"] = item.amount
            elif "cultural" in key:
                budget_by_topic["cultural & recreational"] = item.amount
            elif "economic" in key:
                budget_by_topic["economic development"] = item.amount
            elif "debt" in key:
                budget_by_topic["debt service"] = budget_by_topic.get("debt service", 0) + item.amount

    topic_mentions = []
    for topic, count in sorted(topic_counts.items(), key=lambda x: (-x[1], x[0])):
        amount = budget_by_topic.get(topic)
        share = (amount / total_exp * 100) if amount and total_exp else None
        topic_mentions.append(
            TopicMentionOut(
                topic=topic,
                story_count=count,
                budget_amount=amount,
                budget_share=round(share, 1) if share is not None else None,
            )
        )

    last_run = db.scalar(select(CollectionRun).order_by(desc(CollectionRun.started_at)))
    last_collection: datetime | None = None
    if last_run and last_run.finished_at:
        last_collection = last_run.finished_at
    else:
        collected = [s.last_collected_at for s in sources if s.last_collected_at]
        last_collection = max(collected) if collected else None

    official = [s for s in stories if s.is_official][:20]
    external = [s for s in stories if not s.is_official][:20]

    return DashboardOut(
        organization=OrganizationOut.model_validate(org),
        current_budget=BudgetYearOut.model_validate(budget) if budget else None,
        recent_stories=[StoryOut.model_validate(s) for s in stories[:25]],
        official_stories=[StoryOut.model_validate(s) for s in official],
        external_stories=[StoryOut.model_validate(s) for s in external],
        topic_mentions=topic_mentions,
        sources=[s for s in sources],
        last_collection=last_collection,
    )


@router.post("/collect", response_model=CollectionStatusOut)
def trigger_collect(db: Session = Depends(get_db)) -> CollectionStatusOut:
    run = run_collection(db)
    return CollectionStatusOut(
        status=run.status,
        stories_added=run.stories_added,
        message=run.message,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


@router.get("/collect/status", response_model=CollectionStatusOut | None)
def collect_status(db: Session = Depends(get_db)) -> CollectionStatusOut | None:
    run = db.scalar(select(CollectionRun).order_by(desc(CollectionRun.started_at)))
    if not run:
        return None
    return CollectionStatusOut(
        status=run.status,
        stories_added=run.stories_added,
        message=run.message,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )
