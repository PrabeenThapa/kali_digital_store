import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Column, Integer, String, BigInteger, ForeignKey, Text, Boolean,
    DateTime, Numeric, Index, UniqueConstraint, CheckConstraint, func, select
)
from packages.database.engine import Database
from sqlalchemy.orm import relationship


class PaymentStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EXPIRED = "expired"
    ACTIVE = "active"


class PaymentProvider(StrEnum):
    CRYPTOPAY = "cryptopay"
    STARS = "stars"
    BYBIT = "bybit"
    BINANCE = "binance"
    BEP20 = "bep20"
    TRC20 = "trc20"
    BALANCE = "balance"


class ProductType(StrEnum):
    ACCOUNT = "account"
    PREORDER = "preorder"
    TEAM_INVITE = "team_invite"


class DiscountType(StrEnum):
    PERCENT = "percent"
    FIXED = "fixed"
    BALANCE = "balance"


class Permission:
    USE             = 1 << 0   #   1 — basic access
    BROADCAST       = 1 << 1   #   2 — mass messaging
    SETTINGS_MANAGE = 1 << 2   #   4 — bot settings (maintenance, etc.)
    USERS_MANAGE    = 1 << 3   #   8 — view/block/unblock users, referrals, purchases
    CATALOG_MANAGE  = 1 << 4   #  16 — categories, positions, items/goods CRUD
    ADMINS_MANAGE   = 1 << 5   #  32 — role CRUD, role assignment
    OWN             = 1 << 6   #  64 — owner-only operations
    STATS_VIEW      = 1 << 7   # 128 — statistics, logs, bought-item search
    BALANCE_MANAGE  = 1 << 8   # 256 — top-up / deduct user balance
    PROMO_MANAGE    = 1 << 9   # 512 — promo code CRUD

    @staticmethod
    def is_subset(perms: int, of: int) -> bool:
        """True if every bit in `perms` is also set in `of`."""
        return (perms & ~of) == 0

    @staticmethod
    def has_any_admin_perm(perms: int) -> bool:
        """True if `perms` has any permission beyond USE."""
        return (perms & ~Permission.USE) != 0


class Role(Database.BASE):
    __tablename__ = 'roles'
    id = Column(Integer, primary_key=True)
    name = Column(String(64), unique=True)
    default = Column(Boolean, default=False, index=True)
    permissions = Column(Integer)
    users = relationship('User', backref='role', lazy='raise')

    def __init__(self, name: str, permissions=None, **kwargs):
        super(Role, self).__init__(**kwargs)
        if self.permissions is None:
            self.permissions = 0
        self.name = name
        self.permissions = permissions

    @staticmethod
    async def insert_roles():
        roles = {
            'USER': [Permission.USE],
            'ADMIN': [Permission.USE, Permission.BROADCAST,
                      Permission.SETTINGS_MANAGE, Permission.USERS_MANAGE,
                      Permission.CATALOG_MANAGE, Permission.STATS_VIEW,
                      Permission.BALANCE_MANAGE, Permission.PROMO_MANAGE],
            'OWNER': [Permission.USE, Permission.BROADCAST,
                      Permission.SETTINGS_MANAGE, Permission.USERS_MANAGE,
                      Permission.CATALOG_MANAGE, Permission.ADMINS_MANAGE,
                      Permission.OWN, Permission.STATS_VIEW,
                      Permission.BALANCE_MANAGE, Permission.PROMO_MANAGE],
        }
        default_role = 'USER'
        async with Database().session() as s:
            for r, perms in roles.items():
                result = await s.execute(select(Role).filter_by(name=r))
                role = result.scalars().first()
                if role is None:
                    role = Role(name=r)
                    s.add(role)
                role.reset_permissions()
                for perm in perms:
                    role.add_permission(perm)
                role.default = (role.name == default_role)

    def add_permission(self, perm):
        self.permissions |= perm

    def remove_permission(self, perm):
        self.permissions &= ~perm

    def reset_permissions(self):
        self.permissions = 0

    def has_permission(self, perm):
        return self.permissions & perm == perm

    def __repr__(self):
        return '<Role %r>' % self.name


