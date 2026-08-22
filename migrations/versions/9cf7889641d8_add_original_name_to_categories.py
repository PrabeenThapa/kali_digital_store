"""add original_name to categories

Revision ID: 9cf7889641d8
Revises: dd2345678901
Create Date: 2026-07-20 04:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9cf7889641d8'
down_revision = 'dd2345678901'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if column exists to prevent crash on already-migrated DBs (like ours right now)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('categories')]
    
    if 'original_name' not in columns:
        op.add_column('categories', sa.Column('original_name', sa.String(length=100), nullable=True))
        op.create_unique_constraint('uq_categories_original_name', 'categories', ['original_name'])


def downgrade() -> None:
    op.drop_constraint('uq_categories_original_name', 'categories', type_='unique')
    op.drop_column('categories', 'original_name')
