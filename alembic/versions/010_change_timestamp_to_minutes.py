"""
Change timestamp format to minutes only (remove seconds and milliseconds).

Revision ID: 010_change_timestamp_to_minutes
Revises: 009_add_fts_indexes
Create Date: 2025-12-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = '010_change_timestamp_to_minutes'
down_revision = '009_add_fts_indexes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Change all timestamp columns to store only up to minutes (YYYY-MM-DD HH:MM).

    Steps:
    1. Update existing data: truncate to minutes
    2. Change server_default to use date_trunc('minute', now())
    3. Change column type to TIMESTAMP(0) (no fractional seconds)
    """

    # List of all tables with timestamp columns
    # Note: documents, document_snapshots, document_fields, document_table_sections are partitioned
    # Cannot change column type for partitioned tables, only update data and defaults
    partitioned_tables = ['documents', 'document_snapshots', 'document_fields', 'document_table_sections']

    tables_with_timestamps = [
        ('companies', ['created_at', 'updated_at'], False),
        ('company_document_profiles', ['created_at', 'updated_at'], False),
        ('files', ['uploaded_at'], False),
        ('documents', ['created_at', 'updated_at'], True),  # Partitioned
        ('document_pages', ['created_at'], False),
        ('document_snapshots', ['created_at'], True),  # Partitioned
        ('document_fields', ['created_at', 'updated_at'], True),  # Partitioned
        ('document_signatures', ['created_at', 'updated_at'], False),
        ('document_table_sections', ['created_at', 'updated_at'], True),  # Partitioned
    ]

    for table_name, columns, is_partitioned in tables_with_timestamps:
        for column_name in columns:
            # Step 1: Update existing data - truncate to minutes
            op.execute(f"""
                UPDATE {table_name}
                SET {column_name} = date_trunc('minute', {column_name})
                WHERE {column_name} IS NOT NULL;
            """)

            # Step 2: Change column type to TIMESTAMP(0) - only for non-partitioned tables
            if not is_partitioned:
                op.execute(f"""
                    ALTER TABLE {table_name}
                    ALTER COLUMN {column_name} TYPE TIMESTAMP(0)
                    USING date_trunc('minute', {column_name});
                """)

            # Step 3: Change server_default to truncate to minutes
            if column_name == 'updated_at':
                # For updated_at, we need a trigger
                op.execute(f"""
                    CREATE OR REPLACE FUNCTION update_{table_name}_{column_name}()
                    RETURNS TRIGGER AS $$
                    BEGIN
                        NEW.{column_name} = date_trunc('minute', now());
                        RETURN NEW;
                    END;
                    $$ LANGUAGE plpgsql;

                    DROP TRIGGER IF EXISTS trg_update_{table_name}_{column_name} ON {table_name};
                    CREATE TRIGGER trg_update_{table_name}_{column_name}
                    BEFORE UPDATE ON {table_name}
                    FOR EACH ROW
                    EXECUTE FUNCTION update_{table_name}_{column_name}();
                """)
            else:
                # For created_at, change server_default
                op.execute(f"""
                    ALTER TABLE {table_name}
                    ALTER COLUMN {column_name} SET DEFAULT date_trunc('minute', now());
                """)

    print("✅ All timestamps changed to minutes format (YYYY-MM-DD HH:MM)")


def downgrade() -> None:
    """
    Revert to full timestamp with seconds and milliseconds.
    """

    tables_with_timestamps = [
        ('companies', ['created_at', 'updated_at'], False),
        ('company_document_profiles', ['created_at', 'updated_at'], False),
        ('files', ['uploaded_at'], False),
        ('documents', ['created_at', 'updated_at'], True),
        ('document_pages', ['created_at'], False),
        ('document_snapshots', ['created_at'], True),
        ('document_fields', ['created_at', 'updated_at'], True),
        ('document_signatures', ['created_at', 'updated_at'], False),
        ('document_table_sections', ['created_at', 'updated_at'], True),
    ]

    for table_name, columns, is_partitioned in tables_with_timestamps:
        for column_name in columns:
            # Revert column type to TIMESTAMP (with fractional seconds) - only for non-partitioned
            if not is_partitioned:
                op.execute(f"""
                    ALTER TABLE {table_name}
                    ALTER COLUMN {column_name} TYPE TIMESTAMP
                    USING {column_name};
                """)

            # Remove triggers for updated_at
            if column_name == 'updated_at':
                op.execute(f"""
                    DROP TRIGGER IF EXISTS trg_update_{table_name}_{column_name} ON {table_name};
                    DROP FUNCTION IF EXISTS update_{table_name}_{column_name}();
                """)

            # Revert server_default
            op.execute(f"""
                ALTER TABLE {table_name}
                ALTER COLUMN {column_name} SET DEFAULT now();
            """)

    print("❌ Reverted to full timestamp format")

