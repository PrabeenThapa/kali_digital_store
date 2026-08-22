"""Add category_override to reseller_products table

Revision ID: dd2345678901
Revises: cc1234567890
Create Date: 2026-07-10 00:00:00.000000

Note: reseller_products is created by SQLAlchemy create_all (not Alembic),
and `alembic upgrade head` runs before create_all in the docker entrypoint.
So this migration is defensive: it no-ops if the table or column is absent/present.
"""
from alembic import op
import sqlalchemy as sa

revision = 'dd2345678901'
down_revision = 'cc1234567890'
branch_labels = None
depends_on = None


def _has_column(inspector, table: str, column: str) -> bool:
    if table not in inspector.get_table_names():
        return False
    return column in {c['name'] for c in inspector.get_columns(table)}


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if 'reseller_products' not in inspector.get_table_names():
        # Table not created yet (fresh DB) — create_all will build it with the column.
        return
    if not _has_column(inspector, 'reseller_products', 'category_override'):
        op.add_column('reseller_products', sa.Column('category_override', sa.String(64), nullable=True))


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if _has_column(inspector, 'reseller_products', 'category_override'):
        op.drop_column('reseller_products', 'category_override')
