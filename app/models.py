from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    short_name: Mapped[str] = mapped_column(String(80))
    jurisdiction_type: Mapped[str] = mapped_column(String(80), default="county")
    state: Mapped[str] = mapped_column(String(2), default="NC")
    website_url: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    budgets: Mapped[list["BudgetYear"]] = relationship(back_populates="organization")
    sources: Mapped[list["NewsSource"]] = relationship(back_populates="organization")
    stories: Mapped[list["Story"]] = relationship(back_populates="organization")


class BudgetYear(Base):
    __tablename__ = "budget_years"
    __table_args__ = (UniqueConstraint("organization_id", "fiscal_year", name="uq_org_fy"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    fiscal_year: Mapped[str] = mapped_column(String(20))
    label: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(40), default="adopted")
    tax_rate_cents: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_expenditures: Mapped[float] = mapped_column(Float, default=0)
    total_revenues: Mapped[float] = mapped_column(Float, default=0)
    adopted_on: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization: Mapped[Organization] = relationship(back_populates="budgets")
    line_items: Mapped[list["BudgetLineItem"]] = relationship(
        back_populates="budget_year", cascade="all, delete-orphan"
    )


class BudgetLineItem(Base):
    __tablename__ = "budget_line_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    budget_year_id: Mapped[int] = mapped_column(ForeignKey("budget_years.id"))
    category: Mapped[str] = mapped_column(String(40))  # expenditure | revenue
    function_name: Mapped[str] = mapped_column(String(120))
    amount: Mapped[float] = mapped_column(Float)
    prior_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    pct_change: Mapped[float | None] = mapped_column(Float, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    budget_year: Mapped[BudgetYear] = relationship(back_populates="line_items")


class NewsSource(Base):
    __tablename__ = "news_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    name: Mapped[str] = mapped_column(String(120))
    source_type: Mapped[str] = mapped_column(String(40))  # official | rss | scrape
    url: Mapped[str] = mapped_column(String(500))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_collected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    organization: Mapped[Organization] = relationship(back_populates="sources")
    stories: Mapped[list["Story"]] = relationship(back_populates="source")


class Story(Base):
    __tablename__ = "stories"
    __table_args__ = (UniqueConstraint("url", name="uq_story_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    source_id: Mapped[int | None] = mapped_column(ForeignKey("news_sources.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(700))
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    topics: Mapped[str] = mapped_column(String(300), default="")  # comma-separated tags
    budget_relevance: Mapped[float] = mapped_column(Float, default=0.0)
    is_official: Mapped[bool] = mapped_column(Boolean, default=False)

    organization: Mapped[Organization] = relationship(back_populates="stories")
    source: Mapped[NewsSource | None] = relationship(back_populates="stories")


class CollectionRun(Base):
    __tablename__ = "collection_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="running")
    stories_added: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
