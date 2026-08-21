"""Place model — a point-of-interest with a PostGIS Point geometry."""

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Index, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.core.db import Base


class Place(Base):
    __tablename__ = "places"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # cafe / restaurant / shop / park / bar / hotel
    category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    rating: Mapped[float] = mapped_column(Numeric(2, 1), nullable=False)  # 0.0 - 5.0
    price_level: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 - 4
    is_open_24h: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # WGS84 lon/lat point. spatial_index=False here — we create the GiST index
    # explicitly in __table_args__ so its name is stable and visible in migrations.
    geom: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=settings.srid, spatial_index=False),
        nullable=False,
    )

    __table_args__ = (
        # GiST index on the raw geometry — powers bbox (`&&`) viewport queries.
        Index("ix_places_geom", "geom", postgresql_using="gist"),
        # Functional GiST index on the geography cast — powers metre-based
        # radius (`ST_DWithin(geom::geography, ...)`) and nearest (`<->`) queries.
        Index("ix_places_geog", text("(geom::geography)"), postgresql_using="gist"),
    )
