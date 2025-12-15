"""
Partition related tables (document_fields, document_snapshots, document_table_sections).
Uses HASH partitioning by document_id for better JOIN performance with partitioned documents.

Revision ID: 004_partition_related_tables
Revises: 003_table_partitioning
Create Date: 2025-12-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '004_partition_related_tables'
down_revision = '003_table_partitioning'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add partitioning for related tables:
    1. document_fields - HASH by document_id (for JOIN performance)
    2. document_snapshots - RANGE by created_at (for archiving)
    3. document_table_sections - HASH by document_id (for JOIN performance)

    NOTE: PostgreSQL 12+ supports reference partitioning, but HASH partitioning
    is more compatible and works well for JOIN operations.
    """

    conn = op.get_bind()

    # ========================================================================
    # 1. Partition document_fields by HASH(document_id)
    # ========================================================================

    # Check if already partitioned
    result = conn.execute(sa.text("""
        SELECT COUNT(*)
        FROM pg_inherits
        WHERE inhparent = 'document_fields'::regclass;
    """))
    is_partitioned = result.scalar() > 0

    if not is_partitioned:
        # Check if table exists
        result = conn.execute(sa.text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'document_fields'
            );
        """))
        table_exists = result.scalar()
        
        # Check if table has data (only if table exists)
        has_data = False
        if table_exists:
            try:
                result = conn.execute(sa.text("SELECT COUNT(*) FROM document_fields;"))
                has_data = result.scalar() > 0
            except Exception:
                has_data = False

        if has_data:
            # Create partitioned table structure
            # NOTE: Cannot use INCLUDING ALL because PRIMARY KEY must include partition key
            # So we create table manually without constraints, then add them
            op.execute("""
                CREATE TABLE document_fields_partitioned (
                    id BIGSERIAL NOT NULL,
                    document_id BIGINT NOT NULL,
                    field_id INTEGER,
                    field_code VARCHAR(100),
                    section VARCHAR(50) NOT NULL,
                    group_key VARCHAR(100),
                    raw_label TEXT,
                    language VARCHAR(10),
                    raw_value_text TEXT,
                    raw_value_number NUMERIC(30, 10),
                    raw_value_date DATE,
                    raw_value_bool BOOLEAN,
                    raw_confidence NUMERIC(3, 2),
                    approved_value_text TEXT,
                    approved_value_number NUMERIC(30, 10),
                    approved_value_date DATE,
                    approved_value_bool BOOLEAN,
                    approved_by BIGINT,
                    approved_at TIMESTAMP,
                    is_corrected BOOLEAN NOT NULL DEFAULT false,
                    is_ignored BOOLEAN NOT NULL DEFAULT false,
                    raw_snapshot_id BIGINT,
                    approved_snapshot_id BIGINT,
                    page_id BIGINT,
                    bbox JSONB,
                    created_at TIMESTAMP NOT NULL DEFAULT now(),
                    updated_at TIMESTAMP NOT NULL DEFAULT now(),
                    PRIMARY KEY (id, document_id)
                ) PARTITION BY HASH (document_id);
            """)

            # Create 4 hash partitions (adjust based on expected data volume)
            for i in range(4):
                op.execute(f"""
                    CREATE TABLE document_fields_p{i} PARTITION OF document_fields_partitioned
                    FOR VALUES WITH (modulus 4, remainder {i});
                """)

            # Copy data (only if there is data)
            if has_data:
                op.execute("""
                    INSERT INTO document_fields_partitioned
                    SELECT * FROM document_fields;
                """)

            # Drop old table and rename (only if table existed)
            if table_exists:
                op.execute("DROP TABLE document_fields CASCADE;")
            op.execute("ALTER TABLE document_fields_partitioned RENAME TO document_fields;")

            # NOTE: Cannot create FOREIGN KEY on document_id because documents table is partitioned
            # with PRIMARY KEY (id, created_at). PostgreSQL requires FK to reference unique constraint
            # that includes partition key. We rely on application-level integrity instead.
            # Foreign key constraint is skipped for partitioned tables.

            # Add foreign keys only if referenced tables exist
            result = conn.execute(sa.text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'field_definitions'
                );
            """))
            if result.scalar():
                try:
                    op.execute("""
                        ALTER TABLE document_fields
                        ADD CONSTRAINT document_fields_field_id_fkey
                        FOREIGN KEY (field_id) REFERENCES field_definitions(id);
                    """)
                except Exception as e:
                    # Constraint might already exist, skip
                    pass

            result = conn.execute(sa.text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'document_pages'
                );
            """))
            if result.scalar():
                try:
                    op.execute("""
                        ALTER TABLE document_fields
                        ADD CONSTRAINT document_fields_page_id_fkey
                        FOREIGN KEY (page_id) REFERENCES document_pages(id);
                    """)
                except Exception as e:
                    # Constraint might already exist, skip
                    pass

            # Recreate indexes
            op.execute("""
                CREATE INDEX ix_document_fields_doc_section
                ON document_fields (document_id, section);
            """)

            op.execute("""
                CREATE INDEX ix_document_fields_code
                ON document_fields (field_code)
                WHERE field_code IS NOT NULL;
            """)

            op.execute("""
                CREATE INDEX ix_document_fields_corrected
                ON document_fields (is_corrected)
                WHERE is_corrected = true;
            """)

            op.execute("""
                CREATE INDEX ix_document_fields_unknown
                ON document_fields (field_id)
                WHERE field_id IS NULL;
            """)
        else:
            # No data - just recreate as partitioned
            # NOTE: Cannot create FOREIGN KEY on document_id because documents table is partitioned
            # with PRIMARY KEY (id, created_at). PostgreSQL requires FK to reference unique constraint
            # that includes partition key. We rely on application-level integrity instead.
            
            # Check if table exists before dropping
            result = conn.execute(sa.text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'document_fields'
                );
            """))
            table_exists = result.scalar()
            
            if table_exists:
                op.execute("DROP TABLE document_fields CASCADE;")
            
            op.execute("""
                CREATE TABLE document_fields (
                    id BIGSERIAL NOT NULL,
                    document_id BIGINT NOT NULL,
                    field_id INTEGER,
                    field_code VARCHAR(100),
                    section VARCHAR(50) NOT NULL,
                    group_key VARCHAR(100),
                    raw_label TEXT,
                    language VARCHAR(10),
                    raw_value_text TEXT,
                    raw_value_number NUMERIC(30, 10),
                    raw_value_date DATE,
                    raw_value_bool BOOLEAN,
                    raw_confidence NUMERIC(3, 2),
                    approved_value_text TEXT,
                    approved_value_number NUMERIC(30, 10),
                    approved_value_date DATE,
                    approved_value_bool BOOLEAN,
                    approved_by BIGINT,
                    approved_at TIMESTAMP,
                    is_corrected BOOLEAN NOT NULL DEFAULT false,
                    is_ignored BOOLEAN NOT NULL DEFAULT false,
                    raw_snapshot_id BIGINT,
                    approved_snapshot_id BIGINT,
                    page_id BIGINT,
                    bbox JSONB,
                    created_at TIMESTAMP NOT NULL DEFAULT now(),
                    updated_at TIMESTAMP NOT NULL DEFAULT now(),
                    PRIMARY KEY (id, document_id)
                ) PARTITION BY HASH (document_id);
            """)

            # Create partitions
            for i in range(4):
                op.execute(f"""
                    CREATE TABLE document_fields_p{i} PARTITION OF document_fields
                    FOR VALUES WITH (modulus 4, remainder {i});
                """)

            # Add foreign keys (except document_id - see comment above)
            # Check if field_definitions table exists
            result = conn.execute(sa.text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'field_definitions'
                );
            """))
            if result.scalar():
                op.execute("""
                    ALTER TABLE document_fields
                    ADD CONSTRAINT document_fields_field_id_fkey
                    FOREIGN KEY (field_id) REFERENCES field_definitions(id);
                """)

            # Check if document_pages table exists
            result = conn.execute(sa.text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'document_pages'
                );
            """))
            if result.scalar():
                op.execute("""
                    ALTER TABLE document_fields
                    ADD CONSTRAINT document_fields_page_id_fkey
                    FOREIGN KEY (page_id) REFERENCES document_pages(id);
                """)

            # Create indexes
            op.execute("""
                CREATE INDEX ix_document_fields_doc_section
                ON document_fields (document_id, section);
            """)

            op.execute("""
                CREATE INDEX ix_document_fields_code
                ON document_fields (field_code)
                WHERE field_code IS NOT NULL;
            """)

            op.execute("""
                CREATE INDEX ix_document_fields_corrected
                ON document_fields (is_corrected)
                WHERE is_corrected = true;
            """)

            op.execute("""
                CREATE INDEX ix_document_fields_unknown
                ON document_fields (field_id)
                WHERE field_id IS NULL;
            """)

    # ========================================================================
    # 2. Partition document_snapshots by RANGE(created_at)
    # ========================================================================

    result = conn.execute(sa.text("""
        SELECT COUNT(*)
        FROM pg_inherits
        WHERE inhparent = 'document_snapshots'::regclass;
    """))
    is_partitioned = result.scalar() > 0

    if not is_partitioned:
        result = conn.execute(sa.text("SELECT COUNT(*) FROM document_snapshots;"))
        has_data = result.scalar() > 0

        if has_data:
            # Get date range
            date_result = conn.execute(sa.text("""
                SELECT
                    DATE_TRUNC('year', MIN(created_at)) as min_date,
                    DATE_TRUNC('year', MAX(created_at)) + INTERVAL '1 year' as max_date
                FROM document_snapshots;
            """))
            date_row = date_result.fetchone()

            # Create partitioned table manually (PRIMARY KEY must include partition key)
            # NOTE: UNIQUE constraint on (document_id, snapshot_type, version) removed
            # because it must include partition key. Rely on application-level uniqueness.
            op.execute("""
                CREATE TABLE document_snapshots_partitioned (
                    id BIGSERIAL NOT NULL,
                    document_id BIGINT NOT NULL,
                    snapshot_type VARCHAR(32) NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    payload JSONB NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT now(),
                    created_by BIGINT,
                    PRIMARY KEY (id, created_at)
                ) PARTITION BY RANGE (created_at);
            """)

            if date_row and date_row[0]:
                min_date = date_row[0]
                max_date = date_row[1]
                current_year = min_date.year if min_date else 2024
                end_year = max_date.year if max_date else 2026

                for year in range(current_year, end_year + 1):
                    partition_start = f"{year}-01-01"
                    partition_end = f"{year + 1}-01-01"
                    op.execute(f"""
                        CREATE TABLE document_snapshots_{year} PARTITION OF document_snapshots_partitioned
                        FOR VALUES FROM ('{partition_start}') TO ('{partition_end}');
                    """)
            else:
                # Default partitions
                from datetime import datetime
                current_year = datetime.now().year
                for year in range(current_year, current_year + 2):
                    partition_start = f"{year}-01-01"
                    partition_end = f"{year + 1}-01-01"
                    op.execute(f"""
                        CREATE TABLE document_snapshots_{year} PARTITION OF document_snapshots_partitioned
                        FOR VALUES FROM ('{partition_start}') TO ('{partition_end}');
                    """)

            # Copy data
            op.execute("""
                INSERT INTO document_snapshots_partitioned
                SELECT * FROM document_snapshots;
            """)

            # Drop and rename
            op.execute("DROP TABLE document_snapshots CASCADE;")
            op.execute("ALTER TABLE document_snapshots_partitioned RENAME TO document_snapshots;")

            # NOTE: FOREIGN KEY on document_id skipped (see comment above for document_fields)

            # Recreate indexes
            # NOTE: UNIQUE index removed - cannot create on partitioned table without partition key
            # Application should enforce uniqueness of (document_id, snapshot_type, version)

            op.execute("""
                CREATE INDEX ix_document_snapshots_doc_type
                ON document_snapshots (document_id, snapshot_type);
            """)
        else:
            # No data - create partitioned table
            op.execute("DROP TABLE document_snapshots CASCADE;")
            op.execute("""
                CREATE TABLE document_snapshots (
                    id BIGSERIAL NOT NULL,
                    document_id BIGINT NOT NULL,
                    snapshot_type VARCHAR(32) NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    payload JSONB NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT now(),
                    created_by BIGINT,
                    PRIMARY KEY (id, created_at)
                ) PARTITION BY RANGE (created_at);
            """)

            # Create partitions
            from datetime import datetime
            current_year = datetime.now().year
            for year in range(current_year, current_year + 2):
                partition_start = f"{year}-01-01"
                partition_end = f"{year + 1}-01-01"
                op.execute(f"""
                    CREATE TABLE document_snapshots_{year} PARTITION OF document_snapshots
                    FOR VALUES FROM ('{partition_start}') TO ('{partition_end}');
                """)

            # Create indexes
            op.execute("""
                CREATE INDEX ix_document_snapshots_doc_type
                ON document_snapshots (document_id, snapshot_type);
            """)

    # ========================================================================
    # 3. Partition document_table_sections by HASH(document_id)
    # ========================================================================

    result = conn.execute(sa.text("""
        SELECT COUNT(*)
        FROM pg_inherits
        WHERE inhparent = 'document_table_sections'::regclass;
    """))
    is_partitioned = result.scalar() > 0

    if not is_partitioned:
        result = conn.execute(sa.text("SELECT COUNT(*) FROM document_table_sections;"))
        has_data = result.scalar() > 0

        if has_data:
            # Create partitioned table manually (PRIMARY KEY must include partition key)
            op.execute("""
                CREATE TABLE document_table_sections_partitioned (
                    id BIGSERIAL NOT NULL,
                    document_id BIGINT NOT NULL,
                    section_name VARCHAR(100) NOT NULL,
                    section_order INTEGER NOT NULL DEFAULT 0,
                    column_mapping_raw JSONB NOT NULL,
                    column_mapping_approved JSONB,
                    rows_raw JSONB NOT NULL,
                    rows_approved JSONB,
                    is_corrected BOOLEAN NOT NULL DEFAULT false,
                    approved_by BIGINT,
                    approved_at TIMESTAMP,
                    created_at TIMESTAMP NOT NULL DEFAULT now(),
                    updated_at TIMESTAMP NOT NULL DEFAULT now(),
                    PRIMARY KEY (id, document_id)
                ) PARTITION BY HASH (document_id);
            """)

            # Create partitions
            for i in range(4):
                op.execute(f"""
                    CREATE TABLE document_table_sections_p{i} PARTITION OF document_table_sections_partitioned
                    FOR VALUES WITH (modulus 4, remainder {i});
                """)

            # Copy data
            op.execute("""
                INSERT INTO document_table_sections_partitioned
                SELECT * FROM document_table_sections;
            """)

            # Drop and rename
            op.execute("DROP TABLE document_table_sections CASCADE;")
            op.execute("ALTER TABLE document_table_sections_partitioned RENAME TO document_table_sections;")

            # NOTE: FOREIGN KEY on document_id skipped (see comment above for document_fields)

            # Recreate index
            op.execute("""
                CREATE INDEX ix_document_table_sections_doc
                ON document_table_sections (document_id, section_order);
            """)
        else:
            # No data - create partitioned table
            op.execute("DROP TABLE document_table_sections CASCADE;")
            op.execute("""
                CREATE TABLE document_table_sections (
                    id BIGSERIAL NOT NULL,
                    document_id BIGINT NOT NULL,
                    section_name VARCHAR(100) NOT NULL,
                    section_order INTEGER NOT NULL DEFAULT 0,
                    column_mapping_raw JSONB NOT NULL,
                    column_mapping_approved JSONB,
                    rows_raw JSONB NOT NULL,
                    rows_approved JSONB,
                    is_corrected BOOLEAN NOT NULL DEFAULT false,
                    approved_by BIGINT,
                    approved_at TIMESTAMP,
                    created_at TIMESTAMP NOT NULL DEFAULT now(),
                    updated_at TIMESTAMP NOT NULL DEFAULT now(),
                    PRIMARY KEY (id, document_id),
                    FOREIGN KEY (document_id) REFERENCES documents(id)
                ) PARTITION BY HASH (document_id);
            """)

            # Create partitions
            for i in range(4):
                op.execute(f"""
                    CREATE TABLE document_table_sections_p{i} PARTITION OF document_table_sections
                    FOR VALUES WITH (modulus 4, remainder {i});
                """)

            # Create index
            op.execute("""
                CREATE INDEX ix_document_table_sections_doc
                ON document_table_sections (document_id, section_order);
            """)

    # Update statistics
    op.execute("ANALYZE document_fields;")
    op.execute("ANALYZE document_snapshots;")
    op.execute("ANALYZE document_table_sections;")


