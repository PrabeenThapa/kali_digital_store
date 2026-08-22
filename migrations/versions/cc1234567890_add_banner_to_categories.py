"""Add banner_file_id to categories table

Revision ID: cc1234567890
Revises: f1a2b3c4d5e6
Create Date: 2026-03-09 23:05:42.294758

"""
from alembic import op
import sqlalchemy as sa

revision = 'cc1234567890'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('categories', sa.Column('banner_file_id', sa.String(256), nullable=True))


def downgrade():
    op.drop_column('categories', 'banner_file_id')
