from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.collectors.runner import run_collection
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.seed import seed_database

STATIC_DIR = Path(__file__).resolve().parent / "static"
scheduler = BackgroundScheduler()


def _scheduled_collect() -> None:
    db = SessionLocal()
    try:
        run_collection(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()

    scheduler.add_job(
        _scheduled_collect,
        "interval",
        minutes=settings.collect_interval_minutes,
        id="collect-stories",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