class User(Database.BASE):
    __tablename__ = 'users'
    telegram_id = Column(BigInteger, primary_key=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=True)
    role_id = Column(Integer, ForeignKey('roles.id', ondelete="RESTRICT"), default=1, index=True)
    balance = Column(Numeric(12, 2), nullable=False, default=0)
    referral_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete="SET NULL"), nullable=True, index=True)
    registration_date = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    is_blocked = Column(Boolean, default=False, index=True)
    discount_percent = Column(Numeric(5, 2), nullable=False, default=0)  # Account upgrade: % off all purchases
    user_operations = relationship("Operations", back_populates="user_telegram_id", lazy='raise')
    user_goods = relationship("BoughtGoods", back_populates="user_telegram_id", lazy='raise')

    __table_args__ = (
        CheckConstraint('referral_id != telegram_id', name='ck_users_no_self_referral'),
        Index('ix_users_registration_date', 'registration_date'),
    )

    referral_earnings_received = relationship(
        "ReferralEarnings",
        foreign_keys="ReferralEarnings.referrer_id",
        back_populates="referrer",
        lazy='raise',
    )
    referral_earnings_generated = relationship(
        "ReferralEarnings",
        foreign_keys="ReferralEarnings.referral_id",
        back_populates="referral",
        lazy='raise',
    )

    def __init__(self, telegram_id: int, registration_date: datetime.datetime, balance=0, referral_id=None,
                 role_id: int = 1, **kw: Any):
        super().__init__(**kw)
        self.telegram_id = telegram_id
        self.role_id = role_id
        self.balance = balance
        self.referral_id = referral_id
        self.registration_date = registration_date


class Categories(Database.BASE):
    __tablename__ = 'categories'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    original_name = Column(String(100), unique=True, nullable=True)
    banner_file_id = Column(String(256), nullable=True)   # Telegram file_id of category GIF/animation
    icon_custom_emoji_id = Column(String(64), nullable=True) # Telegram custom emoji ID for inline keyboard
    is_active = Column(Boolean, nullable=False, default=True, server_default='true', index=True) # Admin enable/disable category
    items = relationship("Goods", back_populates="category", lazy='raise')

    def __init__(self, name: str, original_name: str | None = None, **kw: Any):
        super().__init__(**kw)
        self.name = name
        self.original_name = original_name


class Goods(Database.BASE):
    __tablename__ = 'goods'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    price = Column(Numeric(12, 2), nullable=False)
    price_npr = Column(Numeric(12, 2), nullable=True)
    cost_price = Column(Numeric(12, 2), nullable=False, default=0)
    description = Column(Text, nullable=False)
    category_id = Column(Integer, ForeignKey('categories.id', ondelete="CASCADE"), nullable=False, index=True)
    warranty = Column(String(50), nullable=True)   # e.g. "3m", "1y", "lifetime"
    note = Column(Text, nullable=True)             # Admin note shown to user
    is_featured = Column(Boolean, nullable=False, default=False, index=True)  # Show in featured section
    is_hot = Column(Boolean, nullable=False, default=False, server_default='false', index=True)
    is_bestseller = Column(Boolean, nullable=False, default=False, server_default='false', index=True)
    badge_text = Column(String(32), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default='true', index=True)
    auto_delivery = Column(Boolean, nullable=False, default=True, server_default='true', index=True)
    delivery_template = Column(Text, nullable=True) # Custom template with {product_name}, {credentials}, {warranty}, etc.
    delivery_type = Column(String(32), nullable=False, default='instant', server_default="'instant'") # 'instant' | 'manual'
    account_type = Column(String(64), nullable=False, default='preactivated', server_default="'preactivated'") # 'preactivated' | 'existing_account' | 'key' | 'invite'
    icon_custom_emoji_id = Column(String(64), nullable=True) # Telegram custom emoji ID for inline keyboard
    category = relationship("Categories", back_populates="items", lazy='raise')
    values = relationship("ItemValues", back_populates="item", lazy='raise')

    def __init__(self, name: str, price, description: str, category_id: int,
                 warranty: str = None, note: str = None, is_featured: bool = False, cost_price = 0,
                 is_hot: bool = False, is_bestseller: bool = False, badge_text: str = None, is_active: bool = True,
                 price_npr = None, auto_delivery: bool = True, delivery_template: str = None,
                 delivery_type: str = 'instant', account_type: str = 'preactivated', **kw: Any):
        super().__init__(**kw)
        self.name = name
        self.price = price
        self.price_npr = price_npr
        self.cost_price = cost_price
        self.description = description
        self.category_id = category_id
        self.warranty = warranty
        self.note = note
        self.is_featured = is_featured
        self.is_hot = is_hot
        self.is_bestseller = is_bestseller
        self.badge_text = badge_text
        self.is_active = is_active
        self.auto_delivery = auto_delivery
        self.delivery_template = delivery_template
        self.delivery_type = delivery_type
        self.account_type = account_type


