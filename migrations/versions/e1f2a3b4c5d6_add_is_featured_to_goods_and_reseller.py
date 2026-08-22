"""add is_featured to goods and reseller_products

Revision ID: e1f2a3b4c5d6
Revises: 9cf7889641d8
Create Date: 2026-07-22 08:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e1f2a3b4c5d6'
down_revision = '9cf7889641d8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'goods' in tables:
        goods_cols = [col['name'] for col in inspector.get_columns('goods')]
        if 'is_featured' not in goods_cols:
            op.add_column('goods', sa.Column('is_featured', sa.Boolean(), nullable=False, server_default='false'))
            op.create_index('ix_goods_is_featured', 'goods', ['is_featured'])

    if 'reseller_products' in tables:
        reseller_cols = [col['name'] for col in inspector.get_columns('reseller_products')]
        if 'is_featured' not in reseller_cols:
            op.add_column('reseller_products', sa.Column('is_featured', sa.Boolean(), nullable=False, server_default='false'))
            op.create_index('ix_reseller_products_is_featured', 'reseller_products', ['is_featured'])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'goods' in tables:
        goods_cols = [col['name'] for col in inspector.get_columns('goods')]
        if 'is_featured' in goods_cols:
            op.drop_index('ix_goods_is_featured', table_name='goods')
            op.drop_column('goods', 'is_featured')

    if 'reseller_products' in tables:
        reseller_cols = [col['name'] for col in inspector.get_columns('reseller_products')]
        if 'is_featured' in reseller_cols:
            op.drop_index('ix_reseller_products_is_featured', table_name='reseller_products')
            op.drop_column('reseller_products', 'is_featured')
