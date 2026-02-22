#!/usr/bin/env python3
"""
Indian Kanoon Search-Based Scraper
Downloads judgments based on topic search with date filtering
"""

import os
import sys
from pathlib import Path
import time
import argparse
import random
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

# Auto-install dependencies
try:
    import requests
except (ModuleNotFoundError, ImportError):
    print("requests module not found, installing...")
    os.system(f"{sys.executable} -m pip install --break-system-packages -U requests")
    import requests

from requests.structures import CaseInsensitiveDict

try:
    from bs4 import BeautifulSoup as bs
except (ModuleNotFoundError, ImportError):
    print("BeautifulSoup module not found, installing...")
    os.system(f"{sys.executable} -m pip install --break-system-packages -U beautifulsoup4")
    from bs4 import BeautifulSoup as bs


# Create a session for HTTP requests
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
})
url_home = "https://indiankanoon.org"

MAX_RETRIES = 5
BASE_RETRY_SECONDS = 2.0
MAX_RETRY_SECONDS = 60.0
REQUEST_TIMEOUT_SECONDS = 45
SUCCESS_DELAY_SECONDS = 1.2
PAGE_DELAY_SECONDS = 2.0
SEARCH_EMPTY_PAGE_RETRIES = 3
DATE_FORMAT = "%d-%m-%Y"


def calculate_date_range(days=7, from_date=None, to_date=None):
    """
    Calculate the date range for searching.
    Returns (from_date_str, to_date_str) in DD-MM-YYYY format
    """
    if from_date and to_date:
        # User provided custom dates
        return from_date, to_date
    
    # Calculate "this week" as last N days
    today = datetime.now()
    from_dt = today - timedelta(days=days-1)
    
    from_date_str = from_dt.strftime(DATE_FORMAT)
    to_date_str = today.strftime(DATE_FORMAT)
    
    return from_date_str, to_date_str


def parse_date(date_str):
    """Parse DD-MM-YYYY date string."""
    return datetime.strptime(date_str, DATE_FORMAT).date()


def format_date(date_value):
    """Format date object to DD-MM-YYYY string."""
    return date_value.strftime(DATE_FORMAT)


def generate_date_chunks(from_date, to_date, chunk_days):
    """Split a date range into contiguous DD-MM-YYYY chunks."""
    if chunk_days < 1:
        raise ValueError("chunk_days must be >= 1")

    start_date = parse_date(from_date)
    end_date = parse_date(to_date)
    if start_date > end_date:
        raise ValueError(f"from-date must be <= to-date (got {from_date} > {to_date})")

    chunks = []
    current = start_date
    while current <= end_date:
        chunk_end = min(end_date, current + timedelta(days=chunk_days - 1))
        chunks.append((format_date(current), format_date(chunk_end)))
        current = chunk_end + timedelta(days=1)

    return chunks


def build_search_url(topic, from_date, to_date, page_num=0):
    """
    Build the search URL with all filters.
    
    Args:
        topic: Search query (e.g., "food safety")
        from_date: Start date in DD-MM-YYYY format
        to_date: End date in DD-MM-YYYY format
        page_num: Page number for pagination (0-indexed)
    
    Returns:
        Complete search URL
    """
    # Build the formInput parameter
    query_parts = [
        topic,
        "doctypes: judgments",
        "sortby: mostrecent",
        f"fromdate: {from_date}",
        f"todate: {to_date}"
    ]
    
    form_input = " ".join(query_parts)
    encoded_input = quote_plus(form_input)
    
    url = f"{url_home}/search/?formInput={encoded_input}"
    
    if page_num > 0:
        url += f"&pagenum={page_num}"
    
    return url


def crawler(url):
    """Fetch and parse a search page with retry/backoff for transient failures."""
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        except requests.RequestException as e:
            if attempt >= MAX_RETRIES:
                print(f"Error while fetching {url}: {e}")
                return None
            wait_seconds = get_backoff_seconds(attempt) + random.uniform(0.2, 1.0)
            print(f"Search page network error. Retrying in {wait_seconds:.1f}s ({attempt + 1}/{MAX_RETRIES})")
            time.sleep(wait_seconds)
            continue

        if response.status_code == 200:
            return bs(response.content, features="html.parser")

        if response.status_code in (429, 500, 502, 503, 504) and attempt < MAX_RETRIES:
            retry_after = parse_retry_after(response.headers.get('Retry-After'))
            wait_base = retry_after if retry_after is not None else get_backoff_seconds(attempt)
            wait_seconds = min(MAX_RETRY_SECONDS, wait_base) + random.uniform(0.2, 1.0)
            print(f"Search page HTTP {response.status_code}. Retrying in {wait_seconds:.1f}s ({attempt + 1}/{MAX_RETRIES})")
            time.sleep(wait_seconds)
            continue

        print(f"Search page failed: HTTP {response.status_code} ({url})")
        return None

    print(f"Search page failed after retries: {url}")
    return None


