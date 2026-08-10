from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    short_name: str
    jurisdiction_type: str
    state: str
    website_url: str
    description: str | None = None


class BudgetLineItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    function_name: str
    amount: float
    prior_amount: float | None = None
    pct_change: float | None = None
    sort_order: int = 0


class BudgetYearOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fiscal_year: str
    label: str
    status: str
    tax_rate_cents: float | None = None
    total_expenditures: float
    total_revenues: float
    adopted_on: str | None = None
    source_url: str | None = None
    notes: str | None = None
    line_items: list[BudgetLineItemOut] = Field(default_factory=list)


class NewsSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    source_type: str
    url: str
    enabled: bool
    last_collected_at: datetime | None = None


class StoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    summary: str | None = None
    url: str
    published_at: datetime | None = None
    collected_at: datetime
    topics: str
    budget_relevance: float
    is_official: bool
    source: NewsSourceOut | None = None


class TopicMentionOut(BaseModel):
    topic: str
    story_count: int
    budget_amount: float | None = None
    budget_share: float | None = None


class DashboardOut(BaseModel):
    organization: OrganizationOut
    current_budget: BudgetYearOut | None
    recent_stories: list[StoryOut]
    official_stories: list[StoryOut]
    external_stories: list[StoryOut]
    topic_mentions: list[TopicMentionOut]
    sources: list[NewsSourceOut]
    last_collection: datetime | None = None


class CollectionStatusOut(BaseModel):
    status: str
    stories_added: int = 0
    message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
