# Column Analysis Configuration

All column analysis parameters are configurable via `.env` file.

## New Configuration Parameters

Add these to your `.env` file:

```env
# Column Analysis Thresholds (all configurable)
# These parameters control how columns are analyzed and classified

# Very short numeric multiplier: maxLength <= minLength * this → very short numeric (line numbers)
COLUMN_ANALYSIS_VERY_SHORT_MULTIPLIER=1.5

# Numeric ratio threshold: numericRatio threshold for numeric detection
COLUMN_ANALYSIS_NUMERIC_RATIO_THRESHOLD=0.5

# Long text average threshold: avgLength > (minLength + maxLength) * this → long text
COLUMN_ANALYSIS_LONG_TEXT_AVG_THRESHOLD=0.5

# Long text words threshold: avgWords > totalValues / uniqueCount * this → long text
COLUMN_ANALYSIS_LONG_TEXT_WORDS_THRESHOLD=1.0

# Short repetitive ratio: repetitionRatio > uniqueRatio * this → short repetitive
COLUMN_ANALYSIS_SHORT_REPETITIVE_RATIO=1.0

# Short repetitive average threshold: avgLength < (minLength + maxLength) * this → short repetitive
COLUMN_ANALYSIS_SHORT_REPETITIVE_AVG_THRESHOLD=0.5

# Code detection - minimum numeric ratio: Minimum numericRatio for code detection
COLUMN_ANALYSIS_CODE_NUMERIC_MIN=0.2

# Code detection - maximum numeric ratio: Maximum numericRatio for code detection (mixed alphanumeric)
COLUMN_ANALYSIS_CODE_NUMERIC_MAX=0.8

# Code detection - minimum unique ratio: Minimum uniqueRatio for code detection
COLUMN_ANALYSIS_CODE_UNIQUE_MIN=0.3

# Code wrap multiplier: maxLength > avgLength * this → needs wrapping
COLUMN_ANALYSIS_CODE_WRAP_MULTIPLIER=1.5

# Universal short threshold: relativeLength < this → center align
COLUMN_ANALYSIS_UNIVERSAL_SHORT_THRESHOLD=0.3

# Universal variation threshold: lengthVariation < this → uniform length
COLUMN_ANALYSIS_UNIVERSAL_VARIATION_THRESHOLD=0.5

# Textarea word multiplier: fieldValue.length > avgWordLength * this → needs textarea
COLUMN_ANALYSIS_TEXTAREA_WORD_MULTIPLIER=15.0

# Code min length multiplier: avgLength >= minLength * this → code detection minimum length
COLUMN_ANALYSIS_CODE_MIN_LENGTH_MULTIPLIER=2.0

# Words divisor: totalValues / (uniqueCount * this) → words threshold for wrapping
COLUMN_ANALYSIS_WORDS_DIVISOR=2.0
```

## Description

All these parameters control the dynamic column analysis system that determines:
- Column width (max-content vs auto)
- Text alignment (left, center, right)
- Whether to use textarea or input
- Whether to allow text wrapping

The system is **fully universal** and works with any data structure - no hardcoded column names or assumptions.

