"""Lightweight SQLite column adds for evolving models."""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    if "budget_years" in tables:
        cols = {c["name"] for c in inspector.get_columns("budget_years")}
        alters = []
        if "all_funds_total" not in cols:
            alters.append("ADD COLUMN all_funds_total FLOAT")
        if "fund_balance_appropriated" not in cols:
            alters.append("ADD COLUMN fund_balance_appropriated FLOAT")
        if "is_balanced" not in cols:
            alters.append("ADD COLUMN is_balanced BOOLEAN DEFAULT 1")
        if "balance_summary" not in cols:
            alters.append("ADD COLUMN balance_summary TEXT")
        with engine.begin() as conn:
            for clause in alters:
                conn.execute(text(f"ALTER TABLE budget_years {clause}"))

    if "transparency_resources" not in tables:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE transparency_resources (
                        id INTEGER PRIMARY KEY,
                        organization_id INTEGER NOT NULL,
                        name VARCHAR(200) NOT NULL,
                        category VARCHAR(80) NOT NULL,
                        url VARCHAR(700) NOT NULL,
                        description TEXT,
                        sort_order INTEGER DEFAULT 0,
                        FOREIGN KEY(organization_id) REFERENCES organizations (id)
                    )
                    """
                )
            )
