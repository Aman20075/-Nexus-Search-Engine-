from flask import Flask, request, redirect, url_for, session, render_template_string
import sqlite3
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import threading

app = Flask(__name__)
app.secret_key = 'yahan_apna_koi_bhi_secret_password_rakh_sakte_ho'  # Session secure rakhne ke liye
DB_PATH = 'search_engine.db'

# Database Setup (Permanent & Secure)
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            title TEXT,
            content TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# 🕷️ Background Crawler (Permanent Saving)
def auto_crawl_worker(start_url, max_pages=15):
    urls_to_visit = [start_url]
    visited_urls = set()
    pages_crawled = 0

    while urls_to_visit and pages_crawled < max_pages:
        current_url = urls_to_visit.pop(0)
        if current_url in visited_urls:
            continue

        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            response = requests.get(current_url, headers=headers, timeout=5)
            visited_urls.add(current_url)

            if "text/html" not in response.headers.get('Content-Type', ''):
                continue

            soup = BeautifulSoup(response.text, 'html.parser')
            title = soup.title.string.strip() if soup.title and soup.title.string else current_url
            paragraphs = [p.get_text().strip() for p in soup.find_all('p')]
            text_content = ' '.join(paragraphs)

            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO pages (url, title, content)
                VALUES (?, ?, ?)
            ''', (current_url, title, text_content))
            conn.commit()
            conn.close()

            pages_crawled += 1

            for link in soup.find_all('a', href=True):
                full_url = urljoin(current_url, link['href'])
                parsed = urlparse(full_url)
                if parsed.scheme in ['http', 'https']:
                    if full_url not in visited_urls and full_url not in urls_to_visit:
                        urls_to_visit.append(full_url)
        except Exception as e:
            continue

HTML_HEADER = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bharat Search Engine</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css">
    <style>
        body { background: #ffffff; font-family: 'Segoe UI', Roboto, Arial, sans-serif; }
        .bharat-logo { font-size: 65px; font-weight: 700; letter-spacing: -2px; }
        .search-box-container { max-width: 584px; margin: 0 auto; position: relative; }
        .search-input { height: 46px; border-radius: 24px; padding-left: 45px; padding-right: 20px; border: 1px solid #dfe1e5; box-shadow: none; }
        .search-input:focus { border-color: transparent; box-shadow: 0 1px 6px rgba(32,33,36,0.28); }
        .search-icon { position: absolute; left: 16px; top: 13px; color: #9aa0a6; font-size: 16px; }
        .result-card { max-width: 650px; margin-bottom: 24px; }
        .result-title { color: #1a0dab; text-decoration: none; font-size: 20px; font-weight: 400; }
        .result-title:hover { text-decoration: underline; }
        .result-url { color: #202124; font-size: 14px; margin-bottom: 2px; }
        .result-snippet { color: #4d5156; font-size: 14px; line-height: 1.58; }
    </style>
</head>
<body>
"""

HTML_FOOTER = "</body></html>"

# ----------------- HOME PAGE (SEARCH ENGINE) -----------------
@app.route("/")
def home():
    return HTML_HEADER + """
    <div class="container text-center mt-5 pt-4">
        <div class="bharat-logo mb-2">
            <span style="color:#FF9933">B</span><span style="color:#FF9933">h</span><span style="color:#000080">a</span><span style="color:#138808">r</span><span style="color:#138808">a</span><span style="color:#138808">t</span>
        </div>
        <p class="text-muted mb-4">India's Own Secure Web Search Engine 🇮🇳</p>

        <form action="/search" method="GET" class="search-box-container mb-4">
            <i class="bi bi-search search-icon"></i>
            <input type="text" name="q" class="form-control search-input" placeholder="Search the web database..." required autocomplete="off">
            
            <div class="mt-4">
                <button type="submit" class="btn btn-light border px-4 py-2 me-2 text-secondary">Bharat Search</button>
            </div>
        </form>

        <div class="mt-5">
            <a href="/admin_login" class="text-muted small text-decoration-none">🔒 Admin Portal Login</a>
        </div>
    </div>
    """ + HTML_FOOTER

# ----------------- SEARCH RESULTS PAGE -----------------
@app.route("/search")
def search():
    query = request.args.get('q', '')
    if not query:
        return redirect("/")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT url, title, content FROM pages 
        WHERE title LIKE ? OR content LIKE ?
    ''', (f'%{query}%', f'%{query}%'))
    
    rows = cursor.fetchall()
    conn.close()

    header_nav = f"""
    <div class="border-bottom pt-3 px-4">
        <div class="d-flex align-items-center mb-3">
            <a href="/" class="bharat-logo text-decoration-none me-4" style="font-size: 30px;">
                <span style="color:#FF9933">B</span><span style="color:#FF9933">h</span><span style="color:#000080">a</span><span style="color:#138808">r</span><span style="color:#138808">a</span><span style="color:#138808">t</span>
            </a>
            <form action="/search" method="GET" class="search-box-container ms-0 flex-grow-1" style="max-width: 600px;">
                <i class="bi bi-search search-icon"></i>
                <input type="text" name="q" value="{query}" class="form-control search-input" required>
            </form>
        </div>
    </div>
    
    <div class="container-fluid px-5 pt-3" style="margin-left: 110px;">
        <p class="text-muted small">Found {len(rows)} results for <b>{query}</b></p>
    """

    body_results = ""
    if rows:
        for row in rows:
            url, title, content = row[0], row[1], row[2]
            snippet = content[:180] + "..." if len(content) > 180 else content
            body_results += f"""
            <div class="result-card">
                <div class="result-url">{url}</div>
                <a href="{url}" target="_blank" class="result-title">{title}</a>
                <div class="result-snippet mt-1">{snippet}</div>
            </div>
            """
    else:
        body_results = f"""
        <div class="alert alert-warning" style="max-width: 600px;">
            Aapke database me <b>"{query}"</b> se related koi link nahi mila. Sirf Admin hi naye links add kar sakta hai.
        </div>
        """

    body_results += "</div>"
    return HTML_HEADER + header_nav + body_results + HTML_FOOTER

