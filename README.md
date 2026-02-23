# Indian Kanoon Scraper

## Overview

This project contains two scripts:

1. `kanoon.py` - original browse-based scraper
2. `kanoon_search.py` - search-based scraper with date filtering, retries, resume support, and chunked runs

The search scraper targets judgments on [IndianKanoon.org](https://indiankanoon.org).

## Quick Start

Run from this folder:

```bash
cd indian-kanoon
python kanoon_search.py
```

Default behavior:

- Topic: `Food Safety`
- Date range: last `365` days
- Type: `judgments`
- Sort: `mostrecent`
- Output: `Documents/Food_Safety/`

## Common Usage

Download by topic (default 365 days):

```bash
python kanoon_search.py --topic "food safety"
```

Custom date range:

```bash
python kanoon_search.py --topic "environmental law" --from-date 01-01-2026 --to-date 10-02-2026
```

Custom output directory:

```bash
python kanoon_search.py --topic "food safety" --output /path/to/output
```

Auto-chunk a large range (recommended for long ranges):

```bash
python kanoon_search.py --topic "food safety" --days 365 --chunk-days 30
```

## Command-Line Options

| Option | Description | Default |
|---|---|---|
| `--topic` | Search topic/keywords | `Food Safety` |
| `--days` | Days to look back from today | `365` |
| `--from-date` | Start date (`DD-MM-YYYY`) | none |
| `--to-date` | End date (`DD-MM-YYYY`) | none |
| `--output` | Output directory | `Documents` |
| `--chunk-days` | Split selected date range into N-day chunks | disabled |

Notes:

- `--from-date` and `--to-date` must be provided together.
- `--chunk-days` can be combined with either `--days` or explicit dates.

## Resume and Dedup Behavior

Each topic folder keeps an index file:

- `Documents/<Topic_Slug>/.downloaded_ids.txt`

On rerun, the scraper:

1. Skips document IDs already in this index
2. Skips if target PDF file already exists (useful for first run after adding resume logic)
3. Appends newly downloaded IDs to the index

## Retry and Rate-Limit Handling

The scraper includes:

- retry with exponential backoff + jitter for transient network errors
- retry on HTTP `429`, `500`, `502`, `503`, `504`
- `Retry-After` header support when present
- extra retries for empty/transient search pages before deciding to stop

## Important Pagination Limit

Indian Kanoon search results are effectively capped (about 400 results / 40 pages per query in many cases).  
If you need more coverage, use `--chunk-days` (for example `30`, `14`, or `7`) to split the range automatically.

## Output Structure

```text
Documents/
└── Food_Safety/
    ├── Case_Title_1.pdf
    ├── Case_Title_2.pdf
    └── .downloaded_ids.txt
```

## Requirements

- Python 3.x
- Internet connection

Dependencies used:

- `requests`
- `beautifulsoup4`

The script attempts to auto-install missing dependencies.

## PDF to TXT Conversion

Use `pdf_to_txt.py` to convert one PDF or an entire folder of PDFs into UTF-8 `.txt` files.

### Setup

```bash
cd indian-kanoon
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-pdf.txt
```

Optional OCR fallback (for scanned/image-only PDFs):

```bash
brew install tesseract
```

### Convert a Single PDF

```bash
python pdf_to_txt.py \
  --input "/absolute/path/to/file.pdf" \
  --output-dir "/absolute/path/to/output-folder" \
  --ocr --overwrite
```

### Convert a Full Folder

```bash
python pdf_to_txt.py \
  --input "/absolute/path/to/pdf-folder" \
  --output-dir "/absolute/path/to/output-folder" \
  --ocr --overwrite
```

### Useful Notes

- Without `--overwrite`, existing `.txt` files are skipped.
- `--ocr` is fallback-only: embedded PDF text is used first, OCR is used only when needed.
- You can add `--recursive` to scan subfolders.
- Output files keep the same base filename as the source PDF.

## Original Script

To run the original browse-based scraper:

```bash
python kanoon.py
```

## Help

```bash
python kanoon_search.py --help
```
