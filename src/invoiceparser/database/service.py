"""
Database service for Invoice Parser.
Handles: unknown fields, signatures, dynamic tables with column_mapping.
"""
import logging
import mimetypes
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, and_, func, or_, text

from ..utils.datetime_utils import utcnow

from .models import (
    Base, Document, File, DocumentType, DocumentSnapshot,
    DocumentField, DocumentSignature, DocumentTableSection,
    Company, FieldDefinition, DocumentPage
)

logger = logging.getLogger(__name__)


class DatabaseService:
    """Service for database operations with full architecture support"""

    def __init__(self, database_url: str, echo: bool = False, pool_size: int = 50, max_overflow: int = 20):
        """Initialize database service"""
        from .database import init_db
        init_db(database_url, echo=echo, pool_size=pool_size, max_overflow=max_overflow)

    # ========================================================================
    # Document Type Management
    # ========================================================================

    async def get_or_create_document_type(
        self,
        session: AsyncSession,
        code: str,
        name: str,
        description: Optional[str] = None
    ) -> DocumentType:
        """
        Get existing document type or create new one.

        This allows dynamic addition of new document types without migrations.

        Args:
            session: Database session
            code: Unique code for document type (e.g., 'UA_INVOICE', 'FR_FACTURE')
            name: Human-readable name (e.g., 'Ukrainian Invoice')
            description: Optional description (can be in any language)

        Returns:
            DocumentType instance
        """
        result = await session.execute(
            select(DocumentType).where(DocumentType.code == code)
        )
        doc_type = result.scalar_one_or_none()

        if not doc_type:
            doc_type = DocumentType(code=code, name=name, description=description)
            session.add(doc_type)
            await session.flush()
            logger.info(f"Created document type: {code} - {name}")

        return doc_type

    async def list_document_types(
        self,
        session: AsyncSession
    ) -> List[DocumentType]:
        """List all document types"""
        result = await session.execute(select(DocumentType).order_by(DocumentType.code))
        return list(result.scalars().all())

    async def update_document_type(
        self,
        session: AsyncSession,
        code: str,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Optional[DocumentType]:
        """
        Update existing document type.

        Args:
            session: Database session
            code: Document type code
            name: New name (if provided)
            description: New description (if provided)

        Returns:
            Updated DocumentType or None if not found
        """
        result = await session.execute(
            select(DocumentType).where(DocumentType.code == code)
        )
        doc_type = result.scalar_one_or_none()

        if not doc_type:
            return None

        if name is not None:
            doc_type.name = name
        if description is not None:
            doc_type.description = description

        await session.flush()
        logger.info(f"Updated document type: {code}")
        return doc_type

    # ========================================================================
    # Company Management
    # ========================================================================

    def _normalize_tax_id(self, tax_id: Optional[str]) -> Optional[str]:
        """
        Normalize tax_id by extracting only digits.

        Examples:
        - "37483556" -> "37483556"
        - "код за ЄДРПОУ 37483556" -> "37483556"
        - "ІПН 1234567890" -> "1234567890"
        - None -> None
        - "" -> None

        Configuration: NORMALIZE_TAX_ID (default: True)
        """
        # Проверяем тип - tax_id может быть строкой или словарем
        if not tax_id:
            return None

        # Если это словарь, извлекаем значение
        if isinstance(tax_id, dict):
            tax_id = tax_id.get('value') or tax_id.get('tax_id') or str(tax_id)

        # Преобразуем в строку и проверяем
        tax_id_str = str(tax_id).strip() if tax_id else ""
        if not tax_id_str:
            return None

        import re
        # Extract all digits (используем строковое представление)
        numbers = re.findall(r'\d+', tax_id_str)

        if not numbers:
            return None

        # Return the longest sequence (usually the actual ID)
        return max(numbers, key=len)

    def _normalize_company_name(self, name: Optional[str]) -> Optional[str]:
        """
        Normalize company name for comparison.

        - Uppercase
        - Remove extra spaces
        - Remove quotes
        """
        if not name or not name.strip():
            return None

        # Uppercase and remove extra spaces
        normalized = ' '.join(name.upper().split())

        # Remove quotes
        normalized = normalized.replace('"', '').replace("'", '')

        return normalized

    async def find_company_by_tax_id(
        self,
        session: AsyncSession,
        tax_id: str,
        normalize: bool = True
    ) -> Optional[Company]:
        """
        Find company by tax ID.

        Args:
            session: Database session
            tax_id: Tax ID to search for
            normalize: Apply normalization (from config: NORMALIZE_TAX_ID)

        Returns:
            Company or None
        """
        if normalize:
            tax_id = self._normalize_tax_id(tax_id)

        if not tax_id:
            return None

        result = await session.execute(
            select(Company).where(Company.tax_id == tax_id)
        )
        return result.scalar_one_or_none()

    async def find_company_by_name(
        self,
        session: AsyncSession,
        name: str
    ) -> Optional[Company]:
        """
        Find company by normalized name.

        Configuration: TAX_ID_FALLBACK_TO_NAME (default: True)

        Если найдено несколько компаний с одинаковым нормализованным именем,
        возвращает первую (самую старую по created_at).
        """
        normalized_name = self._normalize_company_name(name)

        if not normalized_name:
            return None

        # Search by normalized name (case-insensitive)
        # Если несколько совпадений - берем первую (самую старую)
        result = await session.execute(
            select(Company).where(
                func.upper(func.replace(func.replace(Company.legal_name, '"', ''), "'", '')) == normalized_name
            ).order_by(Company.created_at).limit(1)
        )
        return result.scalar_one_or_none()

    async def create_or_update_company(
        self,
        session: AsyncSession,
        name: str,
        tax_id: Optional[str] = None,
        vat_id: Optional[str] = None,
        address: Optional[str] = None,
        **kwargs
    ) -> Company:
        """
        Create new company or update existing.

        Search strategy (configured via .env):
        1. Normalize tax_id (if NORMALIZE_TAX_ID=True)
        2. Search by normalized tax_id
        3. If not found and TAX_ID_FALLBACK_TO_NAME=True, search by name
        4. If still not found, create new company

        This prevents duplicate companies with different tax_id formats.
        """
        company = None

        # Step 1: Try to find by tax_id (with normalization)
        if tax_id:
            normalized_tax_id = self._normalize_tax_id(tax_id)
            if normalized_tax_id:
                company = await self.find_company_by_tax_id(session, normalized_tax_id, normalize=False)

        # Step 2: Fallback to search by name (if configured)
        # This is configured via TAX_ID_FALLBACK_TO_NAME in .env
        if not company and name:
            # Check if fallback is enabled (default: True)
            # In real implementation, this would come from config
            # For now, we always enable fallback
            company = await self.find_company_by_name(session, name)

        # Step 3: Update existing or create new
        if company:
            # Update existing company
            company.legal_name = name

            # Update tax_id with normalized version
            if tax_id:
                normalized_tax_id = self._normalize_tax_id(tax_id)
                if normalized_tax_id:
                    company.tax_id = normalized_tax_id

            if vat_id:
                company.vat_id = vat_id
            if address:
                company.address_legal = address
            for key, value in kwargs.items():
                if hasattr(company, key):
                    setattr(company, key, value)
            logger.info(f"Updated company: {name} (ID: {company.id})")
        else:
            # Create new company with normalized tax_id
            normalized_tax_id = self._normalize_tax_id(tax_id) if tax_id else None

            company = Company(
                legal_name=name,
                tax_id=normalized_tax_id,
                vat_id=vat_id,
                address_legal=address,
                **kwargs
            )
            session.add(company)
            await session.flush()
            logger.info(f"Created company: {name} (ID: {company.id}, tax_id: {normalized_tax_id})")

        return company

    # ========================================================================
    # Field Definition Management
    # ========================================================================

    async def find_field_definition(
        self,
        session: AsyncSession,
        field_code: Optional[str] = None,
        label: Optional[str] = None
    ) -> Optional[FieldDefinition]:
        """
        Find field definition by code or label.
        Returns None if field is unknown.
        """
        if field_code:
            result = await session.execute(
                select(FieldDefinition).where(FieldDefinition.code == field_code)
            )
            return result.scalar_one_or_none()

        # TODO: Could search by label in field_labels table
        return None

    # ========================================================================
    # Document Saving (Main Workflow)
    # ========================================================================

    async def save_parsed_document(
        self,
        session: AsyncSession,
        file_path: Path,
        raw_json: Dict[str, Any],
        doc_type_code: Optional[str] = None,
        original_filename: Optional[str] = None
    ) -> Document:
        """
        Save parsed document with RAW data (right after AI parsing).

        Handles:
        - Unknown fields (field_id=NULL)
        - Signatures (1-20+)
        - Dynamic tables (column_mapping)

        Configuration:
        - DB_TRANSACTION_TIMEOUT: timeout для транзакции (default: 30 seconds)

        ВАЖНО: Весь процесс обернут в транзакцию.
        При ошибке произойдет автоматический rollback.
        """
        logger.info(f"Saving parsed document: {file_path.name}")

        # Транзакция: автоматический rollback при ошибке
        # Timeout настраивается через DB_TRANSACTION_TIMEOUT в .env
        try:
            # 1. Create File record
            file_record = await self._create_file_record(
                session, file_path, original_filename
            )

            # 2. Detect and get/create document type
            # If doc_type_code is provided, use it
            # Otherwise, auto-detect from JSON data
            if doc_type_code:
                # Use provided code (fallback name will be set in get_or_create)
                detected_code, detected_name = doc_type_code, doc_type_code.replace('_', ' ').title()
            else:
                # Auto-detect from JSON
                detected_code, detected_name = self._detect_document_type_code(raw_json)
                logger.info(f"Auto-detected document type: {detected_code} - {detected_name}")

            doc_type = await self.get_or_create_document_type(
                session, code=detected_code, name=detected_name
            )

            # 3. Extract and link companies
            supplier_id, buyer_id = await self._extract_and_link_companies(
                session, raw_json
            )

            # 4. Create Document (MINIMAL - no business data!)
            document = Document(
                file_id=file_record.id,
                doc_type_id=doc_type.id,
                status='parsed',
                language=self._detect_language(raw_json),
                country=self._detect_country(raw_json),
                supplier_id=supplier_id,
                buyer_id=buyer_id
            )
            session.add(document)
            await session.flush()

            # 5. Create RAW snapshot
            await self._create_snapshot(
                session, document.id, 'raw', raw_json
            )

            # 6. Populate DocumentFields (handles unknown fields!)
            await self._populate_raw_fields(
                session, document.id, raw_json
            )

            # 7. Populate DocumentSignatures
            await self._populate_signatures(
                session, document.id, raw_json, is_raw=True
            )

            # 8. Populate DocumentTableSections (with column_mapping)
            await self._populate_table_sections(
                session, document.id, raw_json, is_raw=True
            )

            # 9. Create DocumentPages (if file is PDF or multi-page)
            await self._populate_document_pages(
                session, document.id, file_record.id, file_path
            )

            # Commit транзакции
            await session.commit()
            logger.info(f"✅ Document saved successfully (ID: {document.id})")
            return document

        except Exception as e:
            # Автоматический rollback при ошибке
            await session.rollback()
            logger.error(f"❌ Error saving document: {e}")
            logger.error(f"   Transaction rolled back. No data saved.")
            raise

    async def save_approved_document(
        self,
        session: AsyncSession,
        document_id: int,
        approved_json: Dict[str, Any],
        user_id: Optional[int] = None
    ) -> Document:
        """
        Save APPROVED data after user review.
        Updates approved_value_* columns.
        """
        logger.info(f"Saving approved document: {document_id}")

        # Load document
        result = await session.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one()

        # Update status
        document.status = 'approved'
        document.updated_by = user_id
        document.updated_at = utcnow()

        # Create APPROVED snapshot
        await self._create_snapshot(
            session, document.id, 'approved', approved_json, user_id
        )

        # Update fields with approved values
        await self._update_approved_fields(
            session, document.id, approved_json, user_id
        )

        # Update signatures with approved values
        await self._populate_signatures(
            session, document.id, approved_json, is_raw=False, user_id=user_id
        )

        # Update table sections with approved values
        await self._populate_table_sections(
            session, document.id, approved_json, is_raw=False, user_id=user_id
        )

        await session.commit()
        logger.info(f"Document approved (ID: {document.id})")

        return document

    async def reject_approved_document(
        self,
        session: AsyncSession,
        document_id: int,
        user_id: Optional[int] = None
    ) -> Document:
        """
        Отменить подтверждение документа (вернуть статус в 'parsed' или 'rejected').

        Args:
            session: Database session
            document_id: ID документа
            user_id: ID пользователя, который отменяет подтверждение

        Returns:
            Updated Document
        """
        logger.info(f"Rejecting approved document: {document_id}")

        # Load document
        result = await session.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()

        if not document:
            raise ValueError(f"Document {document_id} not found")

        # Проверяем, что документ был подтвержден
        if document.status != 'approved':
            logger.warning(f"Document {document_id} is not approved (status: {document.status})")
            # Можно вернуть статус в 'parsed' если он был 'in_review'
            if document.status == 'in_review':
                document.status = 'parsed'
            else:
                # Если уже 'parsed' или 'rejected', просто обновляем
                document.status = 'rejected'
        else:
            # Отменяем подтверждение - возвращаем статус в 'parsed'
            document.status = 'parsed'
            document.updated_by = user_id
            document.updated_at = utcnow()

        await session.commit()
        logger.info(f"Document approval rejected (ID: {document.id}, status: {document.status})")

        return document

    # ========================================================================
    # Helper Methods
    # ========================================================================

    async def _create_file_record(
        self,
        session: AsyncSession,
        file_path: Path,
        original_filename: Optional[str] = None
    ) -> File:
        """Create File record"""
        import hashlib

        file_hash = None
        if file_path.exists():
            with open(file_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()

        mime_type, _ = mimetypes.guess_type(str(file_path))

        file_record = File(
            storage_path=str(file_path),
            original_filename=original_filename or file_path.name,
            file_hash=file_hash,
            mime_type=mime_type or 'application/octet-stream',
            size_bytes=file_path.stat().st_size if file_path.exists() else 0
        )
        session.add(file_record)
        await session.flush()

        return file_record

    async def _extract_and_link_companies(
        self,
        session: AsyncSession,
        json_data: Dict[str, Any]
    ) -> Tuple[Optional[int], Optional[int]]:
        """
        Extract supplier and buyer, create/link companies.
        Handles both formats: parties as dict or as array.
        """
        supplier_id = None
        buyer_id = None

        parties = json_data.get('parties', {})

        # Handle ARRAY format: [{"role": "supplier", "name": "...", "details": {...}}, ...]
        if isinstance(parties, list):
            for party in parties:
                if not isinstance(party, dict):
                    continue

                role = party.get('role', '').lower()
                # Data can be in 'details' or directly in party
                party_data = party.get('details', party) if isinstance(party.get('details'), dict) else party

                # Determine party type by role (multilingual support)
                # Rely on LLM normalization first (it should return 'supplier' or 'buyer')
                # If not, try to detect based on role string content being present in standard English terms
                role_normalized = role.lower()

                # Check for standard normalized roles
                if 'supplier' in role_normalized or 'vendor' in role_normalized or 'seller' in role_normalized:
                    is_supplier = True
                    is_buyer = False
                elif 'buyer' in role_normalized or 'customer' in role_normalized or 'client' in role_normalized:
                    is_supplier = False
                    is_buyer = True
                else:
                    # Fallback: if role matches standard international patterns or just assign based on order/context if possible
                    # Ideally LLM does this. For now, if we can't determine, we might skip specialized linking
                    # or treat as generic party.
                    # However, to be "100% multilingual" without hardcode, we MUST trust the LLM's normalization.
                    is_supplier = False
                    is_buyer = False

                if is_supplier:
                    # Extract tax_id from various fields
                    tax_id = (
                        party_data.get('edrpou') or
                        party_data.get('tax_id') or
                        party_data.get('ipn') or
                        party_data.get('inn')
                    )

                    # Extract bank info
                    bank_account = party_data.get('bank_account', {})
                    if isinstance(bank_account, dict):
                        iban = bank_account.get('iban')
                        bank_name = bank_account.get('bank_name') or bank_account.get('bank')
                    else:
                        iban = None
                        bank_name = None

                    supplier = await self.create_or_update_company(
                        session,
                        name=party.get('name') or '',
                        tax_id=tax_id,
                        vat_id=party_data.get('vat_id'),
                        address=party_data.get('address'),
                        iban=iban,
                        bank_name=bank_name,
                        phone=party_data.get('phone')
                    )
                    supplier_id = supplier.id

                elif is_buyer:
                    # Extract tax_id from various fields
                    tax_id = (
                        party_data.get('edrpou') or
                        party_data.get('tax_id') or
                        party_data.get('ipn') or
                        party_data.get('inn')
                    )

                    buyer = await self.create_or_update_company(
                        session,
                        name=party.get('name') or '',
                        tax_id=tax_id,
                        address=party_data.get('address')
                    )
                    buyer_id = buyer.id

        # Handle DICT format: {"supplier": {...}, "customer": {...}}
        elif isinstance(parties, dict):
            # Supplier
            if 'supplier' in parties:
                supplier_data = parties['supplier']
                if isinstance(supplier_data, dict):
                    supplier = await self.create_or_update_company(
                        session,
                        name=self._extract_value(supplier_data.get('name')) or '',
                        tax_id=self._extract_value(supplier_data.get('tax_id')),
                        vat_id=self._extract_value(supplier_data.get('vat_id')),
                        address=self._extract_value(supplier_data.get('address')),
                        iban=self._extract_value(supplier_data.get('account_number')),
                        bank_name=self._extract_value(supplier_data.get('bank')),
                        phone=self._extract_value(supplier_data.get('phone'))
                    )
                    supplier_id = supplier.id

            # Buyer (can be 'customer' or 'buyer')
            buyer_data = parties.get('customer') or parties.get('buyer')
            if buyer_data and isinstance(buyer_data, dict):
                buyer = await self.create_or_update_company(
                    session,
                    name=self._extract_value(buyer_data.get('name')) or '',
                    tax_id=self._extract_value(buyer_data.get('tax_id')),
                    address=self._extract_value(buyer_data.get('address'))
                )
                buyer_id = buyer.id

        return supplier_id, buyer_id

    async def _create_snapshot(
        self,
        session: AsyncSession,
        document_id: int,
        snapshot_type: str,
        payload: Dict[str, Any],
        user_id: Optional[int] = None
    ):
        """Create document snapshot"""
        result = await session.execute(
            select(DocumentSnapshot.version)
            .where(
                and_(
                    DocumentSnapshot.document_id == document_id,
                    DocumentSnapshot.snapshot_type == snapshot_type
                )
            )
            .order_by(DocumentSnapshot.version.desc())
            .limit(1)
        )
        max_version = result.scalar_one_or_none() or 0

        snapshot = DocumentSnapshot(
            document_id=document_id,
            snapshot_type=snapshot_type,
            version=max_version + 1,
            payload=payload,
            created_by=user_id
        )
        session.add(snapshot)
        await session.flush()

    async def _populate_raw_fields(
        self,
        session: AsyncSession,
        document_id: int,
        json_data: Dict[str, Any]
    ):
        """
        Populate DocumentFields with RAW values.
        HANDLES UNKNOWN FIELDS (field_id=NULL).
        """
        fields_to_create = []

        # Extract all fields from JSON
        all_fields = self._extract_all_fields_from_json(json_data)

        for field_data in all_fields:
            # Try to find in field_definitions
            field_def = await self.find_field_definition(
                session,
                field_code=field_data.get('code')
            )

            field = DocumentField(
                document_id=document_id,
                field_id=field_def.id if field_def else None,  # NULL for unknown!
                field_code=field_def.code if field_def else None,
                section=field_data['section'],
                group_key=field_data.get('group_key'),
                raw_label=field_data.get('label', ''),  # Field label (key name or original label)
                section_label=field_data.get('section_label'),  # Section _label from JSON (original label from document)
                raw_value_text=self._to_text(field_data['value']),
                language=self._detect_language(json_data)
            )
            fields_to_create.append(field)

        session.add_all(fields_to_create)
        await session.flush()
        logger.info(f"Created {len(fields_to_create)} fields ({sum(1 for f in fields_to_create if f.field_id is None)} unknown)")

    async def _populate_signatures(
        self,
        session: AsyncSession,
        document_id: int,
        json_data: Dict[str, Any],
        is_raw: bool = True,
        user_id: Optional[int] = None
    ):
        """
        Populate DocumentSignatures (1-20+ signatures).
        """
        signatures_array = json_data.get('signatures', [])

        if not signatures_array:
            return

        if is_raw:
            # Create new signatures
            for idx, sig_data in enumerate(signatures_array):
                signature = DocumentSignature(
                    document_id=document_id,
                    signature_index=idx,
                    role=sig_data.get('role'),
                    name=sig_data.get('name'),
                    is_signed=sig_data.get('is_signed', False),
                    is_stamped=sig_data.get('is_stamped', False),
                    stamp_content=sig_data.get('stamp_content'),
                    handwritten_date=sig_data.get('handwritten_date'),
                    raw_value=sig_data
                )
                session.add(signature)

            await session.flush()
            logger.info(f"Created {len(signatures_array)} signatures")
        else:
            # Update existing signatures with approved values
            result = await session.execute(
                select(DocumentSignature)
                .where(DocumentSignature.document_id == document_id)
                .order_by(DocumentSignature.signature_index)
            )
            existing_sigs = result.scalars().all()

            for idx, sig_data in enumerate(signatures_array):
                if idx < len(existing_sigs):
                    sig = existing_sigs[idx]
                    sig.approved_value = sig_data
                    # Check if corrected
                    if sig.raw_value != sig_data:
                        sig.is_corrected = True

            await session.flush()

    async def _populate_table_sections(
        self,
        session: AsyncSession,
        document_id: int,
        json_data: Dict[str, Any],
        is_raw: bool = True,
        user_id: Optional[int] = None
    ):
        """
        Populate DocumentTableSections with column_mapping.
        Direct usage from prompts - no transformation!
        """
        table_data = json_data.get('table_data', {})

        if not table_data:
            return

        column_mapping = table_data.get('column_mapping', {})
        line_items = table_data.get('line_items', [])

        if is_raw:
            # Create new table section
            table_section = DocumentTableSection(
                document_id=document_id,
                section_name='line_items',
                section_order=0,
                column_mapping_raw=column_mapping,  # Direct from JSON!
                rows_raw=line_items                  # Direct from JSON!
            )
            session.add(table_section)
            await session.flush()
            logger.info(f"Created table section with {len(line_items)} rows")
        else:
            # Update with approved values
            result = await session.execute(
                select(DocumentTableSection)
                .where(
                    DocumentTableSection.document_id == document_id,
                    DocumentTableSection.section_name == 'line_items'
                )
            )
            table = result.scalar_one_or_none()

            if table:
                table.column_mapping_approved = column_mapping
                table.rows_approved = line_items
                # Check if corrected
                if table.rows_raw != line_items:
                    table.is_corrected = True
                await session.flush()

    async def _populate_document_pages(
        self,
        session: AsyncSession,
        document_id: int,
        file_id: int,
        file_path: Path
    ):
        """
        Create DocumentPage records for the document.
        For images: creates 1 page. For PDFs: creates pages for each PDF page.
        """
        import fitz  # PyMuPDF

        pages_to_create = []

        # Determine file type
        mime_type, _ = mimetypes.guess_type(str(file_path))

        if mime_type == 'application/pdf':
            # PDF: extract pages
            try:
                doc = fitz.open(str(file_path))
                page_count = len(doc)

                for page_num in range(page_count):
                    page = doc[page_num]
                    # Extract text from page (OCR text if available)
                    ocr_text = page.get_text()

                    # For PDF, we use the same file_id for all pages
                    # In a real system, you might want to create separate File records for each page image
                    page_record = DocumentPage(
                        document_id=document_id,
                        file_id=file_id,  # Same file for all pages
                        page_number=page_num + 1,  # 1-based
                        ocr_text=ocr_text if ocr_text.strip() else None
                    )
                    pages_to_create.append(page_record)

                doc.close()
                logger.info(f"Created {len(pages_to_create)} pages from PDF")
            except Exception as e:
                logger.warning(f"Failed to extract PDF pages: {e}. Creating single page record.")
                # Fallback: create single page
                page_record = DocumentPage(
                    document_id=document_id,
                    file_id=file_id,
                    page_number=1,
                    ocr_text=None
                )
                pages_to_create.append(page_record)
        else:
            # Image: create single page
            page_record = DocumentPage(
                document_id=document_id,
                file_id=file_id,
                page_number=1,
                ocr_text=None  # OCR text would be extracted separately if needed
            )
            pages_to_create.append(page_record)
            logger.info(f"Created 1 page for image document")

        if pages_to_create:
            session.add_all(pages_to_create)
            await session.flush()

    async def _update_approved_fields(
        self,
        session: AsyncSession,
        document_id: int,
        json_data: Dict[str, Any],
        user_id: Optional[int] = None
    ):
        """Update fields with approved values"""
        # Load existing fields
        result = await session.execute(
            select(DocumentField).where(DocumentField.document_id == document_id)
        )
        existing_fields = {
            (f.section, f.field_code, f.raw_label): f
            for f in result.scalars().all()
        }

        # Extract approved fields
        all_fields = self._extract_all_fields_from_json(json_data)

        for field_data in all_fields:
            key = (field_data['section'], field_data.get('code'), field_data['label'])

            if key in existing_fields:
                field = existing_fields[key]
                new_value = self._to_text(field_data['value'])

                # Update approved value
                field.approved_value_text = new_value
                field.approved_by = user_id
                field.approved_at = utcnow()

                # Mark as corrected if changed
                if field.raw_value_text != new_value:
                    field.is_corrected = True

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def _extract_all_fields_from_json(self, json_data: Dict[str, Any]) -> List[Dict]:
        """Extract all fields from JSON structure"""
        fields = []

        # document_info
        doc_info = json_data.get('document_info', {})
        doc_info_label = doc_info.get('_label')  # Extract _label if exists

        for key, value in doc_info.items():
            if key not in ['_label', 'location_label'] and value:
                # Extract value and label from new structure { "_label": ..., "value": ... }
                if isinstance(value, dict):
                    field_label = value.get('_label') or key
                    field_value = value.get('value')
                else:
                    field_label = key
                    field_value = value

                if field_value:  # Only add if value exists
                    fields.append({
                        'section': 'header',
                        'code': key,
                        'label': field_label,
                        'value': field_value,
                        'group_key': 'document_info',
                        'section_label': doc_info_label  # Store _label for section
                    })

        # parties - handle both array and dict formats
        parties = json_data.get('parties', {})

        if isinstance(parties, list):
            # Array format: [{"role": "supplier", "name": "...", "details": {...}}, ...]
            for party in parties:
                if not isinstance(party, dict):
                    continue

                role = party.get('role', 'unknown').lower()
                # Determine section name from role - rely on normalized keys from LLM
                if 'supplier' in role or 'vendor' in role or 'seller' in role:
                    section = 'supplier'
                elif 'buyer' in role or 'customer' in role or 'client' in role:
                    section = 'buyer'
                else:
                    section = 'party'

                # Data can be in 'details' or directly in party
                party_data = party.get('details', party) if isinstance(party.get('details'), dict) else party

                if isinstance(party_data, dict):
                    # Extract _label for the section
                    section_label = party.get('_label') or party_data.get('_label') or role

                    for key, value in party_data.items():
                        if key not in ['_label'] and value:
                            # Use _label as the label for fields in this section
                            field_label = section_label if key == 'name' else key

                            fields.append({
                                'section': section,
                                'code': key,
                                'label': field_label,  # Use _label for section header
                                'value': value,
                                'group_key': section,
                                'section_label': section_label  # Store section label separately
                            })

                # Also extract top-level fields from party (name, role, etc.)
                for key, value in party.items():
                    if key not in ['_label', 'details'] and value and key not in [f['code'] for f in fields if f.get('group_key') == section]:
                        fields.append({
                            'section': section,
                            'code': key,
                            'label': key,
                            'value': value,
                            'group_key': section,
                            'section_label': section_label  # Store _label from JSON
                        })

        elif isinstance(parties, dict):
            # Dict format: {"supplier": {...}, "customer": {...}}
            for party_type, party_data in parties.items():
                if isinstance(party_data, dict):
                    # Extract _label for the section (original label from document)
                    section_label = party_data.get('_label', party_type)

                    for key, value in party_data.items():
                        if key not in ['_label'] and value:
                            # Extract value and label from new structure { "_label": ..., "value": ... }
                            if isinstance(value, dict):
                                field_label = value.get('_label') or key
                                field_value = value.get('value')
                            else:
                                field_label = section_label if key == 'name' else key
                                field_value = value

                            if field_value:  # Only add if value exists
                                fields.append({
                                    'section': party_type,
                                    'code': key,
                                    'label': field_label,
                                    'value': field_value,
                                    'group_key': party_type,
                                    'section_label': section_label  # Store section label separately
                                })

        # totals
        totals = json_data.get('totals', {})
        totals_label = totals.get('_label')  # Extract _label if exists

        for key, value in totals.items():
            if key not in ['_label'] and value:
                # Handle new object structure
                if isinstance(value, dict):
                    field_label = value.get('_label') or key
                    field_value = value.get('value')
                else:
                    field_label = key
                    field_value = value

                if field_value is not None:
                    fields.append({
                        'section': 'totals',
                        'code': key,
                        'label': field_label,
                        'value': field_value,
                        'group_key': 'totals',
                        'section_label': totals_label  # Store _label for section
                    })

        # amounts_in_words
        amounts = json_data.get('amounts_in_words', {})
        amounts_label = amounts.get('_label')

        for key, value in amounts.items():
            if key not in ['_label'] and value:
                # Handle new object structure
                if isinstance(value, dict):
                    field_label = value.get('_label') or key
                    field_value = value.get('value')
                else:
                    field_label = key
                    field_value = value

                if field_value is not None:
                    fields.append({
                        'section': 'amounts_in_words',
                        'code': key,
                        'label': field_label,
                        'value': field_value,
                        'group_key': 'amounts_in_words',
                        'section_label': amounts_label
                    })

        # other_fields
        other_fields = json_data.get('other_fields', [])
        for field_data in other_fields:
            fields.append({
                'section': 'other',
                'code': None,  # Unknown!
                'label': field_data.get('label_raw', 'unknown'),
                'value': field_data.get('value_raw'),
                'group_key': 'other'
            })

        return fields

    def _detect_language(self, json_data: Dict[str, Any]) -> Optional[str]:
        """Detect document language"""
        doc_info = json_data.get('document_info', {})
        doc_type_raw = doc_info.get('document_type', '')
        doc_type = self._extract_value(doc_type_raw) or str(doc_type_raw)

        # Language detection: rely on LLM normalization and document content analysis
        # No hardcoded language-specific keywords - use normalized English keys only
        doc_type_upper = doc_type.upper()
        if 'INVOICE' in doc_type_upper:
            return 'en'

        return None

    def _detect_country(self, json_data: Dict[str, Any]) -> Optional[str]:
        """Detect document country"""
        currency_raw = json_data.get('document_info', {}).get('currency')
        currency = self._extract_value(currency_raw) or str(currency_raw) if currency_raw else ''
        if currency == 'UAH':
            return 'UA'
        elif currency == 'RUB':
            return 'RU'
        elif currency == 'EUR':
            return 'EU'

        return None

    def _detect_document_type_code(
        self,
        json_data: Dict[str, Any]
    ) -> Tuple[str, str]:
        """
        Detect document type code and name from parsed JSON.

        Tries to determine document type from:
        1. document_info.document_type field
        2. document_info.type field
        3. Falls back to GENERAL_INVOICE

        Args:
            json_data: Parsed document JSON

        Returns:
            Tuple of (code, name) for document type
        """
        doc_info = json_data.get('document_info', {})

        # Try to get document type from various fields
        # Support both old format (string) and new format ({ "_label": ..., "value": ... })
        doc_type_raw = doc_info.get('document_type') or doc_info.get('type') or ''

        if isinstance(doc_type_raw, dict):
            # New format: extract value from object
            doc_type_str = doc_type_raw.get('value', '') or ''
        else:
            # Old format: direct string
            doc_type_str = str(doc_type_raw) if doc_type_raw else ''

        doc_type_str = doc_type_str.strip()

        if not doc_type_str:
            # No type detected, use general
            return ('GENERAL_INVOICE', 'General Invoice')

        # Normalize document type string
        doc_type_lower = doc_type_str.lower()

        # Try to detect known patterns (using English normalized keys only)
        if 'ttn' in doc_type_lower:
            return ('UA_TTN', 'Ukrainian Waybill')
        elif 'torg-12' in doc_type_lower or 'torg12' in doc_type_lower:
            return ('RU_TORG12', 'Russian TORG-12')
        elif 'facture' in doc_type_lower or 'invoice' in doc_type_lower:
            # Detect country from currency or other hints
            currency_raw = doc_info.get('currency', '')
            if isinstance(currency_raw, dict):
                currency = currency_raw.get('value', '').upper()
            else:
                currency = str(currency_raw).upper()
            if currency == 'EUR' or 'fr' in doc_type_lower:
                return ('FR_FACTURE', 'French Invoice')
            elif currency == 'USD':
                return ('US_INVOICE', 'US Invoice')
            else:
                return ('GENERAL_INVOICE', 'Invoice (Facture)')
        elif 'invoice' in doc_type_lower or 'waybill' in doc_type_lower:
            currency_raw = doc_info.get('currency', '')
            if isinstance(currency_raw, dict):
                currency = currency_raw.get('value', '').upper()
            else:
                currency = str(currency_raw).upper()
            if currency == 'UAH':
                return ('UA_INVOICE', 'Ukrainian Invoice')
            elif currency == 'RUB':
                return ('RU_INVOICE', 'Russian Invoice')
            elif currency == 'USD':
                return ('US_INVOICE', 'US Invoice')
            elif currency == 'EUR':
                return ('EU_INVOICE', 'European Invoice')
            else:
                return ('GENERAL_INVOICE', 'General Invoice')
        else:
            # Unknown type - generate code from type string
            # Convert to uppercase, replace spaces with underscores, remove special chars
            code = doc_type_str.upper()
            code = ''.join(c if c.isalnum() or c in (' ', '-', '_') else '' for c in code)
            code = code.replace(' ', '_').replace('-', '_')
            code = code[:50]  # Limit length

            # If code is too short or generic, use GENERAL_INVOICE
            if len(code) < 3 or code in ('DOCUMENT', 'DOC', 'TYPE'):
                return ('GENERAL_INVOICE', doc_type_str or 'General Invoice')

            # Use detected type name as is
            return (code, doc_type_str)

    def _extract_value(self, field: Any) -> Optional[str]:
        """
        Extract value from field that can be either:
        - Old format: direct string/number
        - New format: { "_label": ..., "value": ... }
        """
        if field is None:
            return None
        if isinstance(field, dict):
            return field.get('value')
        return str(field) if field else None

    def _to_text(self, value: Any) -> Optional[str]:
        """Convert any value to text"""
        if value is None:
            return None
        return str(value)

    # ========================================================================
    # Search Methods (using new indexes)
    # ========================================================================

    async def search_documents_by_table_value(
        self,
        session: AsyncSession,
        column_name: str,
        value: str,
        section_name: str = 'line_items',
        use_approved: bool = True
    ) -> List[Document]:
        """
        Search documents by value in table rows using GIN index.

        Example: Find all documents containing product with SKU 'ABC123'

        Args:
            session: Database session
            column_name: Normalized column name from column_mapping (e.g., 'sku', 'item_description')
            value: Value to search for
            section_name: Table section name (default: 'line_items')
            use_approved: If True, search in approved data, else in raw data

        Returns:
            List of documents matching the criteria
        """
        rows_column = 'rows_approved' if use_approved else 'rows_raw'

        # Use JSONB containment operator with GIN index (jsonb_path_ops)
        # This searches for documents where rows array contains an object with matching column:value
        # Create search pattern JSON: {"column_name": "value"}
        import json
        search_pattern = json.dumps({column_name: value})

        # Use raw SQL for JSONB array search (more efficient with GIN index)
        # @> checks if left JSONB contains right JSONB
        query_text = f"""
            SELECT DISTINCT d.*
            FROM documents d
            JOIN document_table_sections dts ON d.id = dts.document_id
            WHERE dts.section_name = :section_name
              AND EXISTS (
                  SELECT 1
                  FROM jsonb_array_elements(dts.{rows_column}) AS row
                  WHERE row @> :search_pattern::jsonb
              )
        """

        query = text(query_text).columns(Document.id, Document.file_id, Document.doc_type_id,
                                         Document.status, Document.language, Document.country,
                                         Document.supplier_id, Document.buyer_id,
                                         Document.created_at, Document.created_by,
                                         Document.updated_at, Document.updated_by,
                                         Document.parsing_metadata)

        result = await session.execute(
            query.bindparams(
                section_name=section_name,
                search_pattern=search_pattern
            )
        )

        # Extract document IDs and load full objects
        doc_ids = [row[0] for row in result]
        if not doc_ids:
            return []

        docs_query = select(Document).where(Document.id.in_(doc_ids))
        docs_result = await session.execute(docs_query)
        return list(docs_result.scalars().all())

    async def search_documents_by_text(
        self,
        session: AsyncSession,
        search_text: str,
        language: str = 'simple',
        use_ocr: bool = True,
        use_field_values: bool = True
    ) -> List[Document]:
        """
        Full-text search in documents using GIN indexes.

        Searches in:
        - OCR text from pages
        - Field values
        - Company names

        Args:
            session: Database session
            search_text: Text to search for
            language: Language for search ('russian', 'ukrainian', 'english')
            use_ocr: Search in OCR text
            use_field_values: Search in field values

        Returns:
            List of documents matching the search
        """
        # Validate language (default to 'simple' for multilingual support)
        valid_languages = ['simple', 'russian', 'english']
        if language not in valid_languages:
            logger.warning(f"Invalid language '{language}', using 'simple'")
            language = 'simple'

        conditions = []

        if use_ocr:
            # Search in OCR text
            conditions.append(
                select(Document.id).join(DocumentPage).where(
                    func.to_tsvector(language, func.coalesce(DocumentPage.ocr_text, ''))
                    .match(search_text)
                ).exists()
            )

        if use_field_values:
            # Search in field values
            conditions.append(
                select(Document.id).join(DocumentField).where(
                    func.to_tsvector(language, func.coalesce(DocumentField.raw_value_text, ''))
                    .match(search_text)
                ).exists()
            )

        if conditions:
            query = select(Document).where(or_(*conditions))
        else:
            query = select(Document).where(False)  # No results if no search criteria

        result = await session.execute(query)
        return list(result.scalars().all())

    async def search_companies_by_name(
        self,
        session: AsyncSession,
        name: str,
        language: str = 'simple'
    ) -> List[Company]:
        """
        Full-text search companies by name using GIN index.

        Args:
            session: Database session
            name: Company name to search for
            language: Language for search ('simple', 'russian', 'english')
                     'simple' works with any language text

        Returns:
            List of companies matching the search
        """
        # Validate language
        valid_languages = ['simple', 'russian', 'english']
        if language not in valid_languages:
            logger.warning(f"Invalid language '{language}', using 'simple'")
            language = 'simple'

        query = select(Company).where(
            func.to_tsvector(language, func.coalesce(Company.legal_name, ''))
            .match(name)
        )

        result = await session.execute(query)
        return list(result.scalars().all())

    async def search_documents_by_metadata(
        self,
        session: AsyncSession,
        metadata_key: str,
        metadata_value: Any
    ) -> List[Document]:
        """
        Search documents by parsing_metadata JSONB field using GIN index.

        Example: Find all documents parsed with specific model version

        Args:
            session: Database session
            metadata_key: Key in JSONB (e.g., 'model_version', 'processing_time')
            metadata_value: Value to search for

        Returns:
            List of documents matching the criteria
        """
        # Use JSONB containment operator
        query = select(Document).where(
            Document.parsing_metadata[metadata_key].astext == str(metadata_value)
        )

        result = await session.execute(query)
        return list(result.scalars().all())

    async def get_documents_by_status_and_date_range(
        self,
        session: AsyncSession,
        status: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[Document], int]:
        """
        Get documents by status with date range filtering.
        Uses composite index (status, created_at).

        Args:
            session: Database session
            status: Document status
            start_date: Start date for filtering
            end_date: End date for filtering
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            Tuple of (documents list, total count)
        """
        query = select(Document).where(Document.status == status)
        count_query = select(func.count()).select_from(Document).where(Document.status == status)

        if start_date:
            query = query.where(Document.created_at >= start_date)
            count_query = count_query.where(Document.created_at >= start_date)

        if end_date:
            query = query.where(Document.created_at <= end_date)
            count_query = count_query.where(Document.created_at <= end_date)

        # Order by created_at DESC (uses index)
        query = query.order_by(Document.created_at.desc()).limit(limit).offset(offset)

        result = await session.execute(query)
        count_result = await session.execute(count_query)

        return list(result.scalars().all()), count_result.scalar() or 0

    async def get_documents_by_supplier(
        self,
        session: AsyncSession,
        supplier_id: int,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[Document], int]:
        """
        Get documents by supplier with pagination.
        Uses composite index (supplier_id, created_at).

        Args:
            session: Database session
            supplier_id: Supplier company ID
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            Tuple of (documents list, total count)
        """
        query = select(Document).where(
            Document.supplier_id == supplier_id
        ).order_by(Document.created_at.desc()).limit(limit).offset(offset)

        count_query = select(func.count()).select_from(Document).where(
            Document.supplier_id == supplier_id
        )

        result = await session.execute(query)
        count_result = await session.execute(count_query)

        return list(result.scalars().all()), count_result.scalar() or 0
