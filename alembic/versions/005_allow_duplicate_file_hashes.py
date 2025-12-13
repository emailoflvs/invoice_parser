"""
Allow duplicate file hashes - each parsing creates a new record.

Revision ID: 005_allow_duplicate_file_hashes
Revises: 004_partition_related_tables
Create Date: 2025-12-13
"""
from alembic import op
import sqlalchemy as sa

revision = '005_allow_duplicate_file_hashes'
down_revision = '004_partition_related_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Remove UNIQUE constraint on file_hash to allow multiple records for the same file.
    This allows saving each parsing as a separate record in the database.
    """
    # Drop the unique index (PostgreSQL creates unique constraints as unique indexes)
    op.execute("DROP INDEX IF EXISTS uq_files_hash;")

    # Ensure regular non-unique index exists for fast lookups
    conn = op.get_bind()
    result = conn.execute(sa.text("""
        SELECT indexname
        FROM pg_indexes
        WHERE tablename = 'files'
        AND indexname = 'ix_files_hash';
    """))

    index_exists = result.fetchone() is not None

    if not index_exists:
        # Create non-unique index if it doesn't exist
        op.execute("""
            CREATE INDEX ix_files_hash ON files (file_hash)
            WHERE file_hash IS NOT NULL;
        """)


def downgrade() -> None:
    """
    Restore UNIQUE constraint on file_hash (if needed for rollback).
    WARNING: This will fail if there are duplicate file_hash values in the table.
    """
    conn = op.get_bind()

    # Check if there are duplicates
    result = conn.execute(sa.text("""
        SELECT file_hash, COUNT(*) as cnt
        FROM files
        WHERE file_hash IS NOT NULL
        GROUP BY file_hash
        HAVING COUNT(*) > 1;
    """))

    duplicates = result.fetchall()

    if duplicates:
        # Cannot restore unique constraint if duplicates exist
        raise Exception(
            f"Cannot restore UNIQUE constraint: found {len(duplicates)} duplicate file_hash values. "
            "Please remove duplicates first."
        )

    # Check if unique index already exists
    result = conn.execute(sa.text("""
        SELECT indexname
        FROM pg_indexes
        WHERE tablename = 'files'
        AND indexname = 'uq_files_hash';
    """))

    index_exists = result.fetchone() is not None

    if not index_exists:
        # Create unique index
        op.execute("""
            CREATE UNIQUE INDEX uq_files_hash ON files (file_hash)
            WHERE file_hash IS NOT NULL;
        """)

