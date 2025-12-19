# Dynamic Column Width System

## Overview
This system automatically determines optimal column widths based on content analysis, without any hardcoded values.

## How It Works

### 1. Column Order Preservation
- Backend adds `column_order` array to preserve exact order from JSON
- Frontend uses `column_order` first, falls back to `Object.keys(column_mapping)`
- Ensures columns appear in the same order as in the original document

### 2. Content Analysis
Each column is analyzed for:
- `avgLength`: Average character length
- `maxLength`: Maximum character length
- `minLength`: Minimum character length
- `numericRatio`: Ratio of numeric characters (0-1)
- `avgWords`: Average word count
- `repetitionRatio`: How often values repeat
- `uniqueRatio`: Ratio of unique values

### 3. Column Type Detection
Based on content analysis:
- **line-number**: Numeric ratio = 1.0, unique ratio = 1.0, max length ≤ 3
- **numeric**: Numeric ratio ≥ 0.5
- **code**: Min length ≥ 4, unique ratio > 0.3
- **short-repetitive**: Repetition ratio = 1.0, avg length < threshold
- **text**: Everything else (descriptions, names, etc.)

### 4. Weight Calculation
Each column gets a weight based on its type and content:

```javascript
line-number:       weight = 1
short-repetitive:  weight = 2
numeric:           weight = 2-5 (based on maxLength / 3)
code:              weight = 3-6 (based on maxLength / 2.5)
text:              weight = 10-30 (based on avgLength / 10)
```

### 5. Width Distribution Strategy

**Narrow columns** (line-number, quantity, numeric, code, short-repetitive):
- CSS: `width: 1%` - hints browser to compress
- Dynamic `min-width` in `ch` units ensures content fits
- Formula: `min-width = max(minBase, maxLength * multiplier)ch`

**Wide columns** (text):
- CSS: NO width property - browser gives remaining space
- Dynamic `min-width` based on average content length
- Formula: `min-width = max(15, min(50, avgLength * 0.8))ch`

### 6. Min-Width Calculation

```javascript
if (type === 'line-number') {
    minWidthCh = max(2, maxLength + 1);
} else if (type === 'short-repetitive') {
    minWidthCh = max(4, maxLength + 2);
} else if (type === 'numeric') {
    minWidthCh = max(6, maxLength + 2);
} else if (type === 'code') {
    minWidthCh = max(8, maxLength * 1.1);
} else if (type === 'text') {
    minWidthCh = max(15, min(50, avgLength * 0.8));
}
```

## Benefits

### ✅ No Hardcoded Values
- All calculations based on actual content
- Adapts to ANY document structure
- Works with ANY language

### ✅ Multilingual Support
- No language-specific checks
- Pure content-based analysis
- Works for Ukrainian, Russian, English, French, etc.

### ✅ Responsive
- Uses relative units (`ch`, `%`)
- Adapts to screen size
- Works on desktop, tablet, mobile

### ✅ Content-Aware
- Line numbers get minimal space
- Product descriptions get maximum space
- Codes and prices get proportional space

## Examples

### Example 1: Ukrainian Invoice
```
Column Mapping: {
  "no": "№",
  "ukt_zed": "УКТ ЗЕД",
  "product": "Товар",
  "quantity": "Кількість",
  "price_without_vat": "Ціна без ПДВ",
  "amount_without_vat": "Сума без ПДВ"
}

Analysis Results:
- no: type=line-number, weight=1, min-width=3ch
- ukt_zed: type=code, weight=4.4, min-width=11ch
- product: type=text, weight=24, min-width=44ch
- quantity: type=short-repetitive, weight=2, min-width=6ch
- price_without_vat: type=numeric, weight=3.3, min-width=9ch
- amount_without_vat: type=numeric, weight=3.3, min-width=9ch

Total Weight: 38
Width Distribution:
- no: ~3% of table width
- ukt_zed: ~12% of table width
- product: ~63% of table width (WIDEST)
- quantity: ~5% of table width
- price_without_vat: ~9% of table width
- amount_without_vat: ~9% of table width
```

### Example 2: French Invoice
```
Column Mapping: {
  "quantite": "Quantité",
  "produit": "Produit",
  "description": "Description",
  "prix_unitaire": "Prix unitaire",
  "total_ligne": "Total Ligne"
}

Analysis Results:
- quantite: type=numeric, weight=2.5, min-width=7ch
- produit: type=text, weight=15, min-width=25ch
- description: type=text, weight=28, min-width=48ch
- prix_unitaire: type=numeric, weight=3.5, min-width=10ch
- total_ligne: type=numeric, weight=3.5, min-width=10ch

Total Weight: 52.5
Width Distribution:
- quantite: ~5%
- produit: ~29%
- description: ~53% (WIDEST)
- prix_unitaire: ~7%
- total_ligne: ~7%
```

## Configuration

All thresholds are configurable via `.env`:

```bash
# Column analysis thresholds
COLUMN_ANALYSIS_NUMERIC_RATIO_THRESHOLD=0.5
COLUMN_ANALYSIS_CODE_UNIQUE_MIN=0.3
COLUMN_ANALYSIS_CODE_MIN_LENGTH_MULTIPLIER=2.0
COLUMN_ANALYSIS_LONG_TEXT_AVG_THRESHOLD=0.5
COLUMN_ANALYSIS_SHORT_REPETITIVE_RATIO=1.0
# ... and more
```

## Technical Details

### CSS Strategy
- `table-layout: auto` - browser calculates optimal widths
- Narrow columns: `width: 1%` - browser compresses them
- Wide columns: no `width` - browser gives remaining space
- All columns: `min-width: Nch` - content always visible

### Why `ch` Units?
- `1ch` = width of '0' character in current font
- Proportional to font size
- More accurate than `px` for text
- Responsive and dynamic

### Why `width: 1%`?
- Hint to browser: "compress this column"
- Browser still respects `min-width`
- Better than `max-content` for distribution
- Allows text columns to take more space

## Future Improvements

1. Consider font metrics for more accurate sizing
2. Add user preference for column width adjustment
3. Implement column resizing (drag to resize)
4. Cache analysis results for performance
5. Add visual feedback for column weights in debug mode

