"""add price observation type

Revision ID: 2623186894c2
Revises: d20ee2723bbf
Create Date: 2026-08-14 19:59:25.735019
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '2623186894c2'
down_revision: Union[str, None] = 'd20ee2723bbf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'price_observations',
        sa.Column('observation_type', sa.String(length=16), nullable=False, server_default='close'),
    )


def downgrade() -> None:
    op.drop_column('price_observations', 'observation_type')
