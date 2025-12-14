"""
Database models for Invoice Parser application - IMPROVED VERSION.
Addresses:
1. Unknown fields handling
2. Signatures/stamps storage
3. No unnecessary denormalization in documents
4. Dynamic columns for multi-language support
5. Proper column_mapping usage

Architecture designed for Human-in-the-Loop workflow with Raw vs Approved data.
"""
from datetime import datetime
from typing import Optional, List
from decimal import Decimal

from sqlalchemy import (
    BigInteger, String, Text, Boolean, Numeric, Date, ForeignKey,
    Index, UniqueConstraint, func
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB


class Base(DeclarativeBase):
    """Base class for all database models"""
    pass


# ============================================================================
# User Authentication
# ============================================================================

class User(Base):
    """
    User accounts for authentication.
    """
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True,
                                          comment='Unique username')
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True,
                                                 comment='User email address')
    hashed_password: Mapped[str] = mapped_column(String(255),
                                                 comment='Hashed password (bcrypt)')
    is_active: Mapped[bool] = mapped_column(Boolean, default=True,
                                            comment='User account is active')
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False,
                                               comment='User has superuser privileges')

    # Metadata
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(),
                                                  onupdate=func.now())
    last_login: Mapped[Optional[datetime]] = mapped_column(nullable=True,
                                                            comment='Last login timestamp')

    __table_args__ = (
        Index('ix_users_username', 'username'),
        Index('ix_users_email', 'email'),
    )


# ============================================================================
# Reference Tables (Dictionaries)
# ============================================================================

class DocumentType(Base):
    """
    Catalog of document types (Invoice, Waybill, TTN, etc.).
    """
    __tablename__ = 'document_types'

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True,
                                      comment='System code: UA_INVOICE, UA_TTN, FR_FACTURE, etc.')
    name: Mapped[str] = mapped_column(String(200),
                                     comment='Human readable name')
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    documents: Mapped[List["Document"]] = relationship(back_populates="document_type")


class FieldDefinition(Base):
    """
    Global dictionary of KNOWN document fields.
    Unknown fields will have field_id=NULL in document_fields table.
    """
    __tablename__ = 'field_definitions'

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True,
                                      comment='Internal code: invoice_number, supplier_name, vat_amount, etc.')
    section: Mapped[str] = mapped_column(String(50),
                                        comment='Section: header, supplier, buyer, totals, etc.')
    data_type: Mapped[str] = mapped_column(String(20),
                                          comment='Data type: text, number, date, boolean')
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    field_labels: Mapped[List["FieldLabel"]] = relationship(back_populates="field",
                                                             cascade="all, delete-orphan")


class FieldLabel(Base):
    """
    Multi-language labels for field definitions.
    """
    __tablename__ = 'field_labels'

    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(ForeignKey('field_definitions.id'))
    locale: Mapped[str] = mapped_column(String(10),
                                       comment='Language code: ru, uk, en, fr, etc.')
    label: Mapped[str] = mapped_column(String(200),
                                      comment='Translated label for this field')

    # Relationships
    field: Mapped["FieldDefinition"] = relationship(back_populates="field_labels")

    __table_args__ = (
        Index('ix_field_labels_field_locale', 'field_id', 'locale'),
    )


# ============================================================================
# Company / Counterparty Data (For Learning)
# ============================================================================