class ItemValues(Database.BASE):
    __tablename__ = 'item_values'
    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey('goods.id', ondelete="CASCADE"), nullable=False, index=True)
    value = Column(Text, nullable=True)
    is_infinity = Column(Boolean, nullable=False)
    item = relationship("Goods", back_populates="values", lazy='raise')

    __table_args__ = (
        UniqueConstraint('item_id', 'value', name='uq_item_value_per_item'),
        Index('ix_item_values_item_inf', 'item_id', 'is_infinity'),
    )

    def __init__(self, item_id: int, value: str, is_infinity: bool, **kw: Any):
        super().__init__(**kw)
        self.item_id = item_id
        self.value = value
        self.is_infinity = is_infinity


class BoughtGoods(Database.BASE):
    __tablename__ = 'bought_goods'
    id = Column(Integer, primary_key=True)
    item_name = Column(String(100), nullable=False, index=True)
    value = Column(Text, nullable=False)
    price = Column(Numeric(12, 2), nullable=False)
    cost_price = Column(Numeric(12, 2), nullable=False, default=0)
    buyer_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete="SET NULL"), nullable=True, index=True)
    customer_email = Column(String(255), nullable=True)
    delivery_status = Column(String(32), nullable=False, default='delivered', server_default="'delivered'")
    bought_datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    unique_id = Column(BigInteger, nullable=False, unique=True)
    user_telegram_id = relationship("User", back_populates="user_goods", lazy='raise')

    __table_args__ = (
        Index('ix_bought_goods_datetime', 'bought_datetime'),
        Index('ix_bought_goods_buyer_datetime', 'buyer_id', 'bought_datetime'),
    )

    def __init__(self, name: str, value: str, price, bought_datetime, unique_id, buyer_id: int = 0, cost_price = 0, customer_email: str = None, delivery_status: str = 'delivered', **kw: Any):
        super().__init__(**kw)
        self.item_name = name
        self.value = value
        self.price = price
        self.cost_price = cost_price
        self.buyer_id = buyer_id
        self.customer_email = customer_email
        self.delivery_status = delivery_status
        self.bought_datetime = bought_datetime
        self.unique_id = unique_id


class Operations(Database.BASE):
    __tablename__ = 'operations'
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete="SET NULL"), nullable=True, index=True)
    operation_value = Column(Numeric(12, 2), nullable=False)
    operation_time = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    user_telegram_id = relationship("User", back_populates="user_operations", lazy='raise')

    __table_args__ = (
        Index('ix_operations_time', 'operation_time'),
    )

    def __init__(self, user_id: int, operation_value, operation_time, **kw: Any):
        super().__init__(**kw)
        self.user_id = user_id
        self.operation_value = operation_value
        self.operation_time = operation_time


class Payments(Database.BASE):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    provider = Column(String(32), nullable=False, index=True)
    external_id = Column(String(128), nullable=False)
    user_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete="SET NULL"), nullable=True, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(8), nullable=False)
    status = Column(String(16), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('provider', 'external_id', name='uq_payment_provider_ext'),
        Index('ix_payments_status_created', 'status', 'created_at'),
    )


