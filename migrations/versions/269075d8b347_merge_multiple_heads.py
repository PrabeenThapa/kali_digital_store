"""merge multiple heads

Revision ID: 269075d8b347
Revises: 3f84f5064bc4, c0ba4bb64313
Create Date: 2026-08-14 18:07:15.136071

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '269075d8b347'
down_revision: Union[str, None] = ('3f84f5064bc4', 'c0ba4bb64313')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
