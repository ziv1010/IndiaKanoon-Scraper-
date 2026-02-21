# Indian Kanoon Scraper - Usage Guide

## Overview

This project contains two scripts for downloading judgments from [IndianKanoon.org](https://indiankanoon.org):

1. **`kanoon.py`** - Original script that browses all courts by year/month
2. **`kanoon_search.py`** - New search-based script with topic filtering ✨

## Quick Start with Search-Based Scraper

### Basic Usage - "This Week" (Last 7 Days)

```bash
python kanoon_search.py --topic "food safety"
```

This will:
- Search for "food safety" judgments
- Download only from the **last 7 days** (Feb 3-10, 2026)
- Filter for **judgments only** (not articles, etc.)
- Sort by **most recent** first
- Save to `Documents/food_safety/`

### Custom Date Range (Last 30 Days)

```bash
python kanoon_search.py --topic "food safety" --days 30
```

### Specific Date Range

```bash
python kanoon_search.py --topic "environmental law" --from-date 01-01-2026 --to-date 10-02-2026
```

### Custom Output Directory

```bash
python kanoon_search.py --topic "food safety" --output /path/to/custom/folder
```

## Command-Line Options

| Option | Description | Default | Required |
|--------|-------------|---------|----------|
| `--topic` | Search topic/keywords | - | ✅ Yes |
| `--days` | Days to look back from today | 7 | No |
| `--from-date` | Custom start date (DD-MM-YYYY) | - | No* |
| `--to-date` | Custom end date (DD-MM-YYYY) | - | No* |
| `--output` | Output directory | `Documents` | No |

*Both `--from-date` and `--to-date` must be provided together

## Examples

### Download recent food safety judgments
```bash
python kanoon_search.py --topic "food safety"
```

### Download environmental law cases from January 2026
```bash
python kanoon_search.py --topic "environmental law" --from-date 01-01-2026 --to-date 31-01-2026
```

### Download consumer protection cases from last 2 weeks
```bash
python kanoon_search.py --topic "consumer protection" --days 14
```

## Output Structure

PDFs are saved in the following structure:
```
Documents/
└── food_safety/          # Topic name (spaces replaced with underscores)
    ├── Case_Title_1.pdf
    ├── Case_Title_2.pdf
    └── ...
```

## Features

✨ **Topic-based search** - Search for specific legal topics  
📅 **Smart date filtering** - Automatic "this week" or custom ranges  
⚖️ **Judgment-only filter** - Downloads only court judgments  
🔄 **Automatic pagination** - Handles all search result pages  
⏱️ **Rate limiting** - Built-in delays to respect server limits  
📦 **Auto-install dependencies** - Automatically installs required packages  

## Requirements

- Python 3.x
- Internet connection

Dependencies are installed automatically:
- `cfscrape` - For bypassing Cloudflare protection
- `beautifulsoup4` - For HTML parsing
- `requests` - For HTTP requests

## Original Browse-Based Scraper

To use the original scraper that downloads all courts/years/months:

```bash
python kanoon.py
```

⚠️ **Warning**: This will download thousands of files and take hours/days!

## Troubleshooting

**Script says "No results found"**  
- Try adjusting your date range (the topic might not have recent cases)
- Try a broader search topic

**PDFs not downloading**  
- Check your internet connection
- The site might have rate-limited you (wait a few minutes)

**ModuleNotFoundError**  
- The script should auto-install dependencies
- If it fails, manually run: `pip install cfscrape beautifulsoup4`

## Need Help?

View all available options:
```bash
python kanoon_search.py --help
```
