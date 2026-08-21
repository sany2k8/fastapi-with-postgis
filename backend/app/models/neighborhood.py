"""Neighborhood model — a named area with a PostGIS Polygon geometry."""

from geoalchemy2 import Geometry
from sqlalchemy import Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.core.db import Base


class Neighborhood(Base):
    __tablename__ = "neighborhoods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    geom: Mapped[object] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=settings.srid, spatial_index=False),
        nullable=False,
    )

    __table_args__ = (Index("ix_neighborhoods_geom", "geom", postgresql_using="gist"),)