def parse_retry_after(retry_after_header):
    """
    Parse Retry-After header value into seconds.
    Supports both integer seconds and HTTP date format.
    """
    if not retry_after_header:
        return None

    value = str(retry_after_header).strip()
    if value.isdigit():
        return max(1, int(value))

    try:
        retry_at = parsedate_to_datetime(value)
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)

        wait_seconds = (retry_at.astimezone(timezone.utc) - datetime.now(timezone.utc)).total_seconds()
        if wait_seconds > 0:
            return wait_seconds
    except Exception:
        pass

    return None


def get_backoff_seconds(attempt):
    """Compute exponential backoff with an upper bound."""
    return min(MAX_RETRY_SECONDS, BASE_RETRY_SECONDS * (2 ** attempt))


def sanitize_title(title):
    """Sanitize title to a filesystem-safe PDF name fragment."""
    return title.replace('/', '-').replace('\\', '-')


def build_pdf_path(save_path, title):
    """Build the target PDF path for a document title."""
    safe_title = sanitize_title(title)
    return Path(save_path) / f"{safe_title}.pdf"


def load_downloaded_ids(index_path):
    """Load previously downloaded document IDs from disk."""
    if not index_path.exists():
        return set()

    try:
        with index_path.open("r", encoding="utf-8") as f:
            return {line.strip() for line in f if line.strip()}
    except Exception as e:
        print(f"Warning: could not read {index_path}: {e}")
        return set()


def append_downloaded_id(index_path, doc_id):
    """Append one downloaded document ID so runs can resume safely."""
    try:
        with index_path.open("a", encoding="utf-8") as f:
            f.write(f"{doc_id}\n")
    except Exception as e:
        print(f"Warning: could not update {index_path}: {e}")


def is_no_matching_results_page(soup):
    """Detect the explicit 'No Matching results' page."""
    if soup is None:
        return False

    title_text = soup.title.get_text(" ", strip=True).lower() if soup.title else ""
    body_text = soup.get_text(" ", strip=True).lower()
    return "no matching results" in title_text or "no matching results" in body_text


