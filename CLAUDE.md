# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an AI-powered invoice parser that extracts supplier information and product line items from Ukrainian PDF invoices (накладні/акти/інвойси) and exports them to Excel format. The system uses Claude Sonnet 4 with PDF vision capabilities to parse complex, multi-page invoices with varying formats.

Если не знаешь, как правильно выполнить задачу, скажи об этои и я помогу.

## Key Commands

### Running the Parser

```bash
# Parse a single invoice
python3 invoice_parser.py invoices/invoice.pdf

# Parse multiple invoices
python3 invoice_parser.py invoices/*.pdf

# Specify custom output file
python3 invoice_parser.py invoices/*.pdf "output.xls"
```

### Utility Scripts

```bash
# Debug PDF structure and cell line breaks
python3 debug_pdf_structure.py

# Fix split article codes (post-processing)
python3 fix_articles.py "таблиця накладних.xls"

# Manually fix specific article issues
python3 manual_fix_first_article.py
```

### Dependencies

```bash
pip install anthropic>=0.18.0
# Note: xlwt, xlrd, xlutils also required but not in requirements.txt
```

## Architecture

### Core Components

1. **invoice_parser.py** - Main parser orchestrator
   - Uses Claude Sonnet 4 (`claude-sonnet-4-20250514`) via Anthropic API
   - Streaming responses for large documents (up to 186+ items tested)
   - Processes PDF files using base64 encoding with `document` message type
   - Batch processing support with cumulative Excel output
   - Max tokens: 32,000 (can increase to 64,000 for very large invoices)
   - Timeout: 10 minutes per document

2. **task-items-advanced.txt** - Critical system prompt
   - Defines JSON schema for parsed data (header + items structure)
   - Contains crucial rules for handling multi-line table cells in PDFs
   - Addresses common PDF parsing issue: cell values split across lines within same cell
   - Example: Article code "521.318.01.04.06.00\n1" should become "521.318.01.04.06.001"
   - All modifications to parsing behavior should be made here

3. **Utility scripts** - Debugging and post-processing
   - `debug_pdf_structure.py`: Analyzes how Claude sees PDF table structure
   - `fix_articles.py`: Post-processes Excel to merge split article codes
   - Uses xlrd/xlutils for reading and modifying existing Excel files

### Data Flow

```
PDF Invoice → Claude API (with system prompt) → JSON Response → Excel Export
                ↓                                    ↓
        task-items-advanced.txt              14-column format
```

### Excel Output Format (14 columns)

Each row contains supplier details + product info:

1. постачальник (Supplier name)
2. код ЄДРПОУ (EDRPOU code)
3. телефон (Phone)
4. адреса (Address)
5. дата накладної (Invoice date)
6. номер накладної (Invoice number)
7. УКТ ЗЕД (Product code/article)
8. наименование товара (Product name)
9. обозначение товара (Product designation/nomenclature)
10. ціна за шт без пдв (Unit price without VAT)
11. кіл-сть штук (Quantity)
12. сума без пдв (Total without VAT)
13. ціна за одиницю з ПДВ (Unit price with VAT)
14. сума з ПДВ (Total with VAT)

**Important**: Supplier info (columns 1-6) is repeated for every product row, enabling independent row analysis.

## Critical Technical Details

### PDF Cell Line Break Issue

The most common parsing issue: PDF table cells often contain multi-line values that appear as separate lines but are actually **one cell**. The system prompt explicitly handles this:

- **Article codes**: Concatenate lines without spaces
  - `"521.318.01.04.06.00\n1"` → `"521.318.01.04.06.001"`

- **Product names**: Join lines with spaces
  - `"Распределитель\nпневматический"` → `"Распределитель пневматический"`

- **Designations**: If 1-3 digits, merge into article code (ukt_zed), not separate field

### API Configuration

- Model: `claude-sonnet-4-20250514`
- Requires `ANTHROPIC_API_KEY` environment variable
- Uses streaming for real-time progress feedback
- Document is sent as base64-encoded PDF with media type `application/pdf`

### Excel File Handling

- Uses `xlwt` for writing, `xlrd` + `xlutils.copy` for appending
- First run creates file with headers
- Subsequent runs append rows to existing file
- Output file default: `таблиця накладних.xls`

## Known Patterns

### Tested Invoice Types

Successfully processes:
- Camozzi invoices (66 items)
- DneprSpecMash invoices (186 items - stress test)
- AV Metal acts (simple 1-item documents)
- Karnika invoices (21 items)
- Lakover invoices
- Techno-Privid invoices

All Ukrainian language, various formats, mix of detailed/sparse supplier info.

### Error Handling

The parser handles:
- Missing files (skips with warning)
- Corrupted PDFs (reports error, continues batch)
- Missing API key (stops with clear error)
- Malformed JSON (attempts recovery, fallback to error object)
- Timeouts (streaming mitigates this)

### Typical Issues

1. **Split article codes**: Sometimes Claude splits codes between UKT and Oboznachennya columns
   - Solution: Run `fix_articles.py` post-processor

2. **Missing supplier details**: Some invoices lack phone/address
   - System gracefully uses empty strings

3. **Number formatting**: All numbers stored as strings with Ukrainian formatting ("1 234,56")

## Development Notes

- Project language: Mixed (code in English, docs/data in Ukrainian)
- No git repository initialized
- API keys present in task-items-advanced.txt (testing keys for Google Vision/OpenAI)
- No test suite (validation via manual batch processing)
- No linting/formatting configuration

## Modification Guidelines

1. **To change parsing behavior**: Edit `task-items-advanced.txt` system prompt
2. **To change output format**: Modify `export_to_excel_advanced()` in invoice_parser.py
3. **To handle new invoice types**: Add examples to prompt or create specific handlers
4. **To increase capacity**: Adjust `max_tokens` parameter (currently 32k, can go to 64k)

## Important Context from README

- Production ready: Successfully processed 277 products across 6 diverse invoices
- Average speed: ~55 products/minute
- Scalability: Designed for batch processing of hundreds of invoices
- The format with supplier details in each row was an explicit requirement for independent row analysis
