"""road network tables for routing: road_nodes + roads (edges)

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-21

A routable graph built from OpenStreetMap:
  * road_nodes  = graph vertices (OSM node id + point geometry)
  * roads       = graph edges (a straight segment between two nodes, with a
                  travel-time cost and a geometry)

We route with our own Dijkstra/A* in Python (pgRouting isn't installed), so
these tables only need: the topology columns (source/target), the cost, a
city label to keep the three networks separate, and GiST-indexed geometry for
nearest-node snapping and GeoJSON output.
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SRID = 4326


def upgrade() -> None:
    op.create_table(
        "road_nodes",
        # OSM node id (a large bigint) used directly as the vertex id.
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("city", sa.String(length=40), nullable=False),
        sa.Column(
            "geom",
            geoalchemy2.types.Geometry(geometry_type="POINT", srid=SRID, spatial_index=False),
            nullable=False,
        ),
    )
    op.create_index("ix_road_nodes_city", "road_nodes", ["city"])
    op.create_index("ix_road_nodes_geom", "road_nodes", ["geom"], postgresql_using="gist")

    op.create_table(
        "roads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("city", sa.String(length=40), nullable=False),
        sa.Column("osm_way_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("highway", sa.String(length=40), nullable=False),
        sa.Column("source", sa.BigInteger(), nullable=False),  # road_nodes.id
        sa.Column("target", sa.BigInteger(), nullable=False),  # road_nodes.id
        sa.Column("length_m", sa.Float(), nullable=False),
        sa.Column("cost_s", sa.Float(), nullable=False),  # travel time, seconds
        sa.Column("oneway", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "geom",
            geoalchemy2.types.Geometry(geometry_type="LINESTRING", srid=SRID, spatial_index=False),
            nullable=False,
        ),
    )
    op.create_index("ix_roads_city", "roads", ["city"])
    op.create_index("ix_roads_city_source", "roads", ["city", "source"])
    op.create_index("ix_roads_geom", "roads", ["geom"], postgresql_using="gist")


def downgrade() -> None:
    op.drop_index("ix_roads_geom", table_name="roads")
    op.drop_index("ix_roads_city_source", table_name="roads")
    op.drop_index("ix_roads_city", table_name="roads")
    op.drop_table("roads")
    op.drop_index("ix_road_nodes_geom", table_name="road_nodes")
    op.drop_index("ix_road_nodes_city", table_name="road_nodes")
    op.drop_table("road_nodes")
