from flask import Flask, request, redirect, url_for, session
import sqlite3
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import threading
import os

app = Flask(__name__)
app.secret_key = 'bharat_search_secure_multi_role_key_2026'
DB_PATH = 'search_engine.db'

# Database Setup (Pages + Users)
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Search Pages Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            title TEXT,
            content TEXT
        )
    ''')
    
    # 2. Users Table (For Public Login/Signup)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# Background Crawler for Admin
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
    <title>Bharat AI Search Engine</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css">
    <style>
        body { background: #ffffff; font-family: 'Segoe UI', Roboto, Arial, sans-serif; }
        .bharat-logo { font-size: 65px; font-weight: 700; letter-spacing: -2px; }
        .search-box-container { max-width: 584px; margin: 0 auto; position: relative; }
        .search-input { height: 48px; border-radius: 24px; padding-left: 45px; padding-right: 45px; border: 1px solid #dfe1e5; box-shadow: none; }
        .search-input:focus { border-color: transparent; box-shadow: 0 1px 6px rgba(32,33,36,0.28); }
        .search-icon { position: absolute; left: 16px; top: 14px; color: #9aa0a6; font-size: 16px; }
        .mic-icon { position: absolute; right: 16px; top: 13px; color: #FF9933; font-size: 20px; cursor: pointer; }
        .ai-card { max-width: 650px; background: #f8f9fa; border-left: 4px solid #000080; border-radius: 8px; padding: 18px; margin-bottom: 25px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
        .result-card { max-width: 650px; margin-bottom: 24px; }
        .result-title { color: #1a0dab; text-decoration: none; font-size: 20px; font-weight: 400; }
        .result-title:hover { text-decoration: underline; }
        .result-url { color: #202124; font-size: 14px; margin-bottom: 2px; }
        .result-snippet { color: #4d5156; font-size: 14px; line-height: 1.58; }
        .top-nav { position: absolute; right: 20px; top: 20px; }
    </style>
</head>
<body>
"""

HTML_FOOTER = """
<script>
function startVoiceSearch() {
    if ('webkitSpeechRecognition' in window) {
        var recognition = new webkitSpeechRecognition();
        recognition.lang = 'en-IN';
        recognition.start();
        recognition.onresult = function(event) {
            document.getElementById('searchInput').value = event.results[0][0].transcript;
            document.getElementById('searchForm').submit();
        };
    } else {
        alert("Voice search aapke browser me supported nahi hai.");
    }
}
</script>
</body>
</html>
"""

# ----------------- HOME PAGE (SEARCH ENGINE) -----------------
@app.route("/")
def home():
    user_logged = session.get('user_logged')
    username = session.get('username', '')

    nav_links = ""
    if user_logged:
        nav_links = f'<span class="me-3 text-secondary">👤 Hello, <b>{username}</b></span> <a href="/user_logout" class="btn btn-outline-danger btn-sm">Logout</a>'
    else:
        nav_links = '<a href="/user_login" class="btn btn-outline-primary btn-sm me-2">User Login</a> <a href="/user_signup" class="btn btn-primary btn-sm">Sign Up</a>'

    return HTML_HEADER + f"""
    <div class="top-nav">{nav_links}</div>
    <div class="container text-center mt-5 pt-4">
        <div class="bharat-logo mb-2">
            <span style="color:#FF9933">B</span><span style="color:#FF9933">h</span><span style="color:#000080">a</span><span style="color:#138808">r</span><span style="color:#138808">a</span><span style="color:#138808">t</span>
        </div>
        <p class="text-muted mb-4">India's Next-Gen AI Powered Search Engine 🇮🇳</p>

        <form action="/search" method="GET" id="searchForm" class="search-box-container mb-4">
            <i class="bi bi-search search-icon"></i>
            <input type="text" name="q" id="searchInput" class="form-control search-input" placeholder="Search the web or ask AI..." required autocomplete="off">
            <i class="bi bi-mic-fill mic-icon" onclick="startVoiceSearch()" title="Search by voice"></i>
            
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

    ai_summary = ""
    try:
        wiki_api = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={query}&format=json"
        res = requests.get(wiki_api).json()
        if res['query']['search']:
            snippet_raw = res['query']['search'][0]['snippet']
            clean_snippet = BeautifulSoup(snippet_raw, "html.parser").get_text()
            ai_summary = f"✨ <b>Bharat AI Overview:</b> {clean_snippet} Based on verified database records, {query} is a prominent topic searched on Bharat Engine."
    except:
        ai_summary = f"✨ <b>Bharat AI Overview:</b> Results for {query} are listed below."

    header_nav = f"""
    <div class="border-bottom pt-3 px-4">
        <div class="d-flex align-items-center mb-3">
            <a href="/" class="bharat-logo text-decoration-none me-4" style="font-size: 30px;">
                <span style="color:#FF9933">B</span><span style="color:#FF9933">h</span><span style="color:#000080">a</span><span style="color:#138808">r</span><span style="color:#138808">a</span><span style="color:#138808">t</span>
            </a>
            <form action="/search" method="GET" id="searchForm" class="search-box-container ms-0 flex-grow-1" style="max-width: 600px;">
                <i class="bi bi-search search-icon"></i>
                <input type="text" name="q" id="searchInput" value="{query}" class="form-control search-input" required>
                <i class="bi bi-mic-fill mic-icon" onclick="startVoiceSearch()"></i>
            </form>
        </div>
    </div>
    
    <div class="container-fluid px-5 pt-3" style="margin-left: 110px;">
        <div class="ai-card">
            <div class="text-dark" style="font-size: 15px; line-height: 1.6;">{ai_summary}</div>
        </div>
        <p class="text-muted small">Database search results for: <b>{query}</b></p>
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
        body_results += f"""
        <div class="alert alert-light border" style="max-width: 650px;">
            Aapke search query se milte-julte results database mein nahi mile, lekin upar diye gaye <b>Bharat AI Overview</b> ka use kar sakte hain.
        </div>
        """

    body_results += "</div>"
    return HTML_HEADER + header_nav + body_results + HTML_FOOTER

# ----------------- USER SIGNUP / LOGIN / LOGOUT -----------------
@app.route("/user_signup", methods=['GET', 'POST'])
def user_signup():
    msg = ""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            conn.close()
            return redirect("/user_login")
        except:
            msg = "Yeh username pehle se registered hai!"

    return HTML_HEADER + f"""
    <div class="container mt-5" style="max-width: 400px;">
        <h3 class="mb-3 text-center">📝 User Sign Up</h3>
        {f'<div class="alert alert-danger">{msg}</div>' if msg else ''}
        <form method="POST">
            <div class="mb-3"><label>Username</label><input type="text" name="username" class="form-control" required></div>
            <div class="mb-3"><label>Password</label><input type="password" name="password" class="form-control" required></div>
            <button type="submit" class="btn btn-primary w-100">Register</button>
        </form>
        <div class="text-center mt-3"><a href="/user_login" class="text-decoration-none">Already have account? Login</a> | <a href="/" class="text-decoration-none">Home</a></div>
    </div>
    """ + HTML_FOOTER

@app.route("/user_login", methods=['GET', 'POST'])
def user_login():
    error = ""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['user_logged'] = True
            session['username'] = username
            return redirect("/")
        else:
            error = "Galat username ya password!"

    return HTML_HEADER + f"""
    <div class="container mt-5" style="max-width: 400px;">
        <h3 class="mb-3 text-center">👤 User Login</h3>
        {f'<div class="alert alert-danger">{error}</div>' if error else ''}
        <form method="POST">
            <div class="mb-3"><label>Username</label><input type="text" name="username" class="form-control" required></div>
            <div class="mb-3"><label>Password</label><input type="password" name="password" class="form-control" required></div>
            <button type="submit" class="btn btn-success w-100">Login</button>
        </form>
        <div class="text-center mt-3"><a href="/user_signup" class="text-decoration-none">Create Account</a> | <a href="/" class="text-decoration-none">Home</a></div>
    </div>
    """ + HTML_FOOTER

@app.route("/user_logout")
def user_logout():
    session.pop('user_logged', None)
    session.pop('username', None)
    return redirect("/")

# ----------------- ADMIN PANEL (ONLY FOR YOU) -----------------
@app.route("/admin_login", methods=['GET', 'POST'])
def admin_login():
    error = ""
    if request.method == 'POST':
        if request.form.get('username') == "admin" and request.form.get('password') == "Bharat123@#$":
            session['admin_logged'] = True
            return redirect("/admin_dashboard")
        else:
            error = "Galat Admin Credentials!"

    return HTML_HEADER + f"""
    <div class="container mt-5" style="max-width: 400px;">
        <h3 class="mb-3 text-center">🔒 Admin Portal</h3>
        {f'<div class="alert alert-danger">{error}</div>' if error else ''}
        <form method="POST">
            <div class="mb-3"><label>Admin Username</label><input type="text" name="username" class="form-control" required></div>
            <div class="mb-3"><label>Admin Password</label><input type="password" name="password" class="form-control" required></div>
            <button type="submit" class="btn btn-dark w-100">Admin Login</button>
        </form>
        <div class="text-center mt-3"><a href="/" class="text-decoration-none">← Back to Search</a></div>
    </div>
    """ + HTML_FOOTER

@app.route("/admin_dashboard")
def admin_dashboard():
    if not session.get('admin_logged'):
        return redirect("/admin_login")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM pages")
    count = cursor.fetchone()[0]
    conn.close()

    return HTML_HEADER + f"""
    <div class="container mt-5" style="max-width: 600px;">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h3>⚙️ Admin Control Center</h3>
            <a href="/admin_logout" class="btn btn-outline-danger btn-sm">Logout</a>
        </div>
        <div class="alert alert-success">Total Permanent Indexed Links in Engine: <b>{count}</b></div>
        <div class="card p-4">
            <h5 class="mb-3">🤖 Add Website to Permanent DB</h5>
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
    if not session.get('admin_logged'):
        return redirect("/admin_login")
    
    seed_url = request.form.get('seed_url')
    thread = threading.Thread(target=auto_crawl_worker, args=(seed_url, 15))
    thread.start()

    return HTML_HEADER + f"""
    <div class="container mt-5 text-center" style="max-width: 500px;">
        <div class="alert alert-info">
            🚀 Bot background mein active ho gaya hai aur naye links permanent DB mein save kar raha hai!<br><br>
            <a href="/admin_dashboard" class="btn btn-primary">Back to Dashboard</a>
        </div>
    </div>
    """ + HTML_FOOTER

@app.route("/admin_logout")
def admin_logout():
    session.pop('admin_logged', None)
    return redirect("/")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
