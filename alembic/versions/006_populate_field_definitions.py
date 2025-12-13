"""
Populate field_definitions and field_labels with initial data.

Revision ID: 006_populate_field_definitions
Revises: 005_allow_duplicate_file_hashes
Create Date: 2025-12-13
"""
from alembic import op
import sqlalchemy as sa

revision = '006_populate_field_definitions'
down_revision = '005_allow_duplicate_file_hashes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Populate field_definitions and field_labels with standard invoice fields.
    """
    conn = op.get_bind()

    # Check if data already exists
    result = conn.execute(sa.text("SELECT COUNT(*) FROM field_definitions;"))
    count = result.scalar()

    if count > 0:
        # Data already exists, skip
        return

    # Insert field definitions
    field_definitions = [
        # Document Info
        ('document_type', 'header', 'text', 'Document type (Invoice, Waybill, etc.)'),
        ('document_number', 'header', 'text', 'Document number'),
        ('document_date', 'header', 'date', 'Document date'),
        ('location', 'header', 'text', 'Location/place of issue'),
        ('currency', 'header', 'text', 'Currency code'),

        # Supplier
        ('supplier_name', 'supplier', 'text', 'Supplier company name'),
        ('supplier_tax_id', 'supplier', 'text', 'Supplier tax ID/INN/EDRPOU'),
        ('supplier_vat_id', 'supplier', 'text', 'Supplier VAT ID'),
        ('supplier_address', 'supplier', 'text', 'Supplier address'),
        ('supplier_phone', 'supplier', 'text', 'Supplier phone'),
        ('supplier_email', 'supplier', 'text', 'Supplier email'),
        ('supplier_iban', 'supplier', 'text', 'Supplier bank account IBAN'),
        ('supplier_bank', 'supplier', 'text', 'Supplier bank name'),

        # Buyer
        ('buyer_name', 'buyer', 'text', 'Buyer company name'),
        ('buyer_tax_id', 'buyer', 'text', 'Buyer tax ID/INN/EDRPOU'),
        ('buyer_vat_id', 'buyer', 'text', 'Buyer VAT ID'),
        ('buyer_address', 'buyer', 'text', 'Buyer address'),
        ('buyer_phone', 'buyer', 'text', 'Buyer phone'),
        ('buyer_email', 'buyer', 'text', 'Buyer email'),

        # Totals
        ('subtotal', 'totals', 'number', 'Subtotal amount (without VAT)'),
        ('total_vat', 'totals', 'number', 'Total VAT amount'),
        ('total_amount', 'totals', 'number', 'Total amount (with VAT)'),
        ('vat_rate', 'totals', 'number', 'VAT rate percentage'),
        ('amount_in_words', 'totals', 'text', 'Total amount in words'),

        # References
        ('contract', 'references', 'text', 'Contract number'),
        ('order', 'references', 'text', 'Order number'),
        ('po_number', 'references', 'text', 'Purchase order number'),
    ]

    # Insert field definitions (check for existing first)
    for code, section, data_type, description in field_definitions:
        # Check if field definition already exists
        check_result = conn.execute(sa.text("""
            SELECT COUNT(*) FROM field_definitions WHERE code = :code;
        """), {'code': code})
        exists = check_result.scalar() > 0

        if not exists:
            conn.execute(sa.text("""
                INSERT INTO field_definitions (code, section, data_type, description)
                VALUES (:code, :section, :data_type, :description);
            """), {
                'code': code,
                'section': section,
                'data_type': data_type,
                'description': description
            })

    # Insert field labels (multilingual)
    # Get field IDs
    field_ids = {}
    for code, _, _, _ in field_definitions:
        result = conn.execute(
            sa.text("SELECT id FROM field_definitions WHERE code = :code"),
            {'code': code}
        )
        row = result.fetchone()
        if row:
            field_ids[code] = row[0]

    # Field labels in multiple languages
    field_labels = [
        # Document Info
        ('document_type', 'ru', 'Тип документа'),
        ('document_type', 'uk', 'Тип документа'),
        ('document_type', 'en', 'Document Type'),
        ('document_number', 'ru', 'Номер документа'),
        ('document_number', 'uk', 'Номер документа'),
        ('document_number', 'en', 'Document Number'),
        ('document_date', 'ru', 'Дата документа'),
        ('document_date', 'uk', 'Дата документа'),
        ('document_date', 'en', 'Document Date'),
        ('currency', 'ru', 'Валюта'),
        ('currency', 'uk', 'Валюта'),
        ('currency', 'en', 'Currency'),

        # Supplier
        ('supplier_name', 'ru', 'Поставщик'),
        ('supplier_name', 'uk', 'Постачальник'),
        ('supplier_name', 'en', 'Supplier'),
        ('supplier_tax_id', 'ru', 'ИНН поставщика'),
        ('supplier_tax_id', 'uk', 'ЄДРПОУ постачальника'),
        ('supplier_tax_id', 'en', 'Supplier Tax ID'),
        ('supplier_address', 'ru', 'Адрес поставщика'),
        ('supplier_address', 'uk', 'Адреса постачальника'),
        ('supplier_address', 'en', 'Supplier Address'),

        # Buyer
        ('buyer_name', 'ru', 'Покупатель'),
        ('buyer_name', 'uk', 'Покупець'),
        ('buyer_name', 'en', 'Buyer'),
        ('buyer_tax_id', 'ru', 'ИНН покупателя'),
        ('buyer_tax_id', 'uk', 'ЄДРПОУ покупця'),
        ('buyer_tax_id', 'en', 'Buyer Tax ID'),
        ('buyer_address', 'ru', 'Адрес покупателя'),
        ('buyer_address', 'uk', 'Адреса покупця'),
        ('buyer_address', 'en', 'Buyer Address'),

        # Totals
        ('total_amount', 'ru', 'Итого'),
        ('total_amount', 'uk', 'Разом'),
        ('total_amount', 'en', 'Total Amount'),
        ('total_vat', 'ru', 'НДС'),
        ('total_vat', 'uk', 'ПДВ'),
        ('total_vat', 'en', 'Total VAT'),
        ('subtotal', 'ru', 'Сумма без НДС'),
        ('subtotal', 'uk', 'Сума без ПДВ'),
        ('subtotal', 'en', 'Subtotal'),
    ]

    # Insert field labels (check for existing first)
    for code, locale, label in field_labels:
        if code in field_ids:
            # Check if label already exists
            check_result = conn.execute(sa.text("""
                SELECT COUNT(*) FROM field_labels
                WHERE field_id = :field_id AND locale = :locale;
            """), {
                'field_id': field_ids[code],
                'locale': locale
            })
            exists = check_result.scalar() > 0

            if not exists:
                conn.execute(sa.text("""
                    INSERT INTO field_labels (field_id, locale, label)
                    VALUES (:field_id, :locale, :label);
                """), {
                    'field_id': field_ids[code],
                    'locale': locale,
                    'label': label
                })


def downgrade() -> None:
    """
    Remove field definitions and labels (optional - usually not needed).
    """
    # Optionally clear the data
    # op.execute("DELETE FROM field_labels;")
    # op.execute("DELETE FROM field_definitions;")
    pass