def download_pdf(doc_id, save_path, title):
    """
    Download PDF from Indian Kanoon using document ID.
    
    Args:
        doc_id: Document ID from the URL
        save_path: Directory to save the PDF
        title: Title for the PDF filename
    """
    # Use GET request with ?type=pdf parameter
    doc_url = f"{url_home}/doc/{doc_id}/"
    pdf_url = f"{doc_url}?type=pdf"

    print(f"Downloading: {title} (ID: {doc_id})")
    Path(save_path).mkdir(parents=True, exist_ok=True)

    # Include Referer header to avoid 403 errors
    headers = {
        'Referer': doc_url,
        'Accept': 'application/pdf,application/x-pdf,*/*'
    }

    filename = build_pdf_path(save_path, title)

    for attempt in range(MAX_RETRIES + 1):
        try:
            r = session.get(pdf_url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
        except requests.RequestException as e:
            if attempt >= MAX_RETRIES:
                print(f"✗ Error downloading {doc_id}: {e}")
                return False

            wait_seconds = get_backoff_seconds(attempt) + random.uniform(0.2, 1.0)
            print(f"Temporary network error. Retrying in {wait_seconds:.1f}s ({attempt + 1}/{MAX_RETRIES})")
            time.sleep(wait_seconds)
            continue

        status_code = r.status_code
        content_type = r.headers.get('Content-Type', '')

        if status_code == 200 and ('pdf' in content_type.lower() or r.content.startswith(b'%PDF')):
            filename.write_bytes(r.content)
            print(f"✓ Saved: {filename}")
            time.sleep(SUCCESS_DELAY_SECONDS + random.uniform(0.1, 0.5))
            return True

        # Handle rate-limits and transient server failures with retries
        if status_code in (429, 500, 502, 503, 504) and attempt < MAX_RETRIES:
            retry_after = parse_retry_after(r.headers.get('Retry-After'))
            wait_base = retry_after if retry_after is not None else get_backoff_seconds(attempt)
            wait_seconds = min(MAX_RETRY_SECONDS, wait_base) + random.uniform(0.2, 1.0)
            print(f"HTTP {status_code}. Retrying in {wait_seconds:.1f}s ({attempt + 1}/{MAX_RETRIES})")
            time.sleep(wait_seconds)
            continue

        if status_code != 200:
            print(f"✗ Failed: HTTP {status_code}")
            return False

        # Non-PDF 200 responses are often anti-bot/rate-limit pages
        if attempt < MAX_RETRIES:
            wait_seconds = get_backoff_seconds(attempt) + random.uniform(0.2, 1.0)
            print(f"Unexpected response ({content_type}). Retrying in {wait_seconds:.1f}s ({attempt + 1}/{MAX_RETRIES})")
            time.sleep(wait_seconds)
            continue

        print(f"✗ Failed: Got {content_type} instead of PDF")
        return False

    print(f"✗ Failed: Retries exhausted for {doc_id}")
    return False


def extract_document_ids(soup):
    """
    Extract document IDs from search results page.
    
    Returns:
        List of tuples: [(doc_id, title), ...]
    """
    documents = []
    seen_ids = set()  # Avoid duplicates
    
    try:
        # Find all links with "Full Document" text that point to /doc/
        for link in soup.find_all('a', href=lambda x: x and '/doc/' in x):
            link_text = link.get_text(strip=True)
            
            # We only want "Full Document" links, not citation links
            if link_text == "Full Document":
                href = link.get('href', '')
                
                # Extract doc ID from href like /doc/123456/
                parts = href.split('/')
                if len(parts) >= 3 and parts[2]:
                    doc_id = parts[2]
                    
                    # Avoid duplicates
                    if doc_id in seen_ids:
                        continue
                    seen_ids.add(doc_id)
                    
                    # Get the case title from the heading above this link
                    # The title is usually in an h4 or parent structure
                    parent = link.find_parent()
                    if parent:
                        # Look for h4 heading in the same parent
                        heading = parent.find_previous_sibling(['h4', 'h3', 'h2'])
                        if not heading:
                            heading = parent.find_previous(['h4', 'h3', 'h2'])
                        
                        if heading and heading.a:
                            title = heading.a.get_text(strip=True)
                        elif heading:
                            title = heading.get_text(strip=True)
                        else:
                            title = f"Document_{doc_id}"
                    else:
                        title = f"Document_{doc_id}"
                    
                    documents.append((doc_id, title))
    
    except Exception as e:
        print(f"Error extracting document IDs: {e}")
    
    return documents


def has_next_page(soup):
    """Check if there are more pages in the search results"""
    try:
        # Look for pagination links
        pagination = soup.find_all('span', attrs={'class': 'pagenum'})
        return len(pagination) > 0
    except:
        return False


def search_and_download(topic, from_date, to_date, output_dir="Documents"):
    """
    Main search and download function.
    
    Args:
        topic: Search topic
        from_date: Start date (DD-MM-YYYY)
        to_date: End date (DD-MM-YYYY)
        output_dir: Base directory for downloads
    """
    print(f"\n{'='*70}")
    print(f"Indian Kanoon Search Scraper")
    print(f"{'='*70}")
    print(f"Topic: {topic}")
    print(f"Date Range: {from_date} to {to_date}")
    print(f"Document Type: Judgments")
    print(f"Sort By: Most Recent")
    print(f"{'='*70}\n")
    
    # Create output directory structure
    topic_slug = topic.replace(' ', '_').replace('/', '-')
    save_path = f"{output_dir}/{topic_slug}"
    Path(save_path).mkdir(parents=True, exist_ok=True)
    index_path = Path(save_path) / ".downloaded_ids.txt"
    downloaded_ids = load_downloaded_ids(index_path)
    print(f"Resume index: {index_path} ({len(downloaded_ids)} IDs)")
    
    total_downloaded = 0
    total_skipped = 0
    total_failed = 0
    page_num = 0
    
    while True:
        # Build search URL
        search_url = build_search_url(topic, from_date, to_date, page_num)
        print(f"\n📄 Fetching page {page_num + 1}: {search_url}")
        
        # Fetch search results
        soup = crawler(search_url)
        if not soup:
            print("Failed to fetch search results")
            break
        
        # Extract document IDs
        documents = extract_document_ids(soup)
        
        if not documents:
            if is_no_matching_results_page(soup):
                print("No more results found")
                break

            recovered = False
            for retry in range(1, SEARCH_EMPTY_PAGE_RETRIES + 1):
                wait_seconds = get_backoff_seconds(retry - 1) + random.uniform(0.2, 0.8)
                print(
                    f"No documents parsed on page {page_num + 1}. "
                    f"Retrying page in {wait_seconds:.1f}s ({retry}/{SEARCH_EMPTY_PAGE_RETRIES})"
                )
                time.sleep(wait_seconds)

                soup = crawler(search_url)
                if not soup:
                    continue

                if is_no_matching_results_page(soup):
                    print("No more results found")
                    documents = []
                    recovered = False
                    break

                documents = extract_document_ids(soup)
                if documents:
                    recovered = True
                    print(f"Recovered page {page_num + 1} with {len(documents)} results")
                    break

            if not documents and is_no_matching_results_page(soup):
                break

            if not recovered and not documents:
                print(
                    "Stopped early: this page returned no documents after retries. "
                    "Re-run later to continue from where you left off."
                )
                break
        
        print(f"Found {len(documents)} results on this page")
        
        # Download each document
        for doc_id, title in documents:
            if doc_id in downloaded_ids:
                print(f"↷ Skipping already downloaded ID: {doc_id}")
                total_skipped += 1
                continue

            # Also skip if matching file already exists from earlier runs
            # where no ID index was present yet.
            existing_file = build_pdf_path(save_path, title)
            if existing_file.exists():
                print(f"↷ Skipping existing file: {existing_file.name} (ID: {doc_id})")
                downloaded_ids.add(doc_id)
                append_downloaded_id(index_path, doc_id)
                total_skipped += 1
                continue

            if download_pdf(doc_id, save_path, title):
                total_downloaded += 1
                downloaded_ids.add(doc_id)
                append_downloaded_id(index_path, doc_id)
            else:
                total_failed += 1
        
        # Check for next page
        if not has_next_page(soup):
            print("\n✓ Reached last page")
            break
        
        page_num += 1
        time.sleep(PAGE_DELAY_SECONDS)  # Rate limiting between pages
    
    print(f"\n{'='*70}")
    print(f"✓ Download complete!")
    print(f"Successfully downloaded: {total_downloaded}")
    print(f"Skipped (already present): {total_skipped}")
    print(f"Failed downloads: {total_failed}")
    print(f"Saved to: {save_path}")
    print(f"{'='*70}\n")
    return {
        "downloaded": total_downloaded,
        "skipped": total_skipped,
        "failed": total_failed,
    }


def main():
    parser = argparse.ArgumentParser(
        description='Search and download judgments from Indian Kanoon',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download judgments about "food safety" from the last 7 days
  python kanoon_search.py --topic "food safety"
  
  # Download from the last 30 days
  python kanoon_search.py --topic "food safety" --days 30
  
  # Download with custom date range
  python kanoon_search.py --topic "environmental law" --from-date 01-01-2026 --to-date 10-02-2026

  # Auto-split one year into 30-day chunks
  python kanoon_search.py --topic "food safety" --days 365 --chunk-days 30
        """
    )
    
    parser.add_argument(
        '--topic',
        type=str,
        default="Food Safety",
        help='Search topic (e.g., "Food Safety", "environmental law")'
    )
    
    parser.add_argument(
        '--days',
        type=int,
        default=365,
        help='Number of days to look back (default: 365 for "past year")'
    )
    
    parser.add_argument(
        '--from-date',
        type=str,
        help='Custom start date in DD-MM-YYYY format'
    )
    
    parser.add_argument(
        '--to-date',
        type=str,
        help='Custom end date in DD-MM-YYYY format'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default='Documents',
        help='Output directory for downloaded PDFs (default: Documents)'
    )

    parser.add_argument(
        '--chunk-days',
        type=int,
        help='Automatically split date range into chunk-sized windows (e.g., 30)'
    )
    
    args = parser.parse_args()
    
    # Validate custom dates if provided
    if (args.from_date and not args.to_date) or (args.to_date and not args.from_date):
        parser.error("Both --from-date and --to-date must be provided together")
    if args.chunk_days is not None and args.chunk_days < 1:
        parser.error("--chunk-days must be >= 1")
    
    # Calculate date range
    from_date, to_date = calculate_date_range(
        days=args.days,
        from_date=args.from_date,
        to_date=args.to_date
    )

    # Validate final resolved date range
    try:
        parse_date(from_date)
        parse_date(to_date)
    except ValueError:
        parser.error("Dates must be in DD-MM-YYYY format")

    # Run in auto-chunk mode or single-range mode
    if args.chunk_days:
        try:
            chunks = generate_date_chunks(from_date, to_date, args.chunk_days)
        except ValueError as e:
            parser.error(str(e))

        print(f"\nAuto chunk mode enabled: {len(chunks)} chunks of {args.chunk_days} day(s)")
        total_downloaded = 0
        total_skipped = 0
        total_failed = 0

        for i, (chunk_from, chunk_to) in enumerate(chunks, start=1):
            print(f"\n{'#' * 70}")
            print(f"Chunk {i}/{len(chunks)}: {chunk_from} to {chunk_to}")
            print(f"{'#' * 70}")
            stats = search_and_download(args.topic, chunk_from, chunk_to, args.output)
            total_downloaded += stats["downloaded"]
            total_skipped += stats["skipped"]
            total_failed += stats["failed"]

        print(f"\n{'='*70}")
        print("✓ All chunks complete!")
        print(f"Chunked total downloaded: {total_downloaded}")
        print(f"Chunked total skipped: {total_skipped}")
        print(f"Chunked total failed: {total_failed}")
        print(f"{'='*70}\n")
    else:
        search_and_download(args.topic, from_date, to_date, args.output)


if __name__ == '__main__':
    main()
