from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.collectors.runner import run_collection
from app.database import get_db
from app.models import BudgetYear, CollectionRun, NewsSource, Organization, Story, TransparencyResource
from app.money import extract_mentioned_money
from app.schemas import (
    BudgetStoryLinkOut,
    BudgetYearOut,
    BudgetYearSummaryOut,
    CollectionStatusOut,
    DashboardOut,
    FiscalBalanceOut,
    OrganizationOut,
    StoryOut,
    TopicMentionOut,
    TransparencyResourceOut,
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
    budgets = list(
        db.scalars(
            select(BudgetYear)
            .where(BudgetYear.organization_id == org.id)
            .options(selectinload(BudgetYear.line_items))
            .order_by(BudgetYear.fiscal_year)
        ).all()
    )
    budget = None
    if budgets:
        # Prefer the latest fiscal year label lexicographically (FY2025-26 > FY2024-25)
        budget = sorted(budgets, key=lambda b: b.fiscal_year)[-1]

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
    resources = list(
        db.scalars(
            select(TransparencyResource)
            .where(TransparencyResource.organization_id == org.id)
            .order_by(TransparencyResource.sort_order, TransparencyResource.name)
        ).all()
    )

    topic_counts: dict[str, int] = {}
    for story in stories:
        for topic in [t.strip() for t in (story.topics or "").split(",") if t.strip()]:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1

    budget_by_topic: dict[str, float] = {}
    total_exp = budget.total_expenditures if budget else 0
    top_destinations = []
    if budget:
        for item in budget.line_items:
            if item.category == "department":
                top_destinations.append(item)
                continue
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
        top_destinations.sort(key=lambda i: i.sort_order)

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

    budget_story_links: list[BudgetStoryLinkOut] = []
    seen_pairs: set[tuple[str, int]] = set()
    for story in stories:
        topics = [t.strip() for t in (story.topics or "").split(",") if t.strip()]
        if not topics and story.budget_relevance <= 0:
            continue
        ranked_topics = sorted(
            topics,
            key=lambda t: (
                0 if budget_by_topic.get(t) is not None else 1,
                -story.budget_relevance,
                t,
            ),
        )
        for topic in ranked_topics:
            pair = (topic, story.id)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            amount = budget_by_topic.get(topic)
            share = (amount / total_exp * 100) if amount and total_exp else None
            mentioned_money, mentioned_value = extract_mentioned_money(
                story.title, story.summary
            )
            budget_story_links.append(
                BudgetStoryLinkOut(
                    budget_category=topic,
                    budget_amount=amount,
                    budget_share=round(share, 1) if share is not None else None,
                    story_id=story.id,
                    story_title=story.title,
                    story_url=story.url,
                    source_name=story.source.name if story.source else None,
                    budget_relevance=story.budget_relevance,
                    is_official=story.is_official,
                    published_at=story.published_at or story.collected_at,
                    mentioned_money=mentioned_money,
                    mentioned_money_value=mentioned_value,
                )
            )
            break
    budget_story_links.sort(
        key=lambda row: (
            -(row.budget_amount or 0),
            -row.budget_relevance,
            row.budget_category,
            row.story_title.lower(),
        )
    )

    history: list[BudgetYearSummaryOut] = []
    for row in sorted(budgets, key=lambda b: b.fiscal_year):
        gap = round((row.total_expenditures or 0) - (row.total_revenues or 0), 2)
        reserve = float(row.fund_balance_appropriated or 0)
        history.append(
            BudgetYearSummaryOut(
                fiscal_year=row.fiscal_year,
                label=row.label,
                tax_rate_cents=row.tax_rate_cents,
                total_expenditures=row.total_expenditures,
                total_revenues=row.total_revenues,
                all_funds_total=row.all_funds_total,
                fund_balance_appropriated=row.fund_balance_appropriated,
                is_balanced=bool(row.is_balanced if row.is_balanced is not None else True),
                balance_summary=row.balance_summary,
                adopted_on=row.adopted_on,
                source_url=row.source_url,
                operating_gap=gap,
                reserve_draw=reserve,
            )
        )

    fiscal_balance = None
    if budget:
        adopted_gap = round((budget.total_expenditures or 0) - (budget.total_revenues or 0), 2)
        reserve_draw = float(budget.fund_balance_appropriated or 0)
        recurring = (budget.total_revenues or 0) - reserve_draw
        coverage = None
        if recurring > 0 and budget.total_expenditures:
            coverage = round(recurring / budget.total_expenditures * 100, 1)
        if adopted_gap == 0 and reserve_draw > 0:
            status = "balanced_with_reserves"
            headline = "Balanced on paper, drawing reserves"
            detail = (
                budget.balance_summary
                or (
                    "North Carolina counties must adopt a balanced budget ordinance "
                    "(appropriations = estimated revenues). This plan is balanced, but "
                    f"{reserve_draw:,.0f} of revenue is appropriated fund balance—so "
                    "spending exceeds recurring revenues alone."
                )
            )
        elif adopted_gap == 0:
            status = "balanced"
            headline = "Balanced adopted budget"
            detail = (
                budget.balance_summary
                or (
                    "The adopted ordinance balances estimated revenues with appropriations. "
                    "Check the Annual Comprehensive Financial Report (ACFR) after year-end "
                    "for actual surplus or deficit results."
                )
            )
        elif adopted_gap > 0:
            status = "deficit"
            headline = "Adopted plan spends more than estimated revenues"
            detail = budget.balance_summary or f"Adopted gap of ${adopted_gap:,.0f}."
        else:
            status = "surplus"
            headline = "Adopted plan estimates more revenue than appropriations"
            detail = budget.balance_summary or f"Adopted surplus of ${abs(adopted_gap):,.0f}."
        fiscal_balance = FiscalBalanceOut(
            status=status,
            headline=headline,
            detail=detail,
            adopted_gap=adopted_gap,
            reserve_draw=reserve_draw,
            recurring_revenue_coverage=coverage,
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
        budget_history=history,
        fiscal_balance=fiscal_balance,
        top_destinations=top_destinations,
        transparency_resources=[TransparencyResourceOut.model_validate(r) for r in resources],
        recent_stories=[StoryOut.model_validate(s) for s in stories[:25]],
        official_stories=[StoryOut.model_validate(s) for s in official],
        external_stories=[StoryOut.model_validate(s) for s in external],
        topic_mentions=topic_mentions,
        budget_story_links=budget_story_links[:60],
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
