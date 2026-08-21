"""initial postgis schema: places + neighborhoods with GiST indexes

Revision ID: 0001
Revises:
Create Date: 2026-08-21

Values (SRID 4326, column types) are frozen in this revision on purpose: a
migration must reproduce the same schema regardless of what the app config
says later.
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SRID = 4326


def upgrade() -> None:
    # Idempotent: the DB may already have PostGIS enabled by an operator.
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "places",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("rating", sa.Numeric(precision=2, scale=1), nullable=False),
        sa.Column("price_level", sa.Integer(), nullable=False),
        sa.Column("is_open_24h", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "geom",
            geoalchemy2.types.Geometry(geometry_type="POINT", srid=SRID, spatial_index=False),
            nullable=False,
        ),
    )
    op.create_index("ix_places_category", "places", ["category"])
    op.create_index("ix_places_geom", "places", ["geom"], postgresql_using="gist")

    op.create_table(
        "neighborhoods",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column(
            "geom",
            geoalchemy2.types.Geometry(geometry_type="POLYGON", srid=SRID, spatial_index=False),
            nullable=False,
        ),
    )
    op.create_index("ix_neighborhoods_geom", "neighborhoods", ["geom"], postgresql_using="gist")


def downgrade() -> None:
    op.drop_index("ix_neighborhoods_geom", table_name="neighborhoods")
    op.drop_table("neighborhoods")
    op.drop_index("ix_places_geom", table_name="places")
    op.drop_index("ix_places_category", table_name="places")
    op.drop_table("places")
