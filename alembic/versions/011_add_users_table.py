"""
Add users table for password-based authentication.

Revision ID: 011_add_users_table
Revises: 010_change_timestamp_to_minutes
Create Date: 2025-12-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '011_add_users_table'
down_revision = '010_change_timestamp_to_minutes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create users table for authentication.
    """
    op.create_table(
        'users',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text("date_trunc('minute', now())"), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text("date_trunc('minute', now())"), nullable=False),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
        sa.UniqueConstraint('email')
    )

    # Create indexes
    op.create_index('ix_users_username', 'users', ['username'])
    op.create_index('ix_users_email', 'users', ['email'])

    # Create trigger for updated_at
    op.execute("""
        CREATE OR REPLACE FUNCTION update_users_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = date_trunc('minute', now());
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_update_users_updated_at
        BEFORE UPDATE ON users
        FOR EACH ROW
        EXECUTE FUNCTION update_users_updated_at();
    """)

    print("✅ Users table created")


def downgrade() -> None:
    """
    Drop users table.
    """
    op.execute("DROP TRIGGER IF EXISTS trg_update_users_updated_at ON users;")
    op.execute("DROP FUNCTION IF EXISTS update_users_updated_at();")
    op.drop_index('ix_users_email', table_name='users')
    op.drop_index('ix_users_username', table_name='users')
    op.drop_table('users')

    print("❌ Users table dropped")