# ----------------- ADMIN LOGIN & PANEL -----------------
@app.route("/admin_login", methods=['GET', 'POST'])
def admin_login():
    error = ""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # 🔑 Yahan aap apna username aur password set kar sakte hain!
        if username == "admin" and password == "Bharat123@#$":
            session['logged_in'] = True
            return redirect("/admin_dashboard")
        else:
            error = "Galat Username ya Password!"

    return HTML_HEADER + f"""
    <div class="container mt-5" style="max-width: 400px;">
        <h3 class="mb-3 text-center">🔒 Admin Login</h3>
        {f'<div class="alert alert-danger">{error}</div>' if error else ''}
        <form method="POST">
            <div class="mb-3">
                <label>Admin Username</label>
                <input type="text" name="username" class="form-control" required>
            </div>
            <div class="mb-3">
                <label>Admin Password</label>
                <input type="password" name="password" class="form-control" required>
            </div>
            <button type="submit" class="btn btn-primary w-100">Login</button>
        </form>
        <div class="text-center mt-3"><a href="/" class="text-decoration-none">← Back to Search</a></div>
    </div>
    """ + HTML_FOOTER

@app.route("/admin_dashboard")
def admin_dashboard():
    if not session.get('logged_in'):
        return redirect("/admin_login")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM pages")
    count = cursor.fetchone()[0]
    conn.close()

    return HTML_HEADER + f"""
    <div class="container mt-5" style="max-width: 600px;">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h3>⚙️ Admin Control Panel</h3>
            <a href="/admin_logout" class="btn btn-outline-danger btn-sm">Logout</a>
        </div>
        <div class="alert alert-success">
            Total Indexed Links in Permanent DB: <b>{count}</b>
        </div>
        <div class="card p-4">
            <h5 class="mb-3">🤖 Add New Website Link (Crawler Bot)</h5>
            <form action="/admin_add" method="POST">
                <input type="url" name="seed_url" class="form-control mb-3" placeholder="https://example.com" required>
                <button type="submit" class="btn btn-success w-100">Crawl & Save Permanently</button>
            </form>
        </div>
        <div class="mt-4 text-center"><a href="/" class="btn btn-light border">Go to Search Engine</a></div>
    </div>
    """ + HTML_FOOTER

@app.route("/admin_add", methods=['POST'])
def admin_add():
    if not session.get('logged_in'):
        return redirect("/admin_login")
    
    seed_url = request.form.get('seed_url')
    # Background thread se crawl karega taaki page freeze na ho
    thread = threading.Thread(target=auto_crawl_worker, args=(seed_url, 15))
    thread.start()

    return HTML_HEADER + f"""
    <div class="container mt-5 text-center" style="max-width: 500px;">
        <div class="alert alert-info">
            🚀 Link successfully queue me daal diya gaya hai!<br>
            Bot background me website crawl karke database me save kar raha hai. Yeh data permanent rahega aur delete nahi hoga.<br><br>
            <a href="/admin_dashboard" class="btn btn-primary">Back to Dashboard</a>
        </div>
    </div>
    """ + HTML_FOOTER

@app.route("/admin_logout")
def admin_logout():
    session.pop('logged_in', None)
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)
