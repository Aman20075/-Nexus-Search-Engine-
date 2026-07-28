# ⚡ Nexus Search Engine Pro

A lightweight, custom-built Search Engine built with Python, SQLite, Beautiful Soup, and Tkinter GUI.

## 🚀 Features
- **Web Crawler:** Automatically crawls Wikipedia pages and extracts structured content.
- **SQLite Database:** Stores crawled URLs, Titles, and Snippets efficiently.
- **Relevance Scoring:** Ranks search results dynamically based on keyword frequency in titles and content.
- **Dark Mode GUI:** Clean, modern desktop UI designed with Tkinter.
- **Clickable Hyperlinks:** Directly opens search result links in your default browser.

## 🛠️ Tech Stack
- **Language:** Python
- **Scraping:** BeautifulSoup, Requests
- **Database:** SQLite3
- **GUI Framework:** Tkinter
- **Browser Control:** Webbrowser

## 🏃 How to Run
1. Run `crawler.py` to crawl pages and generate the database:
   ```bash
   python crawler.py