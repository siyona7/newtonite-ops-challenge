"""Initial schema

Revision ID: 6f3ade99d56e
Revises:
Create Date: 2026-10-19 03:31:18.806154

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '6f3ade99d56e'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create teams table
    op.create_table(
        'teams',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index(op.f('ix_teams_name'), 'teams', ['name'], unique=True)

    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # Create team_members junction table
    op.create_table(
        'team_members',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('team_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )

    # Create items table
    op.create_table(
        'items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('team_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('priority', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
    )
    op.create_index(op.f('ix_items_created_at'), 'items', ['created_at'])
    op.create_index(op.f('ix_items_priority_status'), 'items', ['priority', 'status'])
    op.create_index(op.f('ix_items_status'), 'items', ['status'])
    op.create_index(op.f('ix_items_team_id'), 'items', ['team_id'])
    op.create_index(op.f('ix_items_team_status'), 'items', ['team_id', 'status'])
    op.create_index(op.f('ix_items_type'), 'items', ['type'])

    # Create events table
    op.create_table(
        'events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('old_values', postgresql.JSONB(), nullable=True),
        sa.Column('new_values', postgresql.JSONB(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['item_id'], ['items.id'], ondelete='CASCADE'),
    )
    op.create_index(op.f('ix_events_created_at'), 'events', ['created_at'])
    op.create_index(op.f('ix_events_event_type'), 'events', ['event_type'])
    op.create_index(op.f('ix_events_item_id'), 'events', ['item_id'])

    # Create outbox_messages table
    op.create_table(
        'outbox_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('aggregate_type', sa.String(100), nullable=False),
        sa.Column('aggregate_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('dead_letter_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(op.f('ix_outbox_messages_aggregate_id'), 'outbox_messages', ['aggregate_id'])
    op.create_index(op.f('ix_outbox_messages_aggregate_type'), 'outbox_messages', ['aggregate_type'])
    op.create_index(op.f('ix_outbox_messages_created_at'), 'outbox_messages', ['created_at'])
    op.create_index(op.f('ix_outbox_messages_status'), 'outbox_messages', ['status'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_outbox_messages_status'), table_name='outbox_messages')
    op.drop_index(op.f('ix_outbox_messages_created_at'), table_name='outbox_messages')
    op.drop_index(op.f('ix_outbox_messages_aggregate_type'), table_name='outbox_messages')
    op.drop_index(op.f('ix_outbox_messages_aggregate_id'), table_name='outbox_messages')
    op.drop_table('outbox_messages')

    op.drop_index(op.f('ix_events_item_id'), table_name='events')
    op.drop_index(op.f('ix_events_event_type'), table_name='events')
    op.drop_index(op.f('ix_events_created_at'), table_name='events')
    op.drop_table('events')

    op.drop_index(op.f('ix_items_type'), table_name='items')
    op.drop_index(op.f('ix_items_team_status'), table_name='items')
    op.drop_index(op.f('ix_items_team_id'), table_name='items')
    op.drop_index(op.f('ix_items_status'), table_name='items')
    op.drop_index(op.f('ix_items_priority_status'), table_name='items')
    op.drop_index(op.f('ix_items_created_at'), table_name='items')
    op.drop_table('items')

    op.drop_table('team_members')

    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')

    op.drop_index(op.f('ix_teams_name'), table_name='teams')
    op.drop_table('teams')
