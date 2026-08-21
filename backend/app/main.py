"""FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import neighborhoods, places, routes
from app.core.config import settings

app = FastAPI(
    title="Places Finder API",
    description="A PostGIS learning app: map-based spatial filtering over POIs.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(places.router, prefix=settings.api_prefix)
app.include_router(neighborhoods.router, prefix=settings.api_prefix)
app.include_router(routes.router, prefix=settings.api_prefix)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
