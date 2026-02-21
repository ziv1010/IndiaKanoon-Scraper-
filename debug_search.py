#!/usr/bin/env python3
"""Quick test to understand the result structure"""

import requests
from bs4 import BeautifulSoup as bs

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
})

url = "https://indiankanoon.org/search/?formInput=food+safety+doctypes%3A+judgments+sortby%3A+mostrecent+fromdate%3A+01-01-2026+todate%3A+10-02-2026"

response = session.get(url)
soup = bs(response.content, features="html.parser")

# Get the results container
results_div = soup.find('div', class_='results_middle')
if results_div:
    print("Found results_middle div\n")
    
    # Look for search results (they might be in different structure)
    result_items = results_div.find_all('div', class_='result')
    print(f"Found {len(result_items)} div.result items\n")
    
    for i, item in enumerate(result_items[:3], 1):
        print(f"Result {i}:")
        # Look for title
        title_elem = item.find(['h3', 'a'])
        if title_elem:
            print(f"  Title: {title_elem.get_text(strip=True)[:80]}")
        
        # Look for doc link
        doc_link = item.find('a', href=lambda x: x and '/doc/' in x)
        if doc_link:
            print(f"  Href: {doc_link.get('href')}")
        print()
