"""Add warranty and note fields to goods table

Revision ID: f1a2b3c4d5e6
Revises: b2c3d4e5f6a7
Create Date: 2026-05-14 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'f1a2b3c4d5e6'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add warranty (e.g. "3m", "1y", "lifetime") and note (admin note per product)
    op.add_column('goods', sa.Column('warranty', sa.String(50), nullable=True))
    op.add_column('goods', sa.Column('note', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('goods', 'note')
    op.drop_column('goods', 'warranty')