class ReferralEarnings(Database.BASE):
    __tablename__ = 'referral_earnings'

    id = Column(Integer, primary_key=True)
    referrer_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete="CASCADE"), nullable=False, index=True)
    referral_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    original_amount = Column(Numeric(12, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    referrer = relationship(
        "User",
        foreign_keys="ReferralEarnings.referrer_id",
        back_populates="referral_earnings_received",
        lazy='raise',
    )
    referral = relationship(
        "User",
        foreign_keys="ReferralEarnings.referral_id",
        back_populates="referral_earnings_generated",
        lazy='raise',
    )

    __table_args__ = (
        CheckConstraint('referrer_id != referral_id', name='ck_referral_earnings_no_self_referral'),
        Index('ix_referral_earnings_referrer_created', 'referrer_id', 'created_at'),
        Index('ix_referral_earnings_referral_created', 'referral_id', 'created_at'),
    )

    def __init__(self, referrer_id: int, referral_id: int, amount, original_amount, **kw: Any):
        super().__init__(**kw)
        self.referrer_id = referrer_id
        self.referral_id = referral_id
        self.amount = amount
        self.original_amount = original_amount


class AuditLog(Database.BASE):
    __tablename__ = 'audit_log'
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    level = Column(String(8), nullable=False, default="INFO")
    user_id = Column(BigInteger, nullable=True)
    action = Column(String(64), nullable=False)
    resource_type = Column(String(32), nullable=True)
    resource_id = Column(String(128), nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)

    __table_args__ = (
        Index('ix_audit_log_timestamp', 'timestamp'),
        Index('ix_audit_log_user_id', 'user_id'),
        Index('ix_audit_log_action', 'action'),
    )

    def __repr__(self):
        return f'<AuditLog {self.action} user={self.user_id} @ {self.timestamp}>'


class PromoCodes(Database.BASE):
    __tablename__ = 'promo_codes'
    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    discount_type = Column(String(32), nullable=False)  # 'percent' | 'fixed' | 'balance' | 'account_upgrade'
    discount_value = Column(Numeric(12, 2), nullable=False)
    max_uses = Column(Integer, nullable=False, default=0)  # 0 = unlimited total uses
    max_uses_per_user = Column(Integer, nullable=False, default=1)  # 0 = unlimited per user, 1 = once per user, N = up to N uses
    current_uses = Column(Integer, nullable=False, default=0)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    category_id = Column(Integer, ForeignKey('categories.id', ondelete='SET NULL'), nullable=True)
    item_id = Column(Integer, ForeignKey('goods.id', ondelete='SET NULL'), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PromoCodeUsages(Database.BASE):
    __tablename__ = 'promo_code_usages'
    id = Column(Integer, primary_key=True)
    promo_id = Column(Integer, ForeignKey('promo_codes.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CartItems(Database.BASE):
    __tablename__ = 'cart_items'
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), nullable=False, index=True)
    item_name = Column(String(100), nullable=False)
    promo_code = Column(String(50), nullable=True)
    added_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())



class Reviews(Database.BASE):
    __tablename__ = 'reviews'
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), nullable=False, index=True)
    item_name = Column(String(100), nullable=False, index=True)
    rating = Column(Integer, nullable=False)  # 1-5
    text = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        UniqueConstraint('user_id', 'item_name', name='uq_review_per_user_item'),
        CheckConstraint('rating >= 1 AND rating <= 5', name='ck_review_rating_range'),
    )


class SupportTicket(Database.BASE):
    """Maps each user to their Forum Topic thread in the support supergroup."""
    __tablename__ = 'support_tickets'
    id         = Column(Integer, primary_key=True)
    user_id    = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), nullable=False, index=True)
    topic_id   = Column(Integer, nullable=False)   # Telegram forum thread_id
    status     = Column(String(16), nullable=False, default='open')   # open | closed
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    __table_args__ = (
        Index('ix_support_tickets_user_status', 'user_id', 'status'),
        Index('ix_support_tickets_topic', 'topic_id'),
    )

    def __init__(self, user_id: int, topic_id: int, **kw):
        super().__init__(**kw)
        self.user_id  = user_id
        self.topic_id = topic_id
        self.status   = 'open'


class SupportMessage(Database.BASE):
    """Live interactive chat messages between customer and support team."""
    __tablename__ = 'support_messages'
    id         = Column(Integer, primary_key=True)
    user_id    = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), nullable=False, index=True)
    sender     = Column(String(16), nullable=False, default='user')  # 'user' | 'admin' | 'system'
    sender_name = Column(String(128), nullable=True)
    message    = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index('ix_support_messages_user_created', 'user_id', 'created_at'),
    )

    def __init__(self, user_id: int, message: str, sender: str = 'user', sender_name: str = None, **kw):
        super().__init__(**kw)
        self.user_id = user_id
        self.message = message
        self.sender = sender
        self.sender_name = sender_name