def downgrade() -> None:
    """
    Remove partitioning from related tables.
    WARNING: This requires copying data back to non-partitioned tables.
    """

    conn = op.get_bind()

    # ========================================================================
    # 1. Remove partitioning from document_fields
    # ========================================================================

    result = conn.execute(sa.text("""
        SELECT COUNT(*)
        FROM pg_inherits
        WHERE inhparent = 'document_fields'::regclass;
    """))
    is_partitioned = result.scalar() > 0

    if is_partitioned:
        # Create non-partitioned table
        op.execute("""
            CREATE TABLE document_fields_regular (
                id BIGSERIAL NOT NULL,
                document_id BIGINT NOT NULL,
                field_id INTEGER,
                field_code VARCHAR(100),
                section VARCHAR(50) NOT NULL,
                group_key VARCHAR(100),
                raw_label TEXT,
                language VARCHAR(10),
                raw_value_text TEXT,
                raw_value_number NUMERIC(30, 10),
                raw_value_date DATE,
                raw_value_bool BOOLEAN,
                raw_confidence NUMERIC(3, 2),
                approved_value_text TEXT,
                approved_value_number NUMERIC(30, 10),
                approved_value_date DATE,
                approved_value_bool BOOLEAN,
                approved_by BIGINT,
                approved_at TIMESTAMP,
                is_corrected BOOLEAN NOT NULL DEFAULT false,
                is_ignored BOOLEAN NOT NULL DEFAULT false,
                raw_snapshot_id BIGINT,
                approved_snapshot_id BIGINT,
                page_id BIGINT,
                bbox JSONB,
                created_at TIMESTAMP NOT NULL DEFAULT now(),
                updated_at TIMESTAMP NOT NULL DEFAULT now(),
                PRIMARY KEY (id),
                FOREIGN KEY (document_id) REFERENCES documents(id),
                FOREIGN KEY (field_id) REFERENCES field_definitions(id),
                FOREIGN KEY (page_id) REFERENCES document_pages(id)
            );
        """)

        # Copy data
        op.execute("""
            INSERT INTO document_fields_regular
            SELECT * FROM document_fields;
        """)

        # Drop partitioned and rename
        op.execute("DROP TABLE document_fields CASCADE;")
        op.execute("ALTER TABLE document_fields_regular RENAME TO document_fields;")

        # Recreate indexes
        op.execute("""
            CREATE INDEX ix_document_fields_doc_section
            ON document_fields (document_id, section);
        """)

        op.execute("""
            CREATE INDEX ix_document_fields_code
            ON document_fields (field_code)
            WHERE field_code IS NOT NULL;
        """)

        op.execute("""
            CREATE INDEX ix_document_fields_corrected
            ON document_fields (is_corrected)
            WHERE is_corrected = true;
        """)

        op.execute("""
            CREATE INDEX ix_document_fields_unknown
            ON document_fields (field_id)
            WHERE field_id IS NULL;
        """)

    # ========================================================================
    # 2. Remove partitioning from document_snapshots
    # ========================================================================

    result = conn.execute(sa.text("""
        SELECT COUNT(*)
        FROM pg_inherits
        WHERE inhparent = 'document_snapshots'::regclass;
    """))
    is_partitioned = result.scalar() > 0

    if is_partitioned:
        op.execute("""
            CREATE TABLE document_snapshots_regular (
                id BIGSERIAL NOT NULL,
                document_id BIGINT NOT NULL,
                snapshot_type VARCHAR(32) NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                payload JSONB NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT now(),
                created_by BIGINT,
                PRIMARY KEY (id),
                FOREIGN KEY (document_id) REFERENCES documents(id),
                UNIQUE (document_id, snapshot_type, version)
            );
        """)

        op.execute("""
            INSERT INTO document_snapshots_regular
            SELECT * FROM document_snapshots;
        """)

        op.execute("DROP TABLE document_snapshots CASCADE;")
        op.execute("ALTER TABLE document_snapshots_regular RENAME TO document_snapshots;")

        op.execute("""
            CREATE INDEX ix_document_snapshots_doc_type
            ON document_snapshots (document_id, snapshot_type);
        """)

    # ========================================================================
    # 3. Remove partitioning from document_table_sections
    # ========================================================================

    result = conn.execute(sa.text("""
        SELECT COUNT(*)
        FROM pg_inherits
        WHERE inhparent = 'document_table_sections'::regclass;
    """))
    is_partitioned = result.scalar() > 0

    if is_partitioned:
        op.execute("""
            CREATE TABLE document_table_sections_regular (
                id BIGSERIAL NOT NULL,
                document_id BIGINT NOT NULL,
                section_name VARCHAR(100) NOT NULL,
                section_order INTEGER NOT NULL DEFAULT 0,
                column_mapping_raw JSONB NOT NULL,
                column_mapping_approved JSONB,
                rows_raw JSONB NOT NULL,
                rows_approved JSONB,
                is_corrected BOOLEAN NOT NULL DEFAULT false,
                approved_by BIGINT,
                approved_at TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT now(),
                updated_at TIMESTAMP NOT NULL DEFAULT now(),
                PRIMARY KEY (id),
                FOREIGN KEY (document_id) REFERENCES documents(id)
            );
        """)

        op.execute("""
            INSERT INTO document_table_sections_regular
            SELECT * FROM document_table_sections;
        """)

        op.execute("DROP TABLE document_table_sections CASCADE;")
        op.execute("ALTER TABLE document_table_sections_regular RENAME TO document_table_sections;")

        op.execute("""
            CREATE INDEX ix_document_table_sections_doc
            ON document_table_sections (document_id, section_order);
        """)