class Company(Base):
    """
    Counterparties (Suppliers and Buyers).
    Used for caching company details and learning parsing patterns.
    """
    __tablename__ = 'companies'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Basic info
    legal_name: Mapped[str] = mapped_column(Text,
                                           comment='Official legal name')
    short_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Identification numbers
    tax_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True,
                                                  comment='Tax ID / INN / EDRPOU')
    vat_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True,
                                                  comment='VAT registration number')
    registration_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True,
                                                             comment='Company registration code')

    # Location
    country: Mapped[Optional[str]] = mapped_column(String(10), nullable=True,
                                                   comment='Country code: UA, RU, FR, etc.')
    language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True,
                                                    comment='Primary language: uk, ru, en, etc.')
    address_legal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    address_postal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Banking
    iban: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    bank_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Contact
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # External system integration
    external_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True,
                                                       comment='ID in CRM/ERP system')
    external_system: Mapped[Optional[str]] = mapped_column(String(50), nullable=True,
                                                           comment='Name of external system')

    # Metadata
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False,
                                              comment='Verified by human moderator')
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(),
                                                 onupdate=func.now())

    # Relationships
    documents_as_supplier: Mapped[List["Document"]] = relationship(
        "Document",
        foreign_keys="[Document.supplier_id]",
        back_populates="supplier"
    )
    documents_as_buyer: Mapped[List["Document"]] = relationship(
        "Document",
        foreign_keys="[Document.buyer_id]",
        back_populates="buyer"
    )
    profiles: Mapped[List["CompanyDocumentProfile"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index('ix_companies_tax_id', 'tax_id'),
        Index('ix_companies_vat_id', 'vat_id'),
        Index('ix_companies_name', 'legal_name'),
    )


class CompanyDocumentProfile(Base):
    """
    Learning profiles for companies.
    Stores expected values and parsing rules for company-document combinations.
    """
    __tablename__ = 'company_document_profiles'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id'))
    doc_type_id: Mapped[int] = mapped_column(ForeignKey('document_types.id'))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Expected/default values
    expected_currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    expected_vat_mode: Mapped[Optional[str]] = mapped_column(String(50), nullable=True,
                                                             comment='general, simplified, no_vat, etc.')

    # Free-form settings in JSON for flexibility
    settings: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True,
                                                     comment='Parsing hints, templates, ML features, etc.')

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(),
                                                 onupdate=func.now())

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="profiles")
    doc_type: Mapped["DocumentType"] = relationship()


# ============================================================================
# Core Document Flow
# ============================================================================

class File(Base):
    """
    Physical files stored in filesystem/S3.
    """
    __tablename__ = 'files'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    storage_path: Mapped[str] = mapped_column(Text,
                                              comment='Full path: filesystem or S3 URL')
    original_filename: Mapped[str] = mapped_column(Text,
                                                   comment='Original filename from upload')
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True,
                                                     comment='SHA256 for deduplication')
    mime_type: Mapped[str] = mapped_column(String(100),
                                          comment='application/pdf, image/jpeg, etc.')
    size_bytes: Mapped[int] = mapped_column(BigInteger)

    uploaded_at: Mapped[datetime] = mapped_column(server_default=func.now())
    uploaded_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True,
                                                       comment='User ID or NULL for system')

    # Relationships
    documents: Mapped[List["Document"]] = relationship(back_populates="file")
    pages: Mapped[List["DocumentPage"]] = relationship(back_populates="file")

    __table_args__ = (
        Index('ix_files_hash', 'file_hash'),
    )