class ResellerSource(Database.BASE):
    """An external reseller API source (ForkPixel, CGPT, etc.)."""
    __tablename__ = 'reseller_sources'
    id          = Column(Integer, primary_key=True)
    name        = Column(String(64), unique=True, nullable=False)   # "forkpixel" | "cgpt"
    base_url    = Column(String(256), nullable=False)
    api_key     = Column(String(512), nullable=False)
    is_active   = Column(Boolean, nullable=False, default=True)
    last_synced = Column(DateTime(timezone=True), nullable=True)
    created_at  = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    products    = relationship("ResellerProduct", back_populates="source", lazy='raise', cascade="all, delete-orphan")

    def __init__(self, name: str, base_url: str, api_key: str, **kw):
        super().__init__(**kw)
        self.name = name
        self.base_url = base_url
        self.api_key = api_key


class ResellerProduct(Database.BASE):
    """Cached product from an external reseller API with admin-overridable sell price."""
    __tablename__ = 'reseller_products'
    id               = Column(Integer, primary_key=True)
    source_id        = Column(Integer, ForeignKey('reseller_sources.id', ondelete='CASCADE'), nullable=False, index=True)
    external_id      = Column(String(128), nullable=False)    # product ID on external API
    external_code    = Column(String(128), nullable=True)     # product code (ForkPixel "code" field)
    name             = Column(String(200), nullable=False)
    description      = Column(Text, nullable=True)
    description_override = Column(Text, nullable=True)
    product_type     = Column(String(32), nullable=False)     # "account" | "preorder" | "team_invite"
    cost_price       = Column(Numeric(12, 4), nullable=False) # wholesale price in USD
    sell_price       = Column(Numeric(12, 2), nullable=True)  # NULL = auto (cost * markup_percent)
    price_npr        = Column(Numeric(12, 2), nullable=True)  # Explicit NPR price
    markup_percent   = Column(Numeric(5, 2), nullable=False, default=30)
    is_enabled       = Column(Boolean, nullable=False, default=True, index=True)
    is_featured      = Column(Boolean, nullable=False, default=False, index=True)  # Show in featured section
    is_hot           = Column(Boolean, nullable=False, default=False, index=True)
    is_bestseller    = Column(Boolean, nullable=False, default=False, index=True)
    badge_text       = Column(String(32), nullable=True)
    auto_delivery    = Column(Boolean, nullable=False, default=True, server_default='true', index=True)
    delivery_template = Column(Text, nullable=True)
    delivery_type    = Column(String(32), nullable=False, default='instant', server_default="'instant'") # 'instant' | 'manual'
    account_type     = Column(String(64), nullable=False, default='preactivated', server_default="'preactivated'") # 'preactivated' | 'existing_account' | 'key' | 'invite'
    stock            = Column(Integer, nullable=True)          # NULL = preorder / preorder item
    category_override = Column(String(64), nullable=True)      # NULL = auto-derive from name
    name_override = Column(String(256), nullable=True)
    icon_custom_emoji_id = Column(String(64), nullable=True)
    last_synced      = Column(DateTime(timezone=True), nullable=True)

    source = relationship("ResellerSource", back_populates="products", lazy='raise')

    __table_args__ = (
        UniqueConstraint('source_id', 'external_id', name='uq_reseller_product'),
        Index('ix_reseller_products_enabled', 'is_enabled'),
    )

    def __init__(self, source_id: int, external_id: str, name: str, product_type: str,
                 cost_price, markup_percent=30, external_code: str = None,
                 description: str = None, stock: int = None, price_npr = None,
                 auto_delivery: bool = True, delivery_template: str = None,
                 delivery_type: str = 'instant', account_type: str = 'preactivated', **kw):
        super().__init__(**kw)
        self.source_id = source_id
        self.external_id = external_id
        self.external_code = external_code
        self.name = name
        self.description = description
        self.product_type = product_type
        self.cost_price = cost_price
        self.markup_percent = markup_percent
        self.stock = stock
        self.price_npr = price_npr
        self.auto_delivery = auto_delivery
        self.delivery_template = delivery_template
        self.delivery_type = delivery_type
        self.account_type = account_type

    @property
    def effective_name(self) -> str:
        """Returns the overridden name if set, else the API name."""
        return self.name_override if self.name_override else self.name

    @property
    def effective_description(self) -> str:
        """Returns the overridden description if set, else API description."""
        return self.description_override if self.description_override else (self.description or "")

    @property
    def effective_sell_price(self) -> float:
        """Returns the actual price to charge users (USD) with min 30% margin and 0.25 step."""
        if self.sell_price is not None:
            return float(self.sell_price)
        from packages.services.pricing import calculate_sell_price
        return calculate_sell_price(self.cost_price, self.markup_percent if self.markup_percent is not None else 30)

    @property
    def effective_category(self) -> str:
        """Admin category override if set, else auto-derived from the name."""
        if self.category_override:
            return self.category_override
        from apps.telegram_bot.utils.category_resolver import resolve_category
        return resolve_category(self.effective_name)

