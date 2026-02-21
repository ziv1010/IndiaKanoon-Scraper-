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
from datetime import datetime, timedelta
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
    
    from_date_str = from_dt.strftime("%d-%m-%Y")
    to_date_str = today.strftime("%d-%m-%Y")
    
    return from_date_str, to_date_str


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
    """Scrape content from web pages"""
    try:
        content = session.get(url).content
        return bs(content, features="html.parser")
    except Exception as e:
        print(f"Error while fetching {url}: {e}")
        return None


def download_pdf(doc_id, save_path, title):
    """
    Download PDF from Indian Kanoon using document ID.
    
    Args:
        doc_id: Document ID from the URL
        save_path: Directory to save the PDF
        title: Title for the PDF filename
    """
    try:
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
        
        # Make GET request for PDF
        r = session.get(pdf_url, headers=headers)
        
        # Check if we got a PDF (not an error page)
        content_type = r.headers.get('Content-Type', '')
        if r.status_code != 200:
            print(f"✗ Failed: HTTP {r.status_code}")
            return
        
        if 'pdf' not in content_type.lower() and not r.content.startswith(b'%PDF'):
            print(f"✗ Failed: Got {content_type} instead of PDF")
            return
        
        # Sanitize filename
        title = title.replace('/', '-').replace('\\', '-')
        filename = Path(save_path) / f"{title}.pdf"
        
        filename.write_bytes(r.content)
        print(f"✓ Saved: {filename}")
        
        time.sleep(0.5)  # Rate limiting
        
    except Exception as e:
        print(f"✗ Error downloading {doc_id}: {e}")


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
    
    total_downloaded = 0
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
            print("No more results found")
            break
        
        print(f"Found {len(documents)} results on this page")
        
        # Download each document
        for doc_id, title in documents:
            download_pdf(doc_id, save_path, title)
            total_downloaded += 1
        
        # Check for next page
        if not has_next_page(soup):
            print("\n✓ Reached last page")
            break
        
        page_num += 1
        time.sleep(1)  # Rate limiting between pages
    
    print(f"\n{'='*70}")
    print(f"✓ Download complete!")
    print(f"Total documents downloaded: {total_downloaded}")
    print(f"Saved to: {save_path}")
    print(f"{'='*70}\n")


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
    
    args = parser.parse_args()
    
    # Validate custom dates if provided
    if (args.from_date and not args.to_date) or (args.to_date and not args.from_date):
        parser.error("Both --from-date and --to-date must be provided together")
    
    # Calculate date range
    from_date, to_date = calculate_date_range(
        days=args.days,
        from_date=args.from_date,
        to_date=args.to_date
    )
    
    # Run the search and download
    search_and_download(args.topic, from_date, to_date, args.output)


if __name__ == '__main__':
    main()
