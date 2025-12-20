"""
Add FTS indexes on document_fields.raw_value_text for multi-language search.

Revision ID: 009_add_fts_indexes
Revises: 008_auto_create_partitions
Create Date: 2025-12-13
"""
from alembic import op
import sqlalchemy as sa

revision = '009_add_fts_indexes'
down_revision = '008_auto_create_partitions'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add FTS indexes on document_fields.raw_value_text.

    Configuration from .env:
    - FTS_LANGUAGES: языки для индексов (default: "simple,russian,english")
    - FTS_PARTIAL_INDEX_LANGUAGES: языки для partial индексов (default: "ru,uk")

    Примечание: Значения берутся из конфигурации через переменные окружения,
    но для миграции используем значения по умолчанию.
    """

    # ========================================================================
    # 1. FTS индексы на document_fields.raw_value_text
    # ========================================================================

    # Simple - универсальный для всех языков
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_fields_raw_value_fts_simple
        ON document_fields USING GIN (to_tsvector('simple', COALESCE(raw_value_text, '')));
    """)

    # Russian - для русского и украинского (partial index)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_fields_raw_value_fts_ru
        ON document_fields USING GIN (to_tsvector('russian', COALESCE(raw_value_text, '')))
        WHERE language IN ('ru', 'uk');
    """)

    # English
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_fields_raw_value_fts_en
        ON document_fields USING GIN (to_tsvector('english', COALESCE(raw_value_text, '')))
        WHERE language = 'en';
    """)

    # ========================================================================
    # 2. Partial index на section_label для быстрого поиска
    # ========================================================================

    # Уже существует из миграции 007, но проверим
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_document_fields_section_label
        ON document_fields (section_label)
        WHERE section_label IS NOT NULL;
    """)

    print("✅ FTS индексы созданы успешно")
    print("   - simple: для всех языков")
    print("   - russian: для ru, uk (partial)")
    print("   - english: для en (partial)")


def downgrade() -> None:
    """Remove FTS indexes"""

    op.execute("DROP INDEX IF EXISTS idx_document_fields_raw_value_fts_simple;")
    op.execute("DROP INDEX IF EXISTS idx_document_fields_raw_value_fts_ru;")
    op.execute("DROP INDEX IF EXISTS idx_document_fields_raw_value_fts_en;")

    print("❌ FTS индексы удалены")










