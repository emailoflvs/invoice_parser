"""Пользовательские исключения для системы InvoiceParser"""

class InvoiceParserError(Exception):
    pass

class PreprocessingError(InvoiceParserError):
    pass

class GeminiError(InvoiceParserError):
    pass

class ExportError(InvoiceParserError):
    pass

class TestModeError(InvoiceParserError):
    pass

class ConfigurationError(InvoiceParserError):
    pass

class ValidationError(InvoiceParserError):
    pass

# Алиасы для обратной совместимости
ProcessingError = PreprocessingError
GeminiAPIError = GeminiError
