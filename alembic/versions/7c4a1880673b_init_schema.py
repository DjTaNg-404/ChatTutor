"""init schema

Revision ID: 7c4a1880673b
Revises:
Create Date: 2026-04-13 21:44:26.215435

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP, VARCHAR, TEXT, INTEGER, BOOLEAN, ENUM
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = '7c4a1880673b'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
    op.execute('CREATE EXTENSION IF NOT EXISTS "vector";')

    # Create enum types
    note_type = ENUM(
        'daily', 'task', 'summary',
        name='notetype',
        create_type=True
    )
    note_type.create(op.get_bind())

    task_status = ENUM(
        'active', 'archived', 'completed',
        name='taskstatus',
        create_type=True
    )
    task_status.create(op.get_bind())

    # Users table
    op.create_table(
        'users',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('username', VARCHAR(50), unique=True, nullable=False, index=True),
        sa.Column('hashed_password', VARCHAR(255), nullable=False),
        sa.Column('created_at', TIMESTAMP(timezone=True), nullable=False, default=sa.func.now()),
        sa.Column('updated_at', TIMESTAMP(timezone=True), nullable=False, default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Sessions table
    op.create_table(
        'sessions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('session_id', VARCHAR(255), nullable=False, index=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('task_id', VARCHAR(100), nullable=False, index=True),
        sa.Column('topic', VARCHAR(200), nullable=True),
        sa.Column('messages', JSONB, nullable=True),
        sa.Column('conversation_summary', TEXT, nullable=True),
        sa.Column('summarized_msg_count', INTEGER, default=0, nullable=False),
        sa.Column('is_summarizing', BOOLEAN, default=False, nullable=False),
        sa.Column('created_at', TIMESTAMP(timezone=True), nullable=False, default=sa.func.now()),
        sa.Column('updated_at', TIMESTAMP(timezone=True), nullable=False, default=sa.func.now(), onupdate=sa.func.now()),
        sa.Index('ix_sessions_user_task', 'user_id', 'task_id'),
    )

    # Tasks table
    op.create_table(
        'tasks',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('task_id', VARCHAR(100), nullable=False, index=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('title', VARCHAR(200), nullable=True),
        sa.Column('icon', VARCHAR(50), nullable=True),
        sa.Column('status', VARCHAR(20), default='active', nullable=False),
        sa.Column('plan_json', JSONB, nullable=True),
        sa.Column('created_at', TIMESTAMP(timezone=True), nullable=False, default=sa.func.now()),
        sa.Column('updated_at', TIMESTAMP(timezone=True), nullable=False, default=sa.func.now(), onupdate=sa.func.now()),
        sa.Index('ix_tasks_user_task_id', 'user_id', 'task_id', unique=True),
    )

    # Notes table
    op.create_table(
        'notes',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('task_id', VARCHAR(100), nullable=False, index=True),
        sa.Column('session_id', VARCHAR(255), nullable=True),
        sa.Column('note_type', note_type, nullable=False),
        sa.Column('content', TEXT, nullable=False),
        sa.Column('metadata_json', JSONB, nullable=True),
        sa.Column('created_at', TIMESTAMP(timezone=True), nullable=False, default=sa.func.now()),
        sa.Index('ix_notes_user_task_type', 'user_id', 'task_id', 'note_type'),
    )

    # Learner profiles table
    op.create_table(
        'learner_profiles',
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('profile_json', JSONB, nullable=False, default=sa.text("'{}'::jsonb")),
        sa.Column('updated_at', TIMESTAMP(timezone=True), nullable=False, default=sa.func.now(), onupdate=sa.func.now()),
    )

    # KG Graphs table
    op.create_table(
        'kg_graphs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('task_id', VARCHAR(100), nullable=False, index=True),
        sa.Column('graph_data', JSONB, nullable=True),
        sa.Column('metadata_json', JSONB, nullable=True),
        sa.Column('updated_at', TIMESTAMP(timezone=True), nullable=False, default=sa.func.now(), onupdate=sa.func.now()),
        sa.Index('ix_kg_graphs_user_task', 'user_id', 'task_id'),
    )

    # Embeddings table (with pgvector)
    op.create_table(
        'embeddings',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('task_id', VARCHAR(100), nullable=False, index=True),
        sa.Column('session_id', VARCHAR(255), nullable=True),
        sa.Column('content', TEXT, nullable=False),
        sa.Column('embedding', Vector(384), nullable=True),
        sa.Column('metadata_json', JSONB, nullable=True),
        sa.Column('created_at', TIMESTAMP(timezone=True), nullable=False, default=sa.func.now()),
        sa.Index('ix_embeddings_user_task', 'user_id', 'task_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('embeddings')
    op.drop_table('kg_graphs')
    op.drop_table('learner_profiles')
    op.drop_table('notes')
    op.drop_table('tasks')
    op.drop_table('sessions')
    op.drop_table('users')

    # Drop enum types
    op.execute('DROP TYPE IF EXISTS notetype;')
    op.execute('DROP TYPE IF EXISTS taskstatus;')

    # Drop extensions (commented out as it may affect other tables)
    # op.execute('DROP EXTENSION IF EXISTS "vector";')
    # op.execute('DROP EXTENSION IF EXISTS "uuid-ossp";')
