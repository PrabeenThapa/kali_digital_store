"""Add is_active to categories and sync missing tables and columns

Revision ID: 4e7a8b9c0d1e
Revises: 3532d77c496b
Create Date: 2026-08-17 08:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e7a8b9c0d1e'
down_revision: Union[str, None] = '3532d77c496b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1. categories.is_active
    if 'categories' in tables:
        cat_cols = {col['name'] for col in inspector.get_columns('categories')}
        if 'is_active' not in cat_cols:
            op.add_column('categories', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))
            op.create_index('ix_categories_is_active', 'categories', ['is_active'])

    # 2. users.discount_percent
    if 'users' in tables:
        user_cols = {col['name'] for col in inspector.get_columns('users')}
        if 'discount_percent' not in user_cols:
            op.add_column('users', sa.Column('discount_percent', sa.Numeric(5, 2), nullable=False, server_default='0'))

    # 3. promo_codes columns
    if 'promo_codes' in tables:
        promo_cols = {col['name'] for col in inspector.get_columns('promo_codes')}
        if 'max_uses_per_user' not in promo_cols:
            op.add_column('promo_codes', sa.Column('max_uses_per_user', sa.Integer(), nullable=False, server_default='1'))
        # Ensure discount_type is String(32)
        op.alter_column('promo_codes', 'discount_type',
                        existing_type=sa.String(length=10),
                        type_=sa.String(length=32),
                        existing_nullable=False)

    # 4. support_tickets table
    if 'support_tickets' not in tables:
        op.create_table(
            'support_tickets',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.telegram_id', ondelete='CASCADE'), nullable=False),
            sa.Column('topic_id', sa.Integer(), nullable=False),
            sa.Column('status', sa.String(length=16), nullable=False, server_default='open'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index('ix_support_tickets_user_id', 'support_tickets', ['user_id'])
        op.create_index('ix_support_tickets_user_status', 'support_tickets', ['user_id', 'status'])
        op.create_index('ix_support_tickets_topic', 'support_tickets', ['topic_id'])

    # 5. reseller_sources table
    if 'reseller_sources' not in tables:
        op.create_table(
            'reseller_sources',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(length=64), unique=True, nullable=False),
            sa.Column('base_url', sa.String(length=256), nullable=False),
            sa.Column('api_key', sa.String(length=512), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('last_synced', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    # 6. reseller_products table
    if 'reseller_products' not in tables:
        op.create_table(
            'reseller_products',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('source_id', sa.Integer(), sa.ForeignKey('reseller_sources.id', ondelete='CASCADE'), nullable=False),
            sa.Column('external_id', sa.String(length=128), nullable=False),
            sa.Column('external_code', sa.String(length=128), nullable=True),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('product_type', sa.String(length=32), nullable=False),
            sa.Column('cost_price', sa.Numeric(12, 4), nullable=False),
            sa.Column('sell_price', sa.Numeric(12, 2), nullable=True),
            sa.Column('markup_percent', sa.Numeric(5, 2), nullable=False, server_default='30'),
            sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('is_featured', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('stock', sa.Integer(), nullable=True),
            sa.Column('category_override', sa.String(length=64), nullable=True),
            sa.Column('name_override', sa.String(length=256), nullable=True),
            sa.Column('icon_custom_emoji_id', sa.String(length=64), nullable=True),
            sa.Column('last_synced', sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint('source_id', 'external_id', name='uq_reseller_product')
        )
        op.create_index('ix_reseller_products_source_id', 'reseller_products', ['source_id'])
        op.create_index('ix_reseller_products_enabled', 'reseller_products', ['is_enabled'])
        op.create_index('ix_reseller_products_is_featured', 'reseller_products', ['is_featured'])

    # 7. reseller_orders table
    if 'reseller_orders' not in tables:
        op.create_table(
            'reseller_orders',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('source_id', sa.Integer(), sa.ForeignKey('reseller_sources.id'), nullable=False),
            sa.Column('reseller_product_id', sa.Integer(), sa.ForeignKey('reseller_products.id'), nullable=True),
            sa.Column('bought_goods_id', sa.Integer(), sa.ForeignKey('bought_goods.id', ondelete='SET NULL'), nullable=True),
            sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.telegram_id', ondelete='SET NULL'), nullable=True),
            sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('external_order_id', sa.String(length=256), nullable=True),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
            sa.Column('delivered_codes', sa.Text(), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('charge_amount', sa.Numeric(12, 4), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('fulfilled_at', sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index('ix_reseller_orders_source_id', 'reseller_orders', ['source_id'])
        op.create_index('ix_reseller_orders_user_id', 'reseller_orders', ['user_id'])
        op.create_index('ix_reseller_orders_status', 'reseller_orders', ['status'])
        op.create_index('ix_reseller_orders_user_status', 'reseller_orders', ['user_id', 'status'])
        op.create_index('ix_reseller_orders_created', 'reseller_orders', ['created_at'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if 'reseller_orders' in tables:
        op.drop_table('reseller_orders')
    if 'reseller_products' in tables:
        op.drop_table('reseller_products')
    if 'reseller_sources' in tables:
        op.drop_table('reseller_sources')
    if 'support_tickets' in tables:
        op.drop_table('support_tickets')

    if 'promo_codes' in tables:
        promo_cols = {col['name'] for col in inspector.get_columns('promo_codes')}
        if 'max_uses_per_user' in promo_cols:
            op.drop_column('promo_codes', 'max_uses_per_user')

    if 'users' in tables:
        user_cols = {col['name'] for col in inspector.get_columns('users')}
        if 'discount_percent' in user_cols:
            op.drop_column('users', 'discount_percent')

    if 'categories' in tables:
        cat_cols = {col['name'] for col in inspector.get_columns('categories')}
        if 'is_active' in cat_cols:
            op.drop_index('ix_categories_is_active', table_name='categories')
            op.drop_column('categories', 'is_active')
