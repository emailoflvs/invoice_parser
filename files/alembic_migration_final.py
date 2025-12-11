"""
Final comprehensive architecture for document parsing.
Includes: unknown fields, signatures, dynamic tables.

Revision ID: 001_final_architecture
Revises: 
Create Date: 2025-12-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001_final_architecture'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all tables"""
    
    # Reference Tables
    op.create_table(
        'document_types',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    
    op.create_table(
        'field_definitions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=100), nullable=False),
        sa.Column('section', sa.String(length=50), nullable=False),
        sa.Column('data_type', sa.String(length=20), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    
    op.create_table(
        'field_labels',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('field_id', sa.Integer(), nullable=False),
        sa.Column('locale', sa.String(length=10), nullable=False),
        sa.Column('label', sa.String(length=200), nullable=False),
        sa.ForeignKeyConstraint(['field_id'], ['field_definitions.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_field_labels_field_locale', 'field_labels', ['field_id', 'locale'])
    
    # Companies
    op.create_table(
        'companies',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('legal_name', sa.Text(), nullable=False),
        sa.Column('short_name', sa.Text(), nullable=True),
        sa.Column('tax_id', sa.String(length=50), nullable=True),
        sa.Column('vat_id', sa.String(length=50), nullable=True),
        sa.Column('registration_code', sa.String(length=50), nullable=True),
        sa.Column('country', sa.String(length=10), nullable=True),
        sa.Column('language', sa.String(length=10), nullable=True),
        sa.Column('address_legal', sa.Text(), nullable=True),
        sa.Column('address_postal', sa.Text(), nullable=True),
        sa.Column('iban', sa.String(length=100), nullable=True),
        sa.Column('bank_name', sa.Text(), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('email', sa.String(length=100), nullable=True),
        sa.Column('external_id', sa.String(length=100), nullable=True),
        sa.Column('external_system', sa.String(length=50), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_companies_tax_id', 'companies', ['tax_id'])
    op.create_index('ix_companies_vat_id', 'companies', ['vat_id'])
    op.create_index('ix_companies_name', 'companies', ['legal_name'])
    
    op.create_table(
        'company_document_profiles',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('company_id', sa.BigInteger(), nullable=False),
        sa.Column('doc_type_id', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('expected_currency', sa.String(length=10), nullable=True),
        sa.Column('expected_vat_mode', sa.String(length=50), nullable=True),
        sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.ForeignKeyConstraint(['doc_type_id'], ['document_types.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Files
    op.create_table(
        'files',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('storage_path', sa.Text(), nullable=False),
        sa.Column('original_filename', sa.Text(), nullable=False),
        sa.Column('file_hash', sa.String(length=64), nullable=True),
        sa.Column('mime_type', sa.String(length=100), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('uploaded_by', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_files_hash', 'files', ['file_hash'])
    
    # Documents (MINIMAL!)
    op.create_table(
        'documents',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('file_id', sa.BigInteger(), nullable=False),
        sa.Column('doc_type_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='parsed'),
        sa.Column('language', sa.String(length=10), nullable=True),
        sa.Column('country', sa.String(length=10), nullable=True),
        sa.Column('supplier_id', sa.BigInteger(), nullable=True),
        sa.Column('buyer_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('created_by', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_by', sa.BigInteger(), nullable=True),
        sa.Column('parsing_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['file_id'], ['files.id']),
        sa.ForeignKeyConstraint(['doc_type_id'], ['document_types.id']),
        sa.ForeignKeyConstraint(['supplier_id'], ['companies.id']),
        sa.ForeignKeyConstraint(['buyer_id'], ['companies.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_documents_status', 'documents', ['status'])
    op.create_index('ix_documents_supplier', 'documents', ['supplier_id'])
    op.create_index('ix_documents_buyer', 'documents', ['buyer_id'])
    op.create_index('ix_documents_created', 'documents', ['created_at'])
    
    # Document Pages
    op.create_table(
        'document_pages',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('document_id', sa.BigInteger(), nullable=False),
        sa.Column('file_id', sa.BigInteger(), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=False),
        sa.Column('ocr_text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id']),
        sa.ForeignKeyConstraint(['file_id'], ['files.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_document_pages_doc', 'document_pages', ['document_id', 'page_number'])
    
    # Document Snapshots
    op.create_table(
        'document_snapshots',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('document_id', sa.BigInteger(), nullable=False),
        sa.Column('snapshot_type', sa.String(length=32), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('created_by', sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_id', 'snapshot_type', 'version')
    )
    op.create_index('ix_document_snapshots_doc_type', 'document_snapshots', ['document_id', 'snapshot_type'])
    
    # Document Fields (handles unknown fields!)
    op.create_table(
        'document_fields',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('document_id', sa.BigInteger(), nullable=False),
        sa.Column('field_id', sa.Integer(), nullable=True, comment='NULL for unknown fields'),
        sa.Column('field_code', sa.String(length=100), nullable=True),
        sa.Column('section', sa.String(length=50), nullable=False),
        sa.Column('group_key', sa.String(length=100), nullable=True),
        sa.Column('raw_label', sa.Text(), nullable=True),
        sa.Column('language', sa.String(length=10), nullable=True),
        sa.Column('raw_value_text', sa.Text(), nullable=True),
        sa.Column('raw_value_number', sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column('raw_value_date', sa.Date(), nullable=True),
        sa.Column('raw_value_bool', sa.Boolean(), nullable=True),
        sa.Column('raw_confidence', sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column('approved_value_text', sa.Text(), nullable=True),
        sa.Column('approved_value_number', sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column('approved_value_date', sa.Date(), nullable=True),
        sa.Column('approved_value_bool', sa.Boolean(), nullable=True),
        sa.Column('approved_by', sa.BigInteger(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('is_corrected', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_ignored', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('raw_snapshot_id', sa.BigInteger(), nullable=True),
        sa.Column('approved_snapshot_id', sa.BigInteger(), nullable=True),
        sa.Column('page_id', sa.BigInteger(), nullable=True),
        sa.Column('bbox', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id']),
        sa.ForeignKeyConstraint(['field_id'], ['field_definitions.id']),
        sa.ForeignKeyConstraint(['raw_snapshot_id'], ['document_snapshots.id']),
        sa.ForeignKeyConstraint(['approved_snapshot_id'], ['document_snapshots.id']),
        sa.ForeignKeyConstraint(['page_id'], ['document_pages.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_document_fields_doc_section', 'document_fields', ['document_id', 'section'])
    op.create_index('ix_document_fields_code', 'document_fields', ['field_code'])
    op.create_index('ix_document_fields_corrected', 'document_fields', ['is_corrected'])
    op.create_index('ix_document_fields_unknown', 'document_fields', ['field_id'])
    
    # Document Signatures (NEW!)
    op.create_table(
        'document_signatures',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('document_id', sa.BigInteger(), nullable=False),
        sa.Column('signature_index', sa.Integer(), nullable=False),
        sa.Column('role', sa.Text(), nullable=True),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('is_signed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_stamped', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('stamp_content', sa.Text(), nullable=True),
        sa.Column('handwritten_date', sa.Text(), nullable=True),
        sa.Column('raw_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('approved_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_corrected', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('page_id', sa.BigInteger(), nullable=True),
        sa.Column('bbox', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id']),
        sa.ForeignKeyConstraint(['page_id'], ['document_pages.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_document_signatures_doc', 'document_signatures', ['document_id', 'signature_index'])
    
    # Document Table Sections (NEW!)
    op.create_table(
        'document_table_sections',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('document_id', sa.BigInteger(), nullable=False),
        sa.Column('section_name', sa.String(length=100), nullable=False),
        sa.Column('section_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('column_mapping_raw', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('column_mapping_approved', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('rows_raw', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('rows_approved', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_corrected', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('approved_by', sa.BigInteger(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_document_table_sections_doc', 'document_table_sections', ['document_id', 'section_order'])
    
    # Seed data
    op.execute("""
        INSERT INTO document_types (code, name, description) VALUES
        ('UA_INVOICE', 'Ukrainian Invoice', 'Видаткова накладна'),
        ('UA_TTN', 'Ukrainian Waybill', 'Товарно-транспортна накладна'),
        ('RU_TORG12', 'Russian TORG-12', 'Товарная накладная ТОРГ-12'),
        ('GENERAL_INVOICE', 'General Invoice', 'Universal invoice format')
    """)


def downgrade() -> None:
    """Drop all tables"""
    op.drop_table('document_table_sections')
    op.drop_table('document_signatures')
    op.drop_table('document_fields')
    op.drop_table('document_snapshots')
    op.drop_table('document_pages')
    op.drop_table('documents')
    op.drop_table('files')
    op.drop_table('company_document_profiles')
    op.drop_table('companies')
    op.drop_table('field_labels')
    op.drop_table('field_definitions')
    op.drop_table('document_types')
