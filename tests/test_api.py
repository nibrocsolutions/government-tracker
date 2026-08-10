from fastapi.testclient import TestClient

from app.main import app


def test_health():
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_organizations_and_dashboard():
    with TestClient(app) as client:
        orgs = client.get("/api/organizations")
        assert orgs.status_code == 200
        body = orgs.json()
        assert any(o["slug"] == "new-hanover-county" for o in body)

        dash = client.get("/api/organizations/new-hanover-county/dashboard")
        assert dash.status_code == 200
        data = dash.json()
        assert data["organization"]["short_name"] == "New Hanover County"
        assert data["current_budget"]["total_expenditures"] == 468_912_088
        assert len(data["current_budget"]["line_items"]) >= 8
        assert len(data["sources"]) >= 4
        assert "budget_story_links" in data
        assert isinstance(data["budget_story_links"], list)
        if data["budget_story_links"]:
            link = data["budget_story_links"][0]
            assert "budget_category" in link
            assert "story_url" in link
            assert "story_title" in link
            assert "mentioned_money" in link
        assert data["fiscal_balance"] is not None
        assert data["fiscal_balance"]["status"] in {
            "balanced",
            "balanced_with_reserves",
            "deficit",
            "surplus",
        }
        assert data["fiscal_balance"]["reserve_draw"] >= 0
        assert len(data["budget_history"]) >= 3
        assert len(data["top_destinations"]) >= 5
        assert any("Sheriff" in d["function_name"] for d in data["top_destinations"])
        assert len(data["transparency_resources"]) >= 4
        assert any(r["category"] == "public_records" for r in data["transparency_resources"])


def test_homepage():
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert b"Government Tracker" in response.content
        assert b"budget-links-table" in response.content
        assert b"Budget" in response.content and b"news links" in response.content
        assert b"Mentioned $" in response.content
        assert b"official-stories-panel" in response.content
        assert b"Where the money goes" in response.content
        assert b"Deficit or surplus" in response.content
        assert b"request records" in response.content
        assert b"mobile-hint" in response.content
        assert b"viewport-fit=cover" in response.content
        # Table should appear before the YoY bar chart section
        html = response.text
        assert html.index("budget-links-panel") < html.index("change-chart")
        assert html.index("exp-chart") < html.index("budget-links-panel")
        assert html.index("fiscal-balance-panel") < html.index("destinations-panel")
        assert html.index("destinations-panel") < html.index("budget-links-panel")
        assert b"destinations-body" in response.content


def test_destinations_include_amounts_for_totals():
    with TestClient(app) as client:
        data = client.get("/api/organizations/new-hanover-county/dashboard").json()
        destinations = data["top_destinations"]
        assert destinations
        assert all("amount" in row for row in destinations)
        assert sum(row["amount"] for row in destinations) > 0
        # prior amounts support the totals-row YoY calculation in the UI
        assert any(row.get("prior_amount") is not None for row in destinations)
