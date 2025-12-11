"""
Database service for Invoice Parser - FINAL VERSION.
Handles: unknown fields, signatures, dynamic tables with column_mapping.
"""
import logging
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import selectinload
from sqlalchemy import select, and_

from db_models_v2 import (
    Base, Document, File, DocumentType, DocumentSnapshot,
    DocumentField, DocumentSignature, DocumentTableSection,
    Company, FieldDefinition, DocumentPage
)

logger = logging.getLogger(__name__)


class DatabaseService:
    """Service for database operations with full architecture support"""

    def __init__(self, database_url: str):
        """Initialize database service"""
        self.engine = create_async_engine(
            database_url,
            echo=False,
            pool_size=5,
            max_overflow=10
        )
        self.SessionLocal = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

    async def create_tables(self):
        """Create all database tables"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")

    async def get_session(self) -> AsyncSession:
        """Get new database session"""
        return self.SessionLocal()

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
        """Get existing document type or create new one"""
        result = await session.execute(
            select(DocumentType).where(DocumentType.code == code)
        )
        doc_type = result.scalar_one_or_none()
        
        if not doc_type:
            doc_type = DocumentType(code=code, name=name, description=description)
            session.add(doc_type)
            await session.flush()
            logger.info(f"Created document type: {code}")
        
        return doc_type

    # ========================================================================
    # Company Management
    # ========================================================================

    async def find_company_by_tax_id(
        self,
        session: AsyncSession,
        tax_id: str
    ) -> Optional[Company]:
        """Find company by tax ID"""
        result = await session.execute(
            select(Company).where(Company.tax_id == tax_id)
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
        """Create new company or update existing"""
        company = None
        if tax_id:
            company = await self.find_company_by_tax_id(session, tax_id)
        
        if company:
            company.legal_name = name
            if vat_id:
                company.vat_id = vat_id
            if address:
                company.address_legal = address
            for key, value in kwargs.items():
                if hasattr(company, key):
                    setattr(company, key, value)
            logger.info(f"Updated company: {name}")
        else:
            company = Company(
                legal_name=name,
                tax_id=tax_id,
                vat_id=vat_id,
                address_legal=address,
                **kwargs
            )
            session.add(company)
            await session.flush()
            logger.info(f"Created company: {name}")
        
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
        doc_type_code: str = "UA_INVOICE",
        original_filename: Optional[str] = None
    ) -> Document:
        """
        Save parsed document with RAW data (right after AI parsing).
        
        Handles:
        - Unknown fields (field_id=NULL)
        - Signatures (1-20+)
        - Dynamic tables (column_mapping)
        """
        logger.info(f"Saving parsed document: {file_path.name}")
        
        # 1. Create File record
        file_record = await self._create_file_record(
            session, file_path, original_filename
        )
        
        # 2. Get document type
        doc_type = await self.get_or_create_document_type(
            session, code=doc_type_code, name="Ukrainian Invoice"
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
        
        await session.commit()
        logger.info(f"Document saved (ID: {document.id})")
        
        return document

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
        document.updated_at = datetime.utcnow()
        
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
        import mimetypes
        
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
        """Extract supplier and buyer, create/link companies"""
        supplier_id = None
        buyer_id = None
        
        parties = json_data.get('parties', {})
        
        # Supplier
        if 'supplier' in parties:
            supplier_data = parties['supplier']
            supplier = await self.create_or_update_company(
                session,
                name=supplier_data.get('name', 'Unknown Supplier'),
                tax_id=supplier_data.get('tax_id'),
                vat_id=supplier_data.get('vat_id'),
                address=supplier_data.get('address'),
                iban=supplier_data.get('account_number'),
                bank_name=supplier_data.get('bank'),
                phone=supplier_data.get('phone')
            )
            supplier_id = supplier.id
        
        # Buyer
        if 'customer' in parties:
            buyer_data = parties['customer']
            buyer = await self.create_or_update_company(
                session,
                name=buyer_data.get('name', 'Unknown Buyer'),
                tax_id=buyer_data.get('tax_id'),
                address=buyer_data.get('address')
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
                raw_label=field_data['label'],
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
                field.approved_at = datetime.utcnow()
                
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
        for key, value in doc_info.items():
            if key not in ['_label', 'location_label'] and value:
                fields.append({
                    'section': 'header',
                    'code': key,
                    'label': key,
                    'value': value,
                    'group_key': 'document_info'
                })
        
        # parties
        parties = json_data.get('parties', {})
        for party_type, party_data in parties.items():
            if isinstance(party_data, dict):
                for key, value in party_data.items():
                    if key not in ['_label'] and value:
                        fields.append({
                            'section': party_type,
                            'code': key,
                            'label': key,
                            'value': value,
                            'group_key': party_type
                        })
        
        # totals
        totals = json_data.get('totals', {})
        for key, value in totals.items():
            if value:
                fields.append({
                    'section': 'totals',
                    'code': key,
                    'label': key,
                    'value': value,
                    'group_key': 'totals'
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
        doc_type = doc_info.get('document_type', '')
        
        if 'Видаткова' in doc_type or 'накладна' in doc_type:
            return 'uk'
        elif 'Накладная' in doc_type:
            return 'ru'
        elif 'Invoice' in doc_type:
            return 'en'
        
        return None

    def _detect_country(self, json_data: Dict[str, Any]) -> Optional[str]:
        """Detect document country"""
        currency = json_data.get('document_info', {}).get('currency')
        if currency == 'UAH':
            return 'UA'
        elif currency == 'RUB':
            return 'RU'
        elif currency == 'EUR':
            return 'EU'
        
        return None

    def _to_text(self, value: Any) -> Optional[str]:
        """Convert any value to text"""
        if value is None:
            return None
        return str(value)
