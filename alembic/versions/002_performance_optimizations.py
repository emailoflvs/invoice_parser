"""
Performance optimizations: GIN indexes, full-text search, composite indexes.

Revision ID: 002_performance_optimizations
Revises: 001_initial_schema
Create Date: 2025-12-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '002_performance_optimizations'
down_revision = '001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add performance optimizations:
    1. GIN indexes on JSONB fields for fast JSON queries
    2. Full-text search indexes for text fields
    3. Composite indexes for common query patterns
    4. Unique constraints for data integrity
    """

    # ========================================================================
    # 1. GIN indexes on JSONB fields
    # ========================================================================

    # document_snapshots.payload - критично для поиска по метаданным
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_snapshots_payload_gin
        ON document_snapshots USING GIN (payload);
    """)

    # documents.parsing_metadata - для поиска по версии модели, времени парсинга
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_parsing_metadata_gin
        ON documents USING GIN (parsing_metadata);
    """)

    # document_fields.bbox - для поиска по координатам полей
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_fields_bbox_gin
        ON document_fields USING GIN (bbox);
    """)

    # document_signatures.raw_value - для поиска в подписях
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_signatures_raw_value_gin
        ON document_signatures USING GIN (raw_value);
    """)

    # document_signatures.approved_value - для поиска в одобренных подписях
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_signatures_approved_value_gin
        ON document_signatures USING GIN (approved_value);
    """)

    # document_table_sections.column_mapping_raw - для поиска по маппингу колонок
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_table_sections_column_mapping_raw_gin
        ON document_table_sections USING GIN (column_mapping_raw);
    """)

    # document_table_sections.rows_raw - КРИТИЧНО для поиска по значениям в таблицах
    # Используем jsonb_path_ops для более быстрого поиска по путям
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_table_sections_rows_raw_gin
        ON document_table_sections USING GIN (rows_raw jsonb_path_ops);
    """)

    # document_table_sections.rows_approved - для поиска в одобренных данных
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_table_sections_rows_approved_gin
        ON document_table_sections USING GIN (rows_approved jsonb_path_ops);
    """)

    # company_document_profiles.settings - для поиска в настройках профилей
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_company_document_profiles_settings_gin
        ON company_document_profiles USING GIN (settings);
    """)

    # ========================================================================
    # 2. Full-text search indexes
    # ========================================================================

    # companies.legal_name - полнотекстовый поиск по названиям компаний
    # Используем 'simple' для мультиязычности (работает с любым текстом)
    # Также добавляем 'russian' и 'english' для лучшей поддержки этих языков
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_companies_legal_name_fts_simple
        ON companies USING GIN (to_tsvector('simple', COALESCE(legal_name, '')));
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_companies_legal_name_fts_ru
        ON companies USING GIN (to_tsvector('russian', COALESCE(legal_name, '')));
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_companies_legal_name_fts_en
        ON companies USING GIN (to_tsvector('english', COALESCE(legal_name, '')));
    """)

    # document_pages.ocr_text - полнотекстовый поиск по OCR тексту
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_pages_ocr_text_fts_simple
        ON document_pages USING GIN (to_tsvector('simple', COALESCE(ocr_text, '')));
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_pages_ocr_text_fts_ru
        ON document_pages USING GIN (to_tsvector('russian', COALESCE(ocr_text, '')));
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_pages_ocr_text_fts_en
        ON document_pages USING GIN (to_tsvector('english', COALESCE(ocr_text, '')));
    """)

    # document_fields.raw_value_text - поиск по значениям полей
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_fields_raw_value_text_fts_ru
        ON document_fields USING GIN (to_tsvector('russian', COALESCE(raw_value_text, '')));
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_fields_raw_value_text_fts_en
        ON document_fields USING GIN (to_tsvector('english', COALESCE(raw_value_text, '')));
    """)

    # ========================================================================
    # 3. Composite indexes for common query patterns
    # ========================================================================

    # documents: фильтрация по статусу и сортировка по дате (для дашбордов)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_status_created
        ON documents (status, created_at DESC);
    """)

    # documents: поиск документов по поставщику с сортировкой
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_supplier_created
        ON documents (supplier_id, created_at DESC)
        WHERE supplier_id IS NOT NULL;
    """)

    # documents: поиск документов по покупателю с сортировкой
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_buyer_created
        ON documents (buyer_id, created_at DESC)
        WHERE buyer_id IS NOT NULL;
    """)

    # documents: мультистрановые запросы (страна + язык + дата)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_country_language_created
        ON documents (country, language, created_at DESC)
        WHERE country IS NOT NULL AND language IS NOT NULL;
    """)

    # documents: поиск по типу документа и статусу
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_type_status
        ON documents (doc_type_id, status)
        WHERE doc_type_id IS NOT NULL;
    """)

    # document_fields: поиск полей документа с фильтрацией по коду и исправлениям
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_fields_doc_code_corrected
        ON document_fields (document_id, field_code, is_corrected)
        WHERE field_code IS NOT NULL;
    """)

    # document_fields: поиск неизвестных полей (field_id IS NULL)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_fields_unknown_fields
        ON document_fields (document_id, section)
        WHERE field_id IS NULL;
    """)

    # document_snapshots: поиск последней версии снимка определенного типа
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_snapshots_doc_type_version
        ON document_snapshots (document_id, snapshot_type, version DESC);
    """)

    # document_table_sections: поиск таблиц по документу и секции
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_table_sections_doc_section
        ON document_table_sections (document_id, section_name, section_order);
    """)

    # companies: поиск по налоговому ID и стране (для избежания дубликатов)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_companies_tax_id_country
        ON companies (tax_id, country)
        WHERE tax_id IS NOT NULL;
    """)

    # ========================================================================
    # 4. Unique constraints for data integrity
    # ========================================================================

    # files.file_hash - файлы с одинаковым хешем должны быть уникальны (дедупликация)
    # Но только если хеш не NULL - несколько NULL значений допустимы
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_files_hash
        ON files (file_hash)
        WHERE file_hash IS NOT NULL;
    """)

    # ========================================================================
    # 5. Partial indexes for better performance
    # ========================================================================

    # document_fields: индекс только для исправленных полей (для ML обучения)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_fields_corrected_only
        ON document_fields (document_id, field_code, is_corrected, approved_at)
        WHERE is_corrected = true;
    """)

    # documents: индекс только для активных документов (не удаленных)
    # Пока нет поля deleted_at, но подготовим структуру
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_active_status
        ON documents (status, created_at DESC)
        WHERE status IN ('parsed', 'in_review', 'approved');
    """)

    # ========================================================================
    # 6. Statistics update for query planner
    # ========================================================================

    # Обновляем статистику для оптимизатора запросов
    op.execute("ANALYZE documents;")
    op.execute("ANALYZE document_fields;")
    op.execute("ANALYZE document_snapshots;")
    op.execute("ANALYZE document_table_sections;")
    op.execute("ANALYZE companies;")


def downgrade() -> None:
    """
    Remove all performance optimizations.
    """

    # Drop composite indexes
    op.drop_index('idx_documents_active_status', table_name='documents', if_exists=True)
    op.drop_index('idx_document_fields_corrected_only', table_name='document_fields', if_exists=True)
    op.drop_index('idx_companies_tax_id_country', table_name='companies', if_exists=True)
    op.drop_index('idx_document_table_sections_doc_section', table_name='document_table_sections', if_exists=True)
    op.drop_index('idx_document_snapshots_doc_type_version', table_name='document_snapshots', if_exists=True)
    op.drop_index('idx_document_fields_unknown_fields', table_name='document_fields', if_exists=True)
    op.drop_index('idx_document_fields_doc_code_corrected', table_name='document_fields', if_exists=True)
    op.drop_index('idx_documents_type_status', table_name='documents', if_exists=True)
    op.drop_index('idx_documents_country_language_created', table_name='documents', if_exists=True)
    op.drop_index('idx_documents_buyer_created', table_name='documents', if_exists=True)
    op.drop_index('idx_documents_supplier_created', table_name='documents', if_exists=True)
    op.drop_index('idx_documents_status_created', table_name='documents', if_exists=True)

    # Drop full-text search indexes
    op.drop_index('idx_document_fields_raw_value_text_fts_en', table_name='document_fields', if_exists=True)
    op.drop_index('idx_document_fields_raw_value_text_fts_ru', table_name='document_fields', if_exists=True)
    op.drop_index('idx_document_pages_ocr_text_fts_en', table_name='document_pages', if_exists=True)
    op.drop_index('idx_document_pages_ocr_text_fts_simple', table_name='document_pages', if_exists=True)
    op.drop_index('idx_document_pages_ocr_text_fts_ru', table_name='document_pages', if_exists=True)
    op.drop_index('idx_companies_legal_name_fts_en', table_name='companies', if_exists=True)
    op.drop_index('idx_companies_legal_name_fts_simple', table_name='companies', if_exists=True)
    op.drop_index('idx_companies_legal_name_fts_ru', table_name='companies', if_exists=True)

    # Drop GIN indexes on JSONB
    op.drop_index('idx_company_document_profiles_settings_gin', table_name='company_document_profiles', if_exists=True)
    op.drop_index('idx_document_table_sections_rows_approved_gin', table_name='document_table_sections', if_exists=True)
    op.drop_index('idx_document_table_sections_rows_raw_gin', table_name='document_table_sections', if_exists=True)
    op.drop_index('idx_document_table_sections_column_mapping_raw_gin', table_name='document_table_sections', if_exists=True)
    op.drop_index('idx_document_signatures_approved_value_gin', table_name='document_signatures', if_exists=True)
    op.drop_index('idx_document_signatures_raw_value_gin', table_name='document_signatures', if_exists=True)
    op.drop_index('idx_document_fields_bbox_gin', table_name='document_fields', if_exists=True)
    op.drop_index('idx_documents_parsing_metadata_gin', table_name='documents', if_exists=True)
    op.drop_index('idx_document_snapshots_payload_gin', table_name='document_snapshots', if_exists=True)

    # Drop unique constraints
    op.drop_index('uq_files_hash', table_name='files', if_exists=True)

