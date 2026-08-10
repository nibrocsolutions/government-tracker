"""Seed New Hanover County and initial FY25-26 budget data.

Budget figures sourced from the New Hanover County FY 2025-2026 Adopted Budget
In-Brief (https://www.nhcgov.com / DocumentCenter).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BudgetLineItem, BudgetYear, NewsSource, Organization, Story


TOPIC_KEYWORDS = {
    "education": [
        "school",
        "schools",
        "education",
        "teacher",
        "student",
        "bond",
        "pre-k",
        "cfcc",
        "community college",
        "nhcs",
    ],
    "public safety": [
        "sheriff",
        "police",
        "fire",
        "911",
        "emergency",
        "crime",
        "jail",
        "public safety",
    ],
    "human services": [
        "health",
        "human services",
        "social services",
        "senior",
        "housing",
        "homeless",
        "mental health",
        "trillium",
    ],
    "general government": [
        "commissioner",
        "budget",
        "tax",
        "election",
        "board",
        "manager",
        "government",
        "meeting",
    ],
    "cultural & recreational": [
        "park",
        "library",
        "museum",
        "garden",
        "recreation",
        "arboretum",
        "airlie",
    ],
    "economic development": [
        "economic",
        "development",
        "business",
        "film",
        "tourism",
        "downtown",
    ],
    "debt service": ["debt", "bond", "financing", "capital project"],
}


def score_budget_relevance(title: str, summary: str | None = None) -> tuple[list[str], float]:
    text = f"{title} {summary or ''}".lower()
    matched: list[str] = []
    score = 0.0
    for topic, keywords in TOPIC_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in text)
        if hits:
            matched.append(topic)
            score += min(hits, 3) * 0.2
    if "budget" in text or "tax rate" in text or "fiscal" in text:
        score += 0.5
        if "general government" not in matched:
            matched.append("general government")
    return matched, min(score, 1.0)


NHC_SOURCES = [
    {
        "name": "NHC Official News",
        "source_type": "official",
        "url": "https://www.nhcgov.com/CivicAlerts.aspx?CID=1,15",
    },
    {
        "name": "NHC Budget Pages",
        "source_type": "official",
        "url": "https://www.nhcgov.com/2784/Fiscal-Year-2025-2026",
    },
    {
        "name": "Port City Daily",
        "source_type": "rss",
        "url": "https://portcitydaily.com/feed/",
    },
    {
        "name": "WHQR Local News",
        "source_type": "rss",
        "url": "https://www.whqr.org/local.rss",
    },
    {
        "name": "WECT Local News",
        "source_type": "rss",
        "url": "https://www.wect.com/arc/outboundfeeds/rss/?outputType=xml",
    },
    {
        "name": "Google News — New Hanover County",
        "source_type": "rss",
        "url": (
            "https://news.google.com/rss/search?"
            "q=%22New+Hanover+County%22&hl=en-US&gl=US&ceid=US:en"
        ),
    },
]


def ensure_nhc_sources(db: Session, org: Organization) -> None:
    existing = {
        s.name: s
        for s in db.scalars(
            select(NewsSource).where(NewsSource.organization_id == org.id)
        ).all()
    }
    desired_names = {cfg["name"] for cfg in NHC_SOURCES}
    for cfg in NHC_SOURCES:
        current = existing.get(cfg["name"])
        if current:
            current.source_type = cfg["source_type"]
            current.url = cfg["url"]
            current.enabled = True
        else:
            db.add(
                NewsSource(
                    organization_id=org.id,
                    name=cfg["name"],
                    source_type=cfg["source_type"],
                    url=cfg["url"],
                    enabled=True,
                )
            )
    # Disable legacy sources that are no longer configured
    for name, source in existing.items():
        if name not in desired_names:
            source.enabled = False


def seed_database(db: Session) -> None:
    existing = db.scalar(select(Organization).where(Organization.slug == "new-hanover-county"))
    if existing:
        ensure_nhc_sources(db, existing)
        db.commit()
        return

    org = Organization(
        slug="new-hanover-county",
        name="New Hanover County, North Carolina",
        short_name="New Hanover County",
        jurisdiction_type="county",
        state="NC",
        website_url="https://www.nhcgov.com/",
        description=(
            "Coastal North Carolina county governing Wilmington and surrounding "
            "communities. Tracks official budget figures against county news and "
            "local media coverage."
        ),
    )
    db.add(org)
    db.flush()

    budget = BudgetYear(
        organization_id=org.id,
        fiscal_year="FY2025-26",
        label="Fiscal Year 2025–2026 Adopted Budget",
        status="adopted",
        tax_rate_cents=30.6,
        total_expenditures=468_912_088,
        total_revenues=468_912_088,
        adopted_on="2025-06-12",
        source_url="https://www.nhcgov.com/2784/Fiscal-Year-2025-2026",
        notes=(
            "Adopted 3–2 by the Board of Commissioners on June 12, 2025. "
            "Property tax rate held at 30.6¢ per $100 assessed value "
            "(29.5¢ General Fund + 1.1¢ Debt Service). "
            "Figures from the FY25-26 Adopted Budget In-Brief."
        ),
    )
    db.add(budget)
    db.flush()

    expenditures = [
        ("Education", 122_480_584, 132_939_870, -7.9, 1),
        ("Public Safety", 114_321_811, 115_557_861, -1.1, 2),
        ("Human Services", 76_891_159, 82_003_212, -6.2, 3),
        ("General Government", 75_222_796, 80_435_488, -6.5, 4),
        ("Education Debt", 29_666_078, 30_918_828, -4.1, 5),
        ("Debt Service", 29_121_633, 26_415_829, 10.2, 6),
        ("Cultural & Recreational", 19_123_903, 17_336_803, 10.3, 7),
        ("Economic & Physical Development", 2_084_124, 2_699_338, -22.8, 8),
    ]
    for name, amount, prior, pct, order in expenditures:
        db.add(
            BudgetLineItem(
                budget_year_id=budget.id,
                category="expenditure",
                function_name=name,
                amount=amount,
                prior_amount=prior,
                pct_change=pct,
                sort_order=order,
            )
        )

    revenues = [
        ("Ad Valorem Taxes", 249_899_955, 233_213_434, 7.2, 1),
        ("Sales Taxes", 117_446_172, 116_245_087, 1.0, 2),
        ("Intergovernmental Revenues", 40_860_744, 47_148_429, -13.3, 3),
        ("Fund Balance Appropriations", 19_701_103, 52_193_661, -62.3, 4),
        ("Other Revenues", 15_290_885, 18_693_164, -18.2, 5),
        ("Charges for Services", 13_726_580, 12_908_749, 6.3, 6),
        ("Transfers", 6_082_203, 3_320_647, 83.2, 7),
        ("Other Taxes", 5_904_446, 5_637_977, 4.7, 8),
    ]
    # Fund-balance appropriations roll up General / Mental Health / Debt Service /
    # Automation enhancement balances from the Adopted In-Brief (~$19.7M).
    for name, amount, prior, pct, order in revenues:
        db.add(
            BudgetLineItem(
                budget_year_id=budget.id,
                category="revenue",
                function_name=name,
                amount=amount,
                prior_amount=prior,
                pct_change=pct,
                sort_order=order,
            )
        )

    ensure_nhc_sources(db, org)
    db.flush()

    official_news = db.scalar(
        select(NewsSource).where(
            NewsSource.organization_id == org.id,
            NewsSource.name == "NHC Official News",
        )
    )
    budget_pages = db.scalar(
        select(NewsSource).where(
            NewsSource.organization_id == org.id,
            NewsSource.name == "NHC Budget Pages",
        )
    )

    # Seed a few illustrative stories so the dashboard is useful before first collect
    seed_stories = [
        (
            official_news,
            "New Hanover County announces opening of Phase 2 expansion at Smith Creek Park",
            "This 85-acre lot features a new entrance, parking area, restroom, picnic shelter "
            "and a one-mile paved trail that is ADA-accessible.",
            "https://www.nhcgov.com/CivicAlerts.aspx?AID=1153",
            True,
        ),
        (
            official_news,
            "New Hanover County seeking applicants for boards and committees",
            "The Board of Commissioners is seeking residents to apply for appointment to "
            "several boards and committees. Applications due September 3, 2026.",
            "https://www.nhcgov.com/CivicAlerts.aspx?AID=1152",
            True,
        ),
        (
            budget_pages,
            "Board adopts Fiscal Year 2025-2026 budget at 30.6-cent tax rate",
            "Commissioners adopted the FY25-26 budget in a 3-2 vote on June 12, 2025, "
            "holding the property tax rate at 30.6 cents per $100 assessed value.",
            "https://www.nhcgov.com/2784/Fiscal-Year-2025-2026",
            True,
        ),
        (
            official_news,
            "New Hanover County Board of Elections shares voter registration guidance",
            "As the November 3, 2026 General Election approaches, voters are reminded about "
            "registration drives and election-related mailings.",
            "https://www.nhcgov.com/CivicAlerts.aspx?AID=1149",
            True,
        ),
    ]
    for source, title, summary, url, official in seed_stories:
        if source is None:
            continue
        topics, relevance = score_budget_relevance(title, summary)
        db.add(
            Story(
                organization_id=org.id,
                source_id=source.id,
                title=title,
                summary=summary,
                url=url,
                topics=",".join(topics),
                budget_relevance=relevance,
                is_official=official,
            )
        )

    db.commit()