class Document(Base):
    """
    The central document entity.
    MINIMAL CORE DATA ONLY - no denormalization!
    All fields are in document_fields table.

    This table only contains:
    - Document identification (file, type, status)
    - Foreign keys to companies
    - Metadata (dates, users)
    """
    __tablename__ = 'documents'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(ForeignKey('files.id'))
    doc_type_id: Mapped[Optional[int]] = mapped_column(ForeignKey('document_types.id'),
                                                       nullable=True)

    # Document lifecycle status
    status: Mapped[str] = mapped_column(String(50), default='parsed',
                                       comment='parsed, in_review, approved, rejected, exported')

    # Language and location
    language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True,
                                                    comment='Document language: uk, ru, en, fr, etc.')
    country: Mapped[Optional[str]] = mapped_column(String(10), nullable=True,
                                                   comment='Document country: UA, RU, FR, etc.')

    # Foreign keys to companies (for fast filtering)
    supplier_id: Mapped[Optional[int]] = mapped_column(ForeignKey('companies.id'), nullable=True)
    buyer_id: Mapped[Optional[int]] = mapped_column(ForeignKey('companies.id'), nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(),
                                                 onupdate=func.now())
    updated_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Technical metadata
    parsing_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment='Model version, timing, AI request IDs, etc.'
    )

    # Relationships
    file: Mapped["File"] = relationship(back_populates="documents")
    document_type: Mapped[Optional["DocumentType"]] = relationship(back_populates="documents")
    supplier: Mapped[Optional["Company"]] = relationship(
        foreign_keys=[supplier_id],
        back_populates="documents_as_supplier"
    )
    buyer: Mapped[Optional["Company"]] = relationship(
        foreign_keys=[buyer_id],
        back_populates="documents_as_buyer"
    )
    snapshots: Mapped[List["DocumentSnapshot"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan"
    )
    fields: Mapped[List["DocumentField"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan"
    )
    table_sections: Mapped[List["DocumentTableSection"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan"
    )
    signatures: Mapped[List["DocumentSignature"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan"
    )
    pages: Mapped[List["DocumentPage"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index('ix_documents_status', 'status'),
        Index('ix_documents_supplier', 'supplier_id'),
        Index('ix_documents_buyer', 'buyer_id'),
        Index('ix_documents_created', 'created_at'),
    )


class DocumentPage(Base):
    """
    Individual pages of multi-page documents.
    """
    __tablename__ = 'document_pages'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey('documents.id'))
    file_id: Mapped[int] = mapped_column(ForeignKey('files.id'),
                                        comment='Link to page image file')

    page_number: Mapped[int] = mapped_column(comment='Page number (1-based)')
    ocr_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True,
                                                    comment='Full OCR text for this page')

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="pages")
    file: Mapped["File"] = relationship(back_populates="pages")

    __table_args__ = (
        Index('ix_document_pages_doc', 'document_id', 'page_number'),
    )


class DocumentSnapshot(Base):
    """
    Stores full JSON states of the document.
    Types: 'raw' (from AI), 'approved' (after user), 'crm_export', etc.
    """
    __tablename__ = 'document_snapshots'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey('documents.id'))

    snapshot_type: Mapped[str] = mapped_column(String(32),
                                               comment='raw, approved, crm_export, etc.')
    version: Mapped[int] = mapped_column(default=1,
                                        comment='Version number within same type')

    # Full JSON payload
    payload: Mapped[dict] = mapped_column(JSONB,
                                         comment='Complete JSON content')

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="snapshots")

    __table_args__ = (
        UniqueConstraint('document_id', 'snapshot_type', 'version',
                        name='uq_document_snapshot_type_version'),
        Index('ix_document_snapshots_doc_type', 'document_id', 'snapshot_type'),
    )


# ============================================================================
# Field Level Data - Universal flexible storage
# ============================================================================

class DocumentField(Base):
    """
    Stores individual fields extracted from document.

    HANDLES UNKNOWN FIELDS:
    - Known fields: field_id is set, field_code from dictionary
    - Unknown fields: field_id=NULL, field_code=NULL, raw_label has original text

    Each row contains BOTH raw (AI) and approved (human) values.
    """
    __tablename__ = 'document_fields'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey('documents.id'))

    # Field identification
    field_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('field_definitions.id'),
        nullable=True,
        comment='NULL for unknown fields'
    )
    field_code: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment='NULL for unknown fields'
    )

    # Grouping and organization
    section: Mapped[str] = mapped_column(
        String(50),
        comment='header, supplier, buyer, totals, signatures, other, etc.'
    )
    group_key: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment='Group identifier: supplier, buyer, signature_1, etc.'
    )

    # How field appears in document (CRITICAL for unknown fields!)
    raw_label: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment='Original label from document - used when field is unknown'
    )
    section_label: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment='Original section label from document (_label from JSON, e.g., "Постачальник:", "Покупець:")'
    )
    language: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment='Detected language'
    )

    # RAW values (from AI parser)
    raw_value_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_value_number: Mapped[Optional[Decimal]] = mapped_column(Numeric(30, 10), nullable=True)
    raw_value_date: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    raw_value_bool: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    raw_confidence: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
        comment='AI confidence: 0.00-1.00'
    )

    # APPROVED values (after user corrections)
    approved_value_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approved_value_number: Mapped[Optional[Decimal]] = mapped_column(Numeric(30, 10), nullable=True)
    approved_value_date: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    approved_value_bool: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    approved_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Control flags
    is_corrected: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment='True if user changed the value - CRITICAL for learning!'
    )
    is_ignored: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment='User marked as irrelevant'
    )

    # Links to snapshots
    raw_snapshot_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('document_snapshots.id'),
        nullable=True
    )
    approved_snapshot_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('document_snapshots.id'),
        nullable=True
    )

    # Page location
    page_id: Mapped[Optional[int]] = mapped_column(ForeignKey('document_pages.id'), nullable=True)
    bbox: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment='Bounding box: {x1, y1, x2, y2}'
    )

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now()
    )

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="fields")
    field_definition: Mapped[Optional["FieldDefinition"]] = relationship()

    __table_args__ = (
        Index('ix_document_fields_doc_section', 'document_id', 'section'),
        Index('ix_document_fields_code', 'field_code'),
        Index('ix_document_fields_corrected', 'is_corrected'),
        Index('ix_document_fields_unknown', 'field_id'),  # NULL values for unknown fields
    )


