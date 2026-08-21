"""Application configuration, loaded from environment via pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # PostGIS lives in the shared system-wide Postgres instance on :5432,
    # in a dedicated database so this project stays isolated from others.
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/placesfinder"

    # SRID 4326 = WGS84 lon/lat, the standard for GPS coordinates and web maps.
    srid: int = 4326

    api_prefix: str = "/api"
    cors_origins: list[str] = ["http://localhost:5199"]


settings = Settings()
