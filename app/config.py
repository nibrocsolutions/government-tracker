from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Government Tracker"
    data_dir: Path = Path("/data")
    database_url: str | None = None
    host: str = "0.0.0.0"
    port: int = 8000
    collect_interval_minutes: int = 60
    user_agent: str = (
        "GovernmentTracker/1.0 (+https://github.com/nibrocsolutions/government-tracker)"
    )

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        db_path = self.data_dir / "government_tracker.db"
        return f"sqlite:///{db_path}"


settings = Settings()
