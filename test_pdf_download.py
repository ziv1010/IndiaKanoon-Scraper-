#!/usr/bin/env python3
"""Test PDF download mechanism"""

import requests

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
})

# Test different download methods
doc_id = "46168352"
url_base = f"https://indiankanoon.org/doc/{doc_id}/"

print("Testing different PDF download methods...\n")

# Method 1: POST with type=pdf
print("Method 1: POST with type=pdf payload")
response1 = session.post(url_base, data="type=pdf", headers={"Content-Type": "application/x-www-form-urlencoded"})
print(f"Status: {response1.status_code}")
print(f"Content-Type: {response1.headers.get('Content-Type')}")
print(f"Content length: {len(response1.content)} bytes")
print(f"First 100 chars: {response1.text[:100]}")
print()

# Method 2: GET with ?type=print
print("Method 2: GET with ?type=print")
response2 = session.get(f"{url_base}?type=print")
print(f"Status: {response2.status_code}")
print(f"Content-Type: {response2.headers.get('Content-Type')}")
print(f"Content length: {len(response2.content)} bytes")
print(f"First 100 chars: {response2.text[:100]}")
print()

# Method 3: Direct PDF URL
print("Method 3: Direct /pdf/ URL")
response3 = session.get(f"https://indiankanoon.org/doc/{doc_id}/pdf/")
print(f"Status: {response3.status_code}")
print(f"Content-Type: {response3.headers.get('Content-Type')}")
print(f"Content length: {len(response3.content)} bytes")
if response3.status_code == 200:
    print(f"First 10 bytes: {response3.content[:10]}")
print()
