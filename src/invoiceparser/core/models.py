"""Основные модели данных для системы InvoiceParser"""
from __future__ import annotations
from datetime import datetime
from datetime import date as DateType
from decimal import Decimal
from typing import Any, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator

class DocumentType(str, Enum):
    IMAGE = "IMAGE"
    PDF = "PDF"

class Mode(str, Enum):
    NORMAL = "NORMAL"
    TEST = "TEST"

class DocumentSource(str, Enum):
    CLI = "CLI"
    TELEGRAM = "TELEGRAM"
    WEB = "WEB"
    EMAIL = "EMAIL"

class PdfProcessingStrategy(str, Enum):
    DIRECT = "DIRECT"
    IMAGE_BASED = "IMAGE_BASED"
    HYBRID = "HYBRID"

class DocumentHeader(BaseModel):
    supplier_name: str | None = None
    supplier_inn: str | None = None
    buyer_name: str | None = None
    buyer_inn: str | None = None
    document_number: str | None = None
    document_date: DateType | None = None
    total_amount: Decimal | None = None
    total_vat: Decimal | None = None
    currency: str | None = None
    class Config:
        extra = "allow"

class DocumentItem(BaseModel):
    line_number: int | None = None
    name: str
    sku: str | None = None
    unit: str | None = None
    quantity: Decimal | None = None
    price: Decimal | None = None
    amount: Decimal | None = None
    vat_rate: str | None = None
    vat_amount: Decimal | None = None
    class Config:
        extra = "allow"

class ParseMetadata(BaseModel):
    source: DocumentSource
    mode: Mode
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    gemini_header_request_id: str | None = None
    gemini_items_request_id: str | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

class ParseResult(BaseModel):
    header: DocumentHeader
    items: list[DocumentItem]
    metadata: ParseMetadata
    class Config:
        extra = "allow"

class TestErrorType(str, Enum):
    MISSING = "MISSING"
    EXTRA = "EXTRA"
    MISMATCH = "MISMATCH"

class TestErrorEntry(BaseModel):
    field_path: str
    expected: Any
    actual: Any
    error_type: TestErrorType
    char_error_count: int | None = None

class TestReport(BaseModel):
    document_name: str
    total_errors: int
    errors_by_field: dict[str, int]
    errors: list[TestErrorEntry]
    passed: bool = Field(default=False)

class PdfAnalysisResult(BaseModel):
    has_text: bool
    text_char_count: int
    page_count: int
    recommended_strategy: PdfProcessingStrategy

# Алиасы для обратной совместимости
class InvoiceHeader(BaseModel):
    """Заголовок счета (алиас для DocumentHeader с другими именами полей)"""
    supplier_name: Optional[str] = None
    supplier_inn: Optional[str] = None
    buyer_name: Optional[str] = None
    buyer_inn: Optional[str] = None
    invoice_number: Optional[str] = None
    document_number: Optional[str] = None  # Альтернативное имя
    date: Optional[DateType] = None
    total_amount: Optional[Decimal] = None
    total_vat: Optional[Decimal] = None
    currency: Optional[str] = None

    class Config:
        populate_by_name = True
        extra = "allow"

class InvoiceData(BaseModel):
    """Данные счета (упрощенная версия ParseResult)"""
    header: InvoiceHeader
    items: list[DocumentItem]

    class Config:
        extra = "allow"
