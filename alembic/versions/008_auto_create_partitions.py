"""
Auto-create partitions for documents table.

Revision ID: 008_auto_create_partitions
Revises: 007_add_section_label
Create Date: 2025-12-13
"""
from alembic import op
import sqlalchemy as sa

revision = '008_auto_create_partitions'
down_revision = '007_add_section_label'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create function and trigger to automatically create partitions for documents table.
    This ensures new year partitions are created automatically without manual intervention.
    """
    # Create function to auto-create partition if needed
    op.execute("""
        CREATE OR REPLACE FUNCTION create_documents_partition_if_needed()
        RETURNS trigger AS $$
        DECLARE
            partition_year INT;
            partition_name TEXT;
            partition_start DATE;
            partition_end DATE;
        BEGIN
            partition_year := EXTRACT(YEAR FROM NEW.created_at);
            partition_name := 'documents_' || partition_year;

            -- Check if partition exists
            IF NOT EXISTS (
                SELECT 1 FROM pg_class WHERE relname = partition_name
            ) THEN
                partition_start := DATE(partition_year || '-01-01');
                partition_end := DATE((partition_year + 1) || '-01-01');

                EXECUTE format('CREATE TABLE %I PARTITION OF documents FOR VALUES FROM (%L) TO (%L)',
                               partition_name, partition_start, partition_end);

                RAISE NOTICE 'Auto-created partition % for year %', partition_name, partition_year;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create trigger (BEFORE INSERT to create partition before data insertion)
    op.execute("""
        CREATE TRIGGER trg_auto_create_documents_partition
        BEFORE INSERT ON documents
        FOR EACH ROW
        EXECUTE FUNCTION create_documents_partition_if_needed();
    """)

    # Also create function for document_snapshots (same logic)
    op.execute("""
        CREATE OR REPLACE FUNCTION create_snapshots_partition_if_needed()
        RETURNS trigger AS $$
        DECLARE
            partition_year INT;
            partition_name TEXT;
            partition_start DATE;
            partition_end DATE;
        BEGIN
            partition_year := EXTRACT(YEAR FROM NEW.created_at);
            partition_name := 'document_snapshots_' || partition_year;

            IF NOT EXISTS (
                SELECT 1 FROM pg_class WHERE relname = partition_name
            ) THEN
                partition_start := DATE(partition_year || '-01-01');
                partition_end := DATE((partition_year + 1) || '-01-01');

                EXECUTE format('CREATE TABLE %I PARTITION OF document_snapshots FOR VALUES FROM (%L) TO (%L)',
                               partition_name, partition_start, partition_end);

                RAISE NOTICE 'Auto-created partition % for year %', partition_name, partition_year;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_auto_create_snapshots_partition
        BEFORE INSERT ON document_snapshots
        FOR EACH ROW
        EXECUTE FUNCTION create_snapshots_partition_if_needed();
    """)


def downgrade() -> None:
    """Remove auto-partition triggers and functions"""
    op.execute("DROP TRIGGER IF EXISTS trg_auto_create_documents_partition ON documents;")
    op.execute("DROP FUNCTION IF EXISTS create_documents_partition_if_needed();")
    op.execute("DROP TRIGGER IF EXISTS trg_auto_create_snapshots_partition ON document_snapshots;")
    op.execute("DROP FUNCTION IF EXISTS create_snapshots_partition_if_needed();")


