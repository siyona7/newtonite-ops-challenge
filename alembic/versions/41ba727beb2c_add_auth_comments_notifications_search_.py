"""Add auth, comments, notifications, search vector, and event trigger

Revision ID: 41ba727beb2c
Revises: 6f3ade99d56e
Create Date: 2026-10-19 04:43:11.793577

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '41ba727beb2c'
down_revision: Union[str, Sequence[str], None] = '6f3ade99d56e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add password_hash column to users
    op.add_column('users', sa.Column('password_hash', sa.String(255), nullable=True))

    # Create idempotency_keys table
    op.create_table(
        'idempotency_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('key', sa.String(255), nullable=False),
        sa.Column('endpoint', sa.String(255), nullable=False),
        sa.Column('response_params', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index(op.f('ix_idempotency_keys_key'), 'idempotency_keys', ['key'], unique=True)

    # Create comments table
    op.create_table(
        'comments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('author_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['item_id'], ['items.id'], ondelete='CASCADE'),
    )
    op.create_index(op.f('ix_comments_created_at'), 'comments', ['created_at'])
    op.create_index(op.f('ix_comments_item_id'), 'comments', ['item_id'])

    # Create notifications table
    op.create_table(
        'notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('notification_type', sa.String(), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['item_id'], ['items.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index(op.f('ix_notifications_created_at'), 'notifications', ['created_at'])
    op.create_index(op.f('ix_notifications_is_read'), 'notifications', ['is_read'])
    op.create_index(op.f('ix_notifications_notification_type'), 'notifications', ['notification_type'])
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'])

    # Add search_vector column to items
    op.add_column('items', sa.Column('search_vector', postgresql.TSVECTOR(), nullable=True))

    # Create search vector trigger function
    op.execute("""
        CREATE OR REPLACE FUNCTION items_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(NEW.description, '')), 'B');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create trigger to update search_vector on insert/update
    op.execute("""
        CREATE TRIGGER items_search_vector_trigger
        BEFORE INSERT OR UPDATE ON items
        FOR EACH ROW
        EXECUTE FUNCTION items_search_vector_update();
    """)

    # Create GIN index on search_vector for fast full-text search
    op.create_index('ix_items_search_vector', 'items', ['search_vector'], postgresql_using='gin')

    # Create append-only trigger function for events
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_event_update() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'Events are append-only and cannot be updated or deleted';
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create trigger to prevent updates/deletes on events
    op.execute("""
        CREATE TRIGGER events_append_only_trigger
        BEFORE UPDATE OR DELETE ON events
        FOR EACH ROW
        EXECUTE FUNCTION prevent_event_update();
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS events_append_only_trigger ON events")
    op.execute("DROP FUNCTION IF EXISTS prevent_event_update()")

    op.execute("DROP TRIGGER IF EXISTS items_search_vector_trigger ON items")
    op.execute("DROP FUNCTION IF EXISTS items_search_vector_update()")

    # Drop search vector index and column
    op.drop_index('ix_items_search_vector', table_name='items')
    op.drop_column('items', 'search_vector')

    # Drop notifications table
    op.drop_index(op.f('ix_notifications_user_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_notification_type'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_is_read'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_created_at'), table_name='notifications')
    op.drop_table('notifications')

    # Drop comments table
    op.drop_index(op.f('ix_comments_item_id'), table_name='comments')
    op.drop_index(op.f('ix_comments_created_at'), table_name='comments')
    op.drop_table('comments')

    # Drop idempotency_keys table
    op.drop_index(op.f('ix_idempotency_keys_key'), table_name='idempotency_keys')
    op.drop_table('idempotency_keys')

    # Drop password_hash column from users
    op.drop_column('users', 'password_hash')
