"""Road-network models: RoadNode (graph vertex) and Road (graph edge)."""

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, Boolean, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.core.db import Base


class RoadNode(Base):
    __tablename__ = "road_nodes"

    # OSM node id used directly as the vertex id (not autoincremented).
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    city: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    geom: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=settings.srid, spatial_index=False),
        nullable=False,
    )

    __table_args__ = (Index("ix_road_nodes_geom", "geom", postgresql_using="gist"),)


class Road(Base):
    __tablename__ = "roads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    city: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    osm_way_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    highway: Mapped[str] = mapped_column(String(40), nullable=False)
    source: Mapped[int] = mapped_column(BigInteger, nullable=False)
    target: Mapped[int] = mapped_column(BigInteger, nullable=False)
    length_m: Mapped[float] = mapped_column(Float, nullable=False)
    cost_s: Mapped[float] = mapped_column(Float, nullable=False)
    oneway: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    geom: Mapped[object] = mapped_column(
        Geometry(geometry_type="LINESTRING", srid=settings.srid, spatial_index=False),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_roads_city_source", "city", "source"),
        Index("ix_roads_geom", "geom", postgresql_using="gist"),
    )