# ============================================================================
# Signatures and Stamps
# ============================================================================

class DocumentSignature(Base):
    """
    Stores signatures and stamps from documents.
    Can have 1, 2, 20, or any number of signatures.

    Handles the "signatures" array from JSON.
    """
    __tablename__ = 'document_signatures'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey('documents.id'))

    # Signature order
    signature_index: Mapped[int] = mapped_column(
        comment='Order in document (0-based)'
    )

    # Role information
    role: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment='Role: Бухгалтер, Отримав(ла), Director, etc.'
    )
    name: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment='Person name'
    )

    # Signature and stamp presence
    is_signed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment='Has handwritten signature'
    )
    is_stamped: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment='Has stamp/seal'
    )

    # Stamp content (if readable)
    stamp_content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment='Text extracted from stamp'
    )

    # Handwritten date (if present)
    handwritten_date: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment='Date written by hand near signature'
    )

    # RAW vs APPROVED (same pattern as fields)
    raw_value: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment='Original signature data from AI'
    )
    approved_value: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment='Corrected signature data'
    )
    is_corrected: Mapped[bool] = mapped_column(Boolean, default=False)

    # Page location
    page_id: Mapped[Optional[int]] = mapped_column(ForeignKey('document_pages.id'), nullable=True)
    bbox: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now()
    )

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="signatures")

    __table_args__ = (
        Index('ix_document_signatures_doc', 'document_id', 'signature_index'),
    )


# ============================================================================
# Table Data - Dynamic columns using column_mapping
# ============================================================================

class DocumentTableSection(Base):
    """
    Stores table data with DYNAMIC columns.

    Uses column_mapping pattern from prompts:
    - column_mapping: JSONB with {normalized_key: "Original Header"}
    - rows: Array of JSONB objects with dynamic keys

    This supports ANY table structure in ANY language!

    Example:
    column_mapping = {
        "no": "№",
        "ukt_zed": "УКТ ЗЕД",
        "tovar": "Товар",
        "kilkist": "Кількість"
    }

    rows = [
        {"no": 1, "ukt_zed": "8501510090", "tovar": "Motor...", "kilkist": "2 шт"},
        {"no": 2, "ukt_zed": "8501510090", "tovar": "Motor...", "kilkist": "2 шт"}
    ]
    """
    __tablename__ = 'document_table_sections'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey('documents.id'))

    # Table identification
    section_name: Mapped[str] = mapped_column(
        String(100),
        comment='Table name: line_items, deliveries, etc.'
    )
    section_order: Mapped[int] = mapped_column(
        default=0,
        comment='Order if multiple tables'
    )

    # Column mapping from prompt pattern
    column_mapping_raw: Mapped[dict] = mapped_column(
        JSONB,
        comment='RAW column mapping: {normalized: "Original Header"}'
    )
    column_mapping_approved: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment='APPROVED column mapping after corrections'
    )

    # Table rows as JSONB array
    rows_raw: Mapped[list] = mapped_column(
        JSONB,
        comment='RAW rows: array of objects with dynamic keys'
    )
    rows_approved: Mapped[Optional[list]] = mapped_column(
        JSONB,
        nullable=True,
        comment='APPROVED rows after corrections'
    )

    # Control
    is_corrected: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now()
    )

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="table_sections")

    __table_args__ = (
        Index('ix_document_table_sections_doc', 'document_id', 'section_order'),
    )
