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


def test_homepage():
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert b"Government Tracker" in response.content
        assert b"budget-links-table" in response.content
        assert b"Budget" in response.content and b"news links" in response.content
        assert b"Mentioned $" in response.content
        assert b"official-stories-panel" in response.content
        # Table should appear before the YoY bar chart section
        html = response.text
        assert html.index("budget-links-panel") < html.index("change-chart")
        assert html.index("exp-chart") < html.index("budget-links-panel")
