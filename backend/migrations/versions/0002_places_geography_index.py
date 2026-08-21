"""add functional GiST index on places.geom::geography

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-21

The radius/nearest queries cast to geography for true metres
(`ST_DWithin(geom::geography, ...)`). The existing geometry index does not
match that expression, so those queries fall back to a sequential scan. A
functional GiST index on the geography expression lets the planner do the
index-assisted candidate lookup (bounding-box skip) before the exact check.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE INDEX ix_places_geog ON places USING gist ((geom::geography))")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_places_geog")