class ResellerOrder(Database.BASE):
    """Tracks an order placed on an external reseller API for a user purchase."""
    __tablename__ = 'reseller_orders'
    id                = Column(Integer, primary_key=True)
    source_id         = Column(Integer, ForeignKey('reseller_sources.id'), nullable=False, index=True)
    reseller_product_id = Column(Integer, ForeignKey('reseller_products.id'), nullable=True)
    bought_goods_id   = Column(Integer, ForeignKey('bought_goods.id', ondelete='SET NULL'), nullable=True)
    user_id           = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='SET NULL'), nullable=True, index=True)
    customer_email    = Column(String(255), nullable=True)
    quantity          = Column(Integer, nullable=False, default=1)
    external_order_id = Column(String(256), nullable=True)    # order code/ID returned by API
    status            = Column(String(32), nullable=False, default='pending', index=True)
    # pending | placed | delivered | failed | refunded
    delivered_codes   = Column(Text, nullable=True)   # JSON list of credential strings
    error_message     = Column(Text, nullable=True)
    charge_amount     = Column(Numeric(12, 4), nullable=True)  # amount actually charged to reseller wallet
    created_at        = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fulfilled_at      = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index('ix_reseller_orders_user_status', 'user_id', 'status'),
        Index('ix_reseller_orders_created', 'created_at'),
    )

    def __init__(self, source_id: int, user_id: int, quantity: int = 1,
                 reseller_product_id: int = None, bought_goods_id: int = None,
                 charge_amount=None, customer_email: str = None, **kw):
        super().__init__(**kw)
        self.source_id = source_id
        self.reseller_product_id = reseller_product_id
        self.bought_goods_id = bought_goods_id
        self.user_id = user_id
        self.customer_email = customer_email
        self.quantity = quantity
        self.charge_amount = charge_amount


class ResellerTopUp(Database.BASE):
    """Tracks manual or automated balance top-ups into external reseller provider accounts."""
    __tablename__ = 'reseller_topups'
    id          = Column(Integer, primary_key=True, autoincrement=True)
    source_id   = Column(Integer, ForeignKey('reseller_sources.id', ondelete='CASCADE'), nullable=False, index=True)
    amount      = Column(Numeric(12, 4), nullable=False) # e.g. 50.00 USD
    currency    = Column(String(8), nullable=False, default='USD')
    payment_method = Column(String(64), nullable=True) # e.g. USDT TRC20, CryptoPay, Card
    note        = Column(Text, nullable=True)
    tx_hash     = Column(String(256), nullable=True)
    created_at  = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)

    source = relationship("ResellerSource", lazy='joined')


class BotSettings(Database.BASE):
    """Key-value store for global settings like Nepal QR Code, payment details, and website text."""
    __tablename__ = 'bot_settings'
    key   = Column(String(128), primary_key=True)
    value = Column(Text, nullable=True)


class ProductReview(Database.BASE):
    """Customer ratings and text reviews for products (both local and reseller)."""
    __tablename__ = 'product_reviews'
    id          = Column(Integer, primary_key=True, autoincrement=True)
    product_id  = Column(String(64), nullable=False, index=True) # e.g. "local_1" or "reseller_5"
    user_id     = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), nullable=False, index=True)
    user_name   = Column(String(128), nullable=True)
    rating      = Column(Integer, nullable=False, default=5) # 1-5
    comment     = Column(Text, nullable=False)
    created_at  = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user = relationship("User", lazy='joined')


class ProductUpvote(Database.BASE):
    """Customer upvotes/likes for products."""
    __tablename__ = 'product_upvotes'
    id          = Column(Integer, primary_key=True, autoincrement=True)
    product_id  = Column(String(64), nullable=False, index=True) # e.g. "local_1" or "reseller_5"
    user_id     = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), nullable=False, index=True)
    created_at  = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('product_id', 'user_id', name='uq_product_user_upvote'),
    )


async def register_models():
    async with Database().engine.begin() as conn:
        await conn.run_sync(Database.BASE.metadata.create_all)
    await Role.insert_roles()

