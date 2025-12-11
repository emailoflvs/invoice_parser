"""
Table partitioning for large tables.
WARNING: This migration partitions existing tables.
For production, consider running during low-traffic periods and having backups.

Revision ID: 003_table_partitioning
Revises: 002_performance_optimizations
Create Date: 2025-12-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '003_table_partitioning'
down_revision = '002_performance_optimizations'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add table partitioning for large tables.

    NOTE: Partitioning existing tables requires:
    1. Creating new partitioned table
    2. Copying data
    3. Renaming tables
    4. Recreating indexes and constraints

    This is done carefully to avoid data loss.
    """

    # ========================================================================
    # Partition documents table by created_at (RANGE partitioning)
    # ========================================================================

    # Check if table is already partitioned
    conn = op.get_bind()
    result = conn.execute(sa.text("""
        SELECT COUNT(*)
        FROM pg_inherits
        WHERE inhparent = 'documents'::regclass;
    """))

    is_partitioned = result.scalar() > 0

    if not is_partitioned:
        # Create partitioned table structure
        # NOTE: For partitioned tables, PRIMARY KEY must include partition key
        # We need to create the table manually with proper structure
        op.execute("""
            CREATE TABLE documents_partitioned (
                id BIGSERIAL NOT NULL,
                file_id BIGINT NOT NULL,
                doc_type_id INTEGER,
                status VARCHAR(50) NOT NULL DEFAULT 'parsed',
                language VARCHAR(10),
                country VARCHAR(10),
                supplier_id BIGINT,
                buyer_id BIGINT,
                created_at TIMESTAMP NOT NULL DEFAULT now(),
                created_by BIGINT,
                updated_at TIMESTAMP NOT NULL DEFAULT now(),
                updated_by BIGINT,
                parsing_metadata JSONB,
                PRIMARY KEY (id, created_at)
            ) PARTITION BY RANGE (created_at);
        """)

        # Get date range from existing data
        date_result = conn.execute(sa.text("""
            SELECT
                DATE_TRUNC('year', MIN(created_at)) as min_date,
                DATE_TRUNC('year', MAX(created_at)) + INTERVAL '1 year' as max_date
            FROM documents;
        """))
        date_row = date_result.fetchone()

        if date_row and date_row[0]:
            min_date = date_row[0]
            max_date = date_row[1]

            # Create partitions for each year
            current_year = min_date.year if min_date else 2024
            end_year = max_date.year if max_date else 2026

            for year in range(current_year, end_year + 1):
                partition_start = f"{year}-01-01"
                partition_end = f"{year + 1}-01-01"

                op.execute(f"""
                    CREATE TABLE documents_{year} PARTITION OF documents_partitioned
                    FOR VALUES FROM ('{partition_start}') TO ('{partition_end}');
                """)

            # Copy data from old table to new partitioned table
            op.execute("""
                INSERT INTO documents_partitioned
                SELECT * FROM documents;
            """)

            # Drop old table and rename new one
            op.execute("DROP TABLE documents CASCADE;")
            op.execute("ALTER TABLE documents_partitioned RENAME TO documents;")

            # Recreate foreign key constraints (they were dropped with CASCADE)
            # Note: This might need adjustment based on actual FK relationships
            op.execute("""
                ALTER TABLE documents
                ADD CONSTRAINT documents_file_id_fkey
                FOREIGN KEY (file_id) REFERENCES files(id);
            """)

            op.execute("""
                ALTER TABLE documents
                ADD CONSTRAINT documents_doc_type_id_fkey
                FOREIGN KEY (doc_type_id) REFERENCES document_types(id);
            """)

            op.execute("""
                ALTER TABLE documents
                ADD CONSTRAINT documents_supplier_id_fkey
                FOREIGN KEY (supplier_id) REFERENCES companies(id);
            """)

            op.execute("""
                ALTER TABLE documents
                ADD CONSTRAINT documents_buyer_id_fkey
                FOREIGN KEY (buyer_id) REFERENCES companies(id);
            """)

            # Recreate indexes (they were dropped with table)
            # Note: Some indexes will be recreated automatically on partitions
            op.execute("""
                CREATE INDEX IF NOT EXISTS ix_documents_status ON documents (status);
            """)

            op.execute("""
                CREATE INDEX IF NOT EXISTS ix_documents_supplier ON documents (supplier_id)
                WHERE supplier_id IS NOT NULL;
            """)

            op.execute("""
                CREATE INDEX IF NOT EXISTS ix_documents_buyer ON documents (buyer_id)
                WHERE buyer_id IS NOT NULL;
            """)

            op.execute("""
                CREATE INDEX IF NOT EXISTS ix_documents_created ON documents (created_at);
            """)
        else:
            # No data yet, just create empty partitioned table structure
            op.execute("DROP TABLE documents CASCADE;")
            op.execute("""
                CREATE TABLE documents (
                    id BIGSERIAL NOT NULL,
                    file_id BIGINT NOT NULL,
                    doc_type_id INTEGER,
                    status VARCHAR(50) NOT NULL DEFAULT 'parsed',
                    language VARCHAR(10),
                    country VARCHAR(10),
                    supplier_id BIGINT,
                    buyer_id BIGINT,
                    created_at TIMESTAMP NOT NULL DEFAULT now(),
                    created_by BIGINT,
                    updated_at TIMESTAMP NOT NULL DEFAULT now(),
                    updated_by BIGINT,
                    parsing_metadata JSONB,
                    PRIMARY KEY (id, created_at),
                    FOREIGN KEY (file_id) REFERENCES files(id),
                    FOREIGN KEY (doc_type_id) REFERENCES document_types(id),
                    FOREIGN KEY (supplier_id) REFERENCES companies(id),
                    FOREIGN KEY (buyer_id) REFERENCES companies(id)
                ) PARTITION BY RANGE (created_at);
            """)

            # Create default partition for current year
            from datetime import datetime
            current_year = datetime.now().year
            op.execute(f"""
                CREATE TABLE documents_{current_year} PARTITION OF documents
                FOR VALUES FROM ('{current_year}-01-01') TO ('{current_year + 1}-01-01');
            """)

            # Create next year partition for future data
            op.execute(f"""
                CREATE TABLE documents_{current_year + 1} PARTITION OF documents
                FOR VALUES FROM ('{current_year + 1}-01-01') TO ('{current_year + 2}-01-01');
            """)

    # ========================================================================
    # Note: Partitioning other tables (document_fields, document_snapshots, etc.)
    # is more complex and should be done carefully. For now, we focus on documents.
    #
    # For document_fields, consider HASH partitioning by document_id:
    # PARTITION BY HASH (document_id)
    #
    # For document_snapshots, consider RANGE partitioning by created_at:
    # PARTITION BY RANGE (created_at)
    # ========================================================================

    # Update statistics
    op.execute("ANALYZE documents;")


