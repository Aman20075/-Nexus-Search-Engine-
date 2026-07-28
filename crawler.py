import requests
from bs4 import BeautifulSoup
import sqlite3
import time
import re

# Database Setup
conn = sqlite3.connect("search_engine.db")
cursor = conn.cursor()

# Table create karna
cursor.execute('''
    CREATE TABLE IF NOT EXISTS pages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT UNIQUE,
        title TEXT,
        snippet TEXT
    )
''')
conn.commit()

start_url = "https://en.wikipedia.org/wiki/Python_(programming_language)"
headers = {'User-Agent': 'Mozilla/5.0'}

visited_urls = set()
urls_to_crawl = [start_url]
max_pages = 5

print("🚀 SQLite Multi-Page Crawling Shuru Ho Rahi Hai...\n")

crawled_count = 0

while urls_to_crawl and crawled_count < max_pages:
    url = urls_to_crawl.pop(0)
    
    if url in visited_urls:
        continue

    visited_urls.add(url)

    try:
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')

        title = soup.title.string if soup.title else "No Title"

        snippet = ""
        for p in soup.find_all('p'):
            text = p.text.strip()
            if len(text) > 50:
                snippet = text[:200] + "..."
                break

        # SQLite Database me insert karna
        cursor.execute('''
            INSERT OR IGNORE INTO pages (url, title, snippet)
            VALUES (?, ?, ?)
        ''', (url, title, snippet))
        conn.commit()

        crawled_count += 1
        print(f"[{crawled_count}/{max_pages}] Saved: {title}")

        # Automatic Next Links Find karna
        for link in soup.find_all('a', href=re.compile(r'^/wiki/')):
            new_url = f"https://en.wikipedia.org{link['href']}"
            if ":" not in link['href'] and new_url not in visited_urls:
                urls_to_crawl.append(new_url)

        time.sleep(1)

    except Exception as e:
        print(f"⚠️ Error crawling {url}: {e}")

conn.close()
print("\n-----------------------------------")
print("🎉 Success! SQLite 'search_engine.db' Database tayar ho gaya!")
print("-----------------------------------")