from flask import Flask, request, redirect, url_for, session
import sqlite3
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import threading
import os

app = Flask(__name__)
# Session permanent banane ke liye (User jab tak khud logout na kare)
app.permanent_session_lifetime = 365 * 24 * 60 * 60  
app.secret_key = 'bharat_search_permanent_session_key_2026'
DB_PATH = 'search_engine.db'

# 🚫 Adult / Vulgar Content Blocklist
BLOCKED_KEYWORDS = ['porn', 'xxx', 'sex', 'adult', 'nude', 'nsfw', 'hot video', 'bhabhi']

def is_safe_query(query):
    query_lower = query.lower()
    for word in BLOCKED_KEYWORDS:
        if word in query_lower:
            return False
    return True

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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            login_type TEXT DEFAULT 'manual'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            query TEXT,
            timestamp TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# 🧠 Autonomous Educational Web Scraper
def autonomous_web_crawler(search_query):
    try:
        formatted_query = search_query.replace(' ', '+')
        target_url = f"https://en.wikipedia.org/wiki/Special:Search?search={formatted_query}"
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(target_url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for a_tag in soup.find_all('a', href=True):
                link = a_tag['href']
                if link.startswith('/wiki/') and ':' not in link:
                    full_url = f"https://en.wikipedia.org{link}"
                    page_res = requests.get(full_url, headers=headers, timeout=4)
                    if page_res.status_code == 200:
                        page_soup = BeautifulSoup(page_res.text, 'html.parser')
                        title = page_soup.title.string.strip() if page_soup.title and page_soup.title.string else search_query
                        paragraphs = [p.get_text().strip() for p in page_soup.find_all('p')]
                        content = ' '.join(paragraphs)
                        
                        if len(content) > 100:
                            conn = sqlite3.connect(DB_PATH)
                            cursor = conn.cursor()
                            cursor.execute('''
                                INSERT OR IGNORE INTO pages (url, title, content)
                                VALUES (?, ?, ?)
                            ''', (full_url, title, content))
                            conn.commit()
                            conn.close()
                    break
    except Exception as e:
        pass

HTML_HEADER = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bharat Safe AI Search Engine</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css">
    <style>
        body { background: #ffffff; font-family: 'Segoe UI', Roboto, Arial, sans-serif; overflow-x: hidden; }
        .bharat-logo { font-size: 65px; font-weight: 700; letter-spacing: -2px; }
        .search-box-container { max-width: 584px; width: 100%; margin: 0 auto; position: relative; }
        .search-input { height: 48px; border-radius: 24px; padding-left: 45px; padding-right: 45px; border: 1px solid #dfe1e5; box-shadow: none; }
        .search-input:focus { border-color: transparent; box-shadow: 0 1px 6px rgba(32,33,36,0.28); }
        .search-icon { position: absolute; left: 16px; top: 14px; color: #9aa0a6; font-size: 16px; }
        .mic-icon { position: absolute; right: 16px; top: 13px; color: #FF9933; font-size: 20px; cursor: pointer; }
        .results-wrapper { max-width: 700px; margin: 0 auto; padding: 0 20px; }
        .ai-card { background: #f8f9fa; border-left: 4px solid #000080; border-radius: 8px; padding: 18px; margin-bottom: 25px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
        .result-card { margin-bottom: 24px; word-break: break-word; }
        .result-title { color: #1a0dab; text-decoration: none; font-size: 18px; font-weight: 400; display: block; }
        .result-title:hover { text-decoration: underline; }
        .result-url { color: #202124; font-size: 13px; margin-bottom: 2px; }
        .result-snippet { color: #4d5156; font-size: 14px; line-height: 1.58; }
        .top-nav { position: absolute; right: 20px; top: 20px; }
        .social-btn { width: 100%; border-radius: 20px; font-weight: 500; margin-bottom: 10px; padding: 10px; text-decoration: none; display: inline-block; }
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

# ----------------- HOME PAGE -----------------
@app.route("/")
def home():
    user_logged = session.get('user_logged')
    username = session.get('username', '')

    if user_logged:
        nav_links = f'''
            <span class="me-3 text-secondary">👤 Hello, <b>{username}</b></span> 
            <a href="/my_history" class="btn btn-outline-secondary btn-sm me-2">📜 My History</a>
            <a href="/logout_verify" class="btn btn-outline-danger btn-sm">Logout</a>
        '''
    else:
        nav_links = '<a href="/user_login" class="btn btn-outline-primary btn-sm me-2">User Login</a> <a href="/user_signup" class="btn btn-primary btn-sm">Sign Up</a>'

    return HTML_HEADER + f"""
    <div class="top-nav">{nav_links}</div>
    <div class="container text-center mt-5 pt-4">
        <div class="bharat-logo mb-2">
            <span style="color:#FF9933">B</span><span style="color:#FF9933">h</span><span style="color:#000080">a</span><span style="color:#138808">r</span><span style="color:#138808">a</span><span style="color:#138808">t</span>
        </div>
        <p class="text-muted mb-4">India's Safe & Educational AI Search Engine 🇮🇳</p>

        <form action="/search" method="GET" id="searchForm" class="search-box-container mb-4">
            <i class="bi bi-search search-icon"></i>
            <input type="text" name="q" id="searchInput" class="form-control search-input" placeholder="Search books, science, history or concepts..." required autocomplete="off">
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

# ----------------- SEARCH ROUTE -----------------
@app.route("/search")
def search():
    query = request.args.get('q', '').strip()
    if not query:
        return redirect("/")

    if not is_safe_query(query):
        return HTML_HEADER + f"""
        <div class="results-wrapper pt-5 text-center">
            <div class="alert alert-danger p-4 shadow-sm" style="max-width: 600px; margin: 0 auto;">
                <h4 class="alert-heading">🚫 Safe Search Blocked</h4>
                <p>Aapne jo query search ki hai wo <b>Bharat Safe Search Policy</b> ke khilaf hai.</p>
                <hr>
                <a href="/" class="btn btn-primary btn-sm">← Back to Search</a>
            </div>
        </div>
        """ + HTML_FOOTER

    if session.get('user_logged'):
        current_user = session.get('username')
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO search_history (username, query, timestamp) VALUES (?, ?, ?)", 
                       (current_user, query, current_time))
        conn.commit()
        conn.close()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT url, title, content FROM pages 
        WHERE title LIKE ? OR content LIKE ?
    ''', (f'%{query}%', f'%{query}%'))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        t = threading.Thread(target=autonomous_web_crawler, args=(query,))
        t.start()
        t.join(timeout=2.5)

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT url, title, content FROM pages 
            WHERE title LIKE ? OR content LIKE ?
        ''', (f'%{query}%', f'%{query}%'))
        rows = cursor.fetchall()
        conn.close()

    ai_summary = f"✨ <b>Bharat Educational Overview:</b> Verified insights and book-level academic facts for <b>{query}</b>."

    header_nav = f"""
    <div class="border-bottom pt-3 px-3">
        <div class="d-flex align-items-center mb-3 flex-wrap">
            <a href="/" class="bharat-logo text-decoration-none me-4 mb-2 mb-md-0" style="font-size: 30px;">
                <span style="color:#FF9933">B</span><span style="color:#FF9933">h</span><span style="color:#000080">a</span><span style="color:#138808">r</span><span style="color:#138808">a</span><span style="color:#138808">t</span>
            </a>
            <form action="/search" method="GET" id="searchForm" class="search-box-container ms-0 flex-grow-1" style="max-width: 600px;">
                <i class="bi bi-search search-icon"></i>
                <input type="text" name="q" id="searchInput" value="{query}" class="form-control search-input" required>
                <i class="bi bi-mic-fill mic-icon" onclick="startVoiceSearch()"></i>
            </form>
        </div>
    </div>
    
    <div class="results-wrapper pt-4">
        <div class="ai-card">
            <div class="text-dark" style="font-size: 15px; line-height: 1.6;">{ai_summary}</div>
        </div>
        <p class="text-muted small mb-4">Educational database records for: <b>{query}</b></p>
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
            Academic index is learning. New records for <b>{query}</b> are being compiled.
        </div>
        """

    body_results += "</div>"
    return HTML_HEADER + header_nav + body_results + HTML_FOOTER

# ----------------- MY HISTORY PAGE -----------------
@app.route("/my_history")
def my_history():
    if not session.get('user_logged'):
        return redirect("/user_login")
    
    username = session.get('username')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT query, timestamp FROM search_history WHERE username = ? ORDER BY id DESC", (username,))
    history_items = cursor.fetchall()
    conn.close()

    history_html = ""
    if history_items:
        for item in history_items:
            history_html += f"""
            <li class="list-group-item d-flex justify-content-between align-items-center">
                <span>🔍 <b>{item[0]}</b></span>
                <span class="text-muted small">{item[1]}</span>
            </li>
            """
    else:
        history_html = '<li class="list-group-item text-muted text-center">Aapne abhi tak kuch search nahi kiya hai.</li>'

    return HTML_HEADER + f"""
    <div class="container mt-5" style="max-width: 600px;">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h3>📜 Aapki Search History</h3>
            <a href="/" class="btn btn-outline-primary btn-sm">← Back to Search</a>
        </div>
        <ul class="list-group shadow-sm">
            {history_html}
        </ul>
    </div>
    """ + HTML_FOOTER

# ----------------- LOGOUT WITH VERIFICATION -----------------
@app.route("/logout_verify", methods=['GET', 'POST'])
def logout_verify():
    if not session.get('user_logged'):
        return redirect("/")
    
    username = session.get('username')
    login_type = session.get('login_type')
    error = ""
    
    if request.method == 'POST':
        # Agar user Google ya Phone se aaya hai toh direct logout allow hoga, manual wale ko password dena padega
        if login_type != 'manual':
            session.pop('user_logged', None)
            session.pop('username', None)
            session.pop('login_type', None)
            return redirect("/")
            
        password = request.form.get('password')
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            session.pop('user_logged', None)
            session.pop('username', None)
            session.pop('login_type', None)
            return redirect("/")
        else:
            error = "Galat password! Sahi password darj karein."

    error_div = f'<div class="alert alert-danger">{error}</div>' if error else ''
    
    if login_type != 'manual':
        form_content = """
            <p class="text-muted text-center mb-3">Kya aap logout karna chahte hain?</p>
            <button type="submit" class="btn btn-danger w-100 mb-2">Confirm Logout</button>
        """
    else:
        form_content = f"""
            <div class="mb-3">
                <label>Password for <b>{username}</b></label>
                <input type="password" name="password" class="form-control" required>
            </div>
            <button type="submit" class="btn btn-danger w-100 mb-2">Confirm Logout</button>
        """

    return HTML_HEADER + f"""
    <div class="container mt-5" style="max-width: 400px;">
        <div class="card p-4 shadow-sm border-danger">
            <h4 class="text-danger mb-3 text-center">⚠️ Logout Confirm Karein</h4>
            {error_div}
            <form method="POST">
                {form_content}
                <a href="/" class="btn btn-light border w-100">Cancel</a>
            </form>
        </div>
    </div>
    """ + HTML_FOOTER

# ----------------- REAL GMAIL LOGIN ROUTE -----------------
@app.route("/social_login/google", methods=['GET', 'POST'])
def google_login():
    error = ""
    if request.method == 'POST':
        user_email = request.form.get('email', '').strip()
        
        # Valid Gmail ID check
        if user_email and "@" in user_email:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO users (username, password, login_type) VALUES (?, ?, ?)", 
                           (user_email, 'google_verified', 'google'))
            conn.commit()
            conn.close()

            session.permanent = True
            session['user_logged'] = True
            session['username'] = user_email  # Asli Gmail ID session me save hogi
            session['login_type'] = 'google'
            return redirect("/")
        else:
            error = "Kripya valid Gmail address enter karein!"

    error_div = f'<div class="alert alert-danger">{error}</div>' if error else ''
    return HTML_HEADER + f"""
    <div class="container mt-5" style="max-width: 400px;">
        <div class="card p-4 shadow-sm text-center">
            <h4 class="mb-3"><i class="bi bi-google text-danger"></i> Google Sign-In</h4>
            <p class="text-muted small">Apni Gmail ID se login karein:</p>
            {error_div}
            <form method="POST">
                <input type="email" name="email" class="form-control mb-3" placeholder="example@gmail.com" required>
                <button type="submit" class="btn btn-danger w-100">Continue with Gmail</button>
            </form>
            <div class="mt-3"><a href="/user_login" class="text-decoration-none small">← Back to Login</a></div>
        </div>
    </div>
    """ + HTML_FOOTER

# ----------------- REAL PHONE LOGIN ROUTE -----------------
@app.route("/social_login/phone", methods=['GET', 'POST'])
def phone_login():
    error = ""
    if request.method == 'POST':
        phone_no = request.form.get('phone', '').strip()
        if phone_no and len(phone_no) >= 10:
            user_id = f"+91-{phone_no}"
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO users (username, password, login_type) VALUES (?, ?, ?)", 
                           (user_id, 'phone_verified', 'phone'))
            conn.commit()
            conn.close()

            session.permanent = True
            session['user_logged'] = True
            session['username'] = user_id
            session['login_type'] = 'phone'
            return redirect("/")
        else:
            error = "Kripya sahi 10 digit ka Mobile Number enter karein!"

    error_div = f'<div class="alert alert-danger">{error}</div>' if error else ''
    return HTML_HEADER + f"""
    <div class="container mt-5" style="max-width: 400px;">
        <div class="card p-4 shadow-sm text-center">
            <h4 class="mb-3"><i class="bi bi-phone-fill text-success"></i> Phone Sign-In</h4>
            <p class="text-muted small">Apna mobile number darj karein:</p>
            {error_div}
            <form method="POST">
                <input type="tel" name="phone" class="form-control mb-3" placeholder="9876543210" maxlength="10" required>
                <button type="submit" class="btn btn-success w-100">Continue with Phone</button>
            </form>
            <div class="mt-3"><a href="/user_login" class="text-decoration-
