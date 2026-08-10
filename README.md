# Government Tracker

Track local government budgets against official updates and outside news coverage. Built to run as a Docker container on a Raspberry Pi (or any host), starting with **New Hanover County, NC**.

## Quick start (Raspberry Pi or any Docker host)

```bash
git clone https://github.com/nibrocsolutions/government-tracker.git
cd government-tracker
docker compose up -d --build
```

Open [http://localhost:8000](http://localhost:8000) (or `http://<pi-ip>:8000`).

That’s it—SQLite data persists in a Docker volume, and story collectors refresh on a schedule.

### Useful commands

```bash
# View logs
docker compose logs -f

# Pull latest code and rebuild
git pull && docker compose up -d --build

# Stop
docker compose down
```

## What it does

- Stores organizations (extensible beyond New Hanover County)
- Seeds the **FY 2025–2026 Adopted Budget** (General Fund ~$468.9M, 30.6¢ tax rate) from NHC published figures
- Charts expenditures, revenues, and year-over-year function changes
- Collects stories from:
  - Official NHC CivicAlerts / budget pages ([nhcgov.com](https://www.nhcgov.com/))
  - Local and regional feeds (Port City Daily, WHQR, WECT, Google News for NHC)
- Tags stories to budget themes (education, public safety, human services, taxes, etc.)
- Compares news attention vs budget share

## Local development (without Docker)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
mkdir -p data
DATA_DIR=./data uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API

| Endpoint | Description |
| --- | --- |
| `GET /api/health` | Health check |
| `GET /api/organizations` | List tracked orgs |
| `GET /api/organizations/{slug}/dashboard` | Budget + stories + topic chart data |
| `GET /api/organizations/{slug}/budget` | Budget line items |
| `GET /api/organizations/{slug}/stories` | Stories (`official_only`, `budget_related`) |
| `POST /api/collect` | Trigger a source refresh now |
| `GET /api/collect/status` | Last collection run |

## Configuration

Environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATA_DIR` | `/data` | SQLite directory |
| `PORT` | `8000` | HTTP port |
| `COLLECT_INTERVAL_MINUTES` | `60` | Auto-refresh interval |
| `DATABASE_URL` | `sqlite:///{DATA_DIR}/government_tracker.db` | Override DB |

## Adding another government later

Organizations are first-class records. Seed or insert a new row in `organizations`, attach `budget_years` / `news_sources`, and the dashboard org picker will list it. Collectors already work per enabled source.

## Architecture

- **FastAPI** + SQLAlchemy + SQLite
- **APScheduler** for periodic collection
- Static dashboard (Chart.js) served by the same container
- Multi-arch `python:3.12-slim` image (amd64 / arm64)

## Sources & attribution

Budget numbers are derived from New Hanover County’s publicly posted FY25-26 Adopted Budget materials. News headlines are collected from public pages/feeds; follow each publisher’s terms for production use.
