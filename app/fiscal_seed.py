"""Historical budgets, department destinations, and transparency resources for NHC."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BudgetLineItem, BudgetYear, Organization, TransparencyResource

# Comparable General Fund / Modified GF adopted totals from NHC budget books & notices.
NHC_HISTORY = [
    {
        "fiscal_year": "FY2022-23",
        "label": "Fiscal Year 2022–2023 Adopted Budget",
        "status": "adopted",
        "tax_rate_cents": 45.5,
        "total_expenditures": 508_000_000,
        "total_revenues": 508_000_000,
        "all_funds_total": 508_000_000,
        "fund_balance_appropriated": 0,
        "is_balanced": True,
        "adopted_on": "2022-06-06",
        "source_url": "https://www.nhcgov.com/341/Fiscal-Year-2022-2023",
        "balance_summary": (
            "Adopted as a balanced budget (revenues = appropriations). "
            "County materials described a $508M balanced plan with a 2¢ tax-rate cut to 45.5¢."
        ),
        "notes": "Board unanimously adopted the FY22-23 plan on June 6, 2022.",
    },
    {
        "fiscal_year": "FY2023-24",
        "label": "Fiscal Year 2023–2024 Adopted Budget",
        "status": "adopted",
        "tax_rate_cents": 45.0,
        "total_expenditures": 441_713_950,
        "total_revenues": 441_713_950,
        "all_funds_total": 588_300_000,
        "fund_balance_appropriated": 0,
        "is_balanced": True,
        "adopted_on": "2023-06-05",
        "source_url": "https://www.nhcgov.com/2515/Fiscal-Year-2023-2024",
        "balance_summary": (
            "Balanced adopted budget. General Fund about $441.7M; all-funds spending plan "
            "about $588.3M. Tax rate cut a half-cent to 45.0¢."
        ),
        "notes": "Approved by a majority of the Board of Commissioners on June 5, 2023.",
    },
    {
        "fiscal_year": "FY2024-25",
        "label": "Fiscal Year 2024–2025 Adopted Budget",
        "status": "adopted",
        "tax_rate_cents": 45.0,
        "total_expenditures": 448_615_702,
        "total_revenues": 448_615_702,
        "all_funds_total": 543_100_000,
        "fund_balance_appropriated": 0,
        "is_balanced": True,
        "adopted_on": "2024-06-17",
        "source_url": "https://www.nhcgov.com/2516/Fiscal-Year-2024-2025",
        "balance_summary": (
            "Balanced adopted budget at 45.0¢. County materials emphasized little/no principal "
            "use of the Revenue Stabilization Fund for General Fund operations. "
            "All-funds plan about $543.1M."
        ),
        "notes": (
            "Comparable Modified General Fund series from later In-Brief tables is $448.6M; "
            "the budget ordinance also lists a $423.8M General Fund appropriation line depending "
            "on fund presentation."
        ),
    },
    {
        "fiscal_year": "FY2025-26",
        "label": "Fiscal Year 2025–2026 Adopted Budget",
        "status": "adopted",
        "tax_rate_cents": 30.6,
        "total_expenditures": 468_912_088,
        "total_revenues": 468_912_088,
        "all_funds_total": 558_722_817,
        "fund_balance_appropriated": 19_701_103,
        "is_balanced": True,
        "adopted_on": "2025-06-12",
        "source_url": "https://www.nhcgov.com/2784/Fiscal-Year-2025-2026",
        "balance_summary": (
            "Still a balanced ordinance (appropriations = estimated revenues), but about "
            "$19.7M comes from fund-balance appropriations—so the plan draws on reserves "
            "rather than recurring revenues alone. Revaluation year; rate reset to 30.6¢."
        ),
        "notes": (
            "Adopted 3–2 on June 12, 2025. Education + education debt ≈ 32% of General Fund. "
            "Top destinations include Schools operating support and the Sheriff’s Office."
        ),
    },
]

# Top FY25-26 General Fund destinations from Adopted In-Brief department comparison.
FY26_DEPARTMENTS = [
    ("New Hanover County Schools — Operating", 103_463_712, 99_560_894, 3.9, 1),
    ("Sheriff's Office", 93_408_418, 89_692_125, 4.1, 2),
    ("Social Services", 42_017_889, 42_458_884, -1.0, 3),
    ("Health Department", 25_098_251, 24_800_224, 1.2, 4),
    ("Installment Debt (non-education)", 24_332_340, 21_455_286, 13.4, 5),
    ("NHC Schools — Debt Service", 20_247_137, 21_169_476, -4.4, 6),
    ("Facilities Management", 19_183_596, 20_372_255, -5.8, 7),
    ("Information Technology", 17_365_757, 14_922_962, 16.4, 8),
    ("Cape Fear Community College — Operating", 13_258_161, 11_922_167, 11.2, 9),
    ("Non-Departmental", 11_585_139, 15_776_820, -26.6, 10),
    ("CFCC — Debt Service", 9_391_641, 9_717_965, -3.4, 11),
    ("Parks and Gardens", 8_677_088, 8_330_615, 4.2, 12),
    ("911 Call Center", 8_118_537, 8_997_959, -9.8, 13),
    ("Library", 7_564_405, 5_959_602, 26.9, 14),
    ("Tax Administration", 6_066_490, 6_009_460, 0.9, 15),
]

NHC_RESOURCES = [
    {
        "name": "Open Public Records Request portal",
        "category": "public_records",
        "url": "https://newhanovercountync.nextrequest.com/",
        "description": (
            "Submit a North Carolina public records request (N.C.G.S. Chapter 132) for budget "
            "workpapers, contracts, emails, or other fiscal records not already posted online. "
            "Managed by the Office of Communications. Not for background checks, marriage, "
            "divorce, property, or court records."
        ),
        "sort_order": 1,
    },
    {
        "name": "Information Requests (how-to page)",
        "category": "public_records",
        "url": "https://www.nhcgov.com/193/Information-Requests",
        "description": (
            "County page explaining public records law and which requests belong in the portal "
            "versus other departments."
        ),
        "sort_order": 2,
    },
    {
        "name": "Fiscal Year Budgets archive",
        "category": "budget_documents",
        "url": "https://www.nhcgov.com/297/Fiscal-Year-Budgets",
        "description": "Official adopted/recommended budget books and In-Brief PDFs by fiscal year.",
        "sort_order": 3,
    },
    {
        "name": "FY25-26 Adopted Budget page",
        "category": "budget_documents",
        "url": "https://www.nhcgov.com/2784/Fiscal-Year-2025-2026",
        "description": "Current adopted budget narrative, In-Brief, and full Adopted Book links.",
        "sort_order": 4,
    },
    {
        "name": "Taxpayer Receipt (Balancing Act)",
        "category": "spending_tools",
        "url": "https://nhc-engage.abalancingact.com/2025TR",
        "description": (
            "Interactive “where do my tax dollars go?” receipt based on adopted budget allocations."
        ),
        "sort_order": 5,
    },
    {
        "name": "Finance Department",
        "category": "contacts",
        "url": "https://www.nhcgov.com/252/Finance",
        "description": (
            "Finance/Budget staff publish the books and can answer process questions; budget "
            "documents list contact emails such as akostusiak@nhcgov.com for budget comments."
        ),
        "sort_order": 6,
    },
    {
        "name": "Board of Commissioners meetings & agendas",
        "category": "oversight",
        "url": "https://www.nhcgov.com/127/County-Commissioners",
        "description": (
            "Budget amendments, mid-year updates, and spending policy debates appear in agendas, "
            "packets, and meeting video."
        ),
        "sort_order": 7,
    },
    {
        "name": "Annual Comprehensive Financial Report (ACFR) search tip",
        "category": "audited_results",
        "url": "https://www.nhcgov.com/Search/Results?searchPhrase=ACFR",
        "description": (
            "Audited year-end statements show actual revenues vs expenditures (true surplus/"
            "deficit after the year closes)—use alongside the adopted budget, which must balance "
            "by North Carolina law."
        ),
        "sort_order": 8,
    },
]


def _upsert_budget_year(db: Session, org: Organization, cfg: dict) -> BudgetYear:
    budget = db.scalar(
        select(BudgetYear).where(
            BudgetYear.organization_id == org.id,
            BudgetYear.fiscal_year == cfg["fiscal_year"],
        )
    )
    if not budget:
        budget = BudgetYear(organization_id=org.id, fiscal_year=cfg["fiscal_year"])
        db.add(budget)
    for key, value in cfg.items():
        if key != "fiscal_year":
            setattr(budget, key, value)
    db.flush()
    return budget


def ensure_department_destinations(db: Session, budget: BudgetYear) -> None:
    existing = {
        item.function_name: item
        for item in budget.line_items
        if item.category == "department"
    }
    for name, amount, prior, pct, order in FY26_DEPARTMENTS:
        row = existing.get(name)
        if row:
            row.amount = amount
            row.prior_amount = prior
            row.pct_change = pct
            row.sort_order = order
        else:
            db.add(
                BudgetLineItem(
                    budget_year_id=budget.id,
                    category="department",
                    function_name=name,
                    amount=amount,
                    prior_amount=prior,
                    pct_change=pct,
                    sort_order=order,
                )
            )


def ensure_transparency_resources(db: Session, org: Organization) -> None:
    existing = {
        r.name: r
        for r in db.scalars(
            select(TransparencyResource).where(TransparencyResource.organization_id == org.id)
        ).all()
    }
    desired = {cfg["name"] for cfg in NHC_RESOURCES}
    for cfg in NHC_RESOURCES:
        row = existing.get(cfg["name"])
        if row:
            row.category = cfg["category"]
            row.url = cfg["url"]
            row.description = cfg["description"]
            row.sort_order = cfg["sort_order"]
        else:
            db.add(
                TransparencyResource(
                    organization_id=org.id,
                    name=cfg["name"],
                    category=cfg["category"],
                    url=cfg["url"],
                    description=cfg["description"],
                    sort_order=cfg["sort_order"],
                )
            )
    for name, row in existing.items():
        if name not in desired:
            db.delete(row)


def ensure_nhc_fiscal_data(db: Session, org: Organization) -> None:
    current = None
    for cfg in NHC_HISTORY:
        budget = _upsert_budget_year(db, org, cfg)
        if cfg["fiscal_year"] == "FY2025-26":
            current = budget
    if current:
        ensure_department_destinations(db, current)
    ensure_transparency_resources(db, org)