def downgrade() -> None:
    """
    Remove partitioning (convert back to regular tables).
    WARNING: This requires copying data back to non-partitioned table.
    """

    conn = op.get_bind()

    # Check if documents is partitioned
    result = conn.execute(sa.text("""
        SELECT COUNT(*)
        FROM pg_inherits
        WHERE inhparent = 'documents'::regclass;
    """))

    is_partitioned = result.scalar() > 0

    if is_partitioned:
        # Create new non-partitioned table
        op.execute("""
            CREATE TABLE documents_regular (
                LIKE documents INCLUDING ALL
            );
        """)

        # Remove partitioning from structure - recreate as regular table
        op.execute("""
            CREATE TABLE documents_regular (
                id BIGSERIAL NOT NULL,
                file_id BIGINT NOT NULL,
                doc_type_id INTEGER,
                status VARCHAR(50) NOT NULL DEFAULT 'parsed',
                language VARCHAR(10),
                country VARCHAR(10),
                supplier_id BIGINT,
                buyer_id BIGINT,
                created_at TIMESTAMP NOT NULL DEFAULT now(),
                created_by BIGINT,
                updated_at TIMESTAMP NOT NULL DEFAULT now(),
                updated_by BIGINT,
                parsing_metadata JSONB,
                PRIMARY KEY (id)
            );
        """)

        # Copy data from partitioned table
        op.execute("""
            INSERT INTO documents_regular
            SELECT id, file_id, doc_type_id, status, language, country,
                   supplier_id, buyer_id, created_at, created_by,
                   updated_at, updated_by, parsing_metadata
            FROM documents;
        """)

        # Drop partitioned table and rename
        op.execute("DROP TABLE documents CASCADE;")
        op.execute("ALTER TABLE documents_regular RENAME TO documents;")

        # Recreate foreign keys
        op.execute("""
            ALTER TABLE documents
            ADD CONSTRAINT documents_file_id_fkey
            FOREIGN KEY (file_id) REFERENCES files(id);
        """)

        op.execute("""
            ALTER TABLE documents
            ADD CONSTRAINT documents_doc_type_id_fkey
            FOREIGN KEY (doc_type_id) REFERENCES document_types(id);
        """)

        op.execute("""
            ALTER TABLE documents
            ADD CONSTRAINT documents_supplier_id_fkey
            FOREIGN KEY (supplier_id) REFERENCES companies(id);
        """)

        op.execute("""
            ALTER TABLE documents
            ADD CONSTRAINT documents_buyer_id_fkey
            FOREIGN KEY (buyer_id) REFERENCES companies(id);
        """)

        # Recreate indexes
        op.execute("CREATE INDEX ix_documents_status ON documents (status);")
        op.execute("CREATE INDEX ix_documents_supplier ON documents (supplier_id);")
        op.execute("CREATE INDEX ix_documents_buyer ON documents (buyer_id);")
        op.execute("CREATE INDEX ix_documents_created ON documents (created_at);")

