from flask import Flask, request, redirect, url_for, session
import sqlite3
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import threading
import os

app = Flask(__name__)
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
    <title>Bharat AI Search Engine</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css">
    <style>
        body { background: #ffffff; font-family: arial, sans-serif; overflow-x: hidden; margin: 0; }
        
        /* Top Navigation Header (Google Style) */
        .google-header { display: flex; justify-content: space-between; align-items: center; padding: 12px 20px; font-size: 14px; }
        .creator-info { font-weight: 600; color: #5f6368; }
        .top-right-nav { display: flex; align-items: center; gap: 12px; }
        .user-email-badge { background: #f1f3f4; padding: 6px 12px; border-radius: 16px; font-size: 13px; color: #3c4043; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

        /* Google Main Logo & Search Box */
        .main-container { margin-top: 80px; text-align: center; }
        .bharat-logo { font-size: 80px; font-weight: 600; letter-spacing: -2px; user-select: none; }
        
        .search-wrapper { max-width: 584px; margin: 20px auto 0 auto; padding: 0 12px; }
        .search-box { position: relative; display: flex; align-items: center; border: 1px solid #dfe1e5; border-radius: 24px; padding: 0 14px; height: 46px; box-shadow: none; transition: box-shadow 0.2s; }
        .search-box:hover, .search-box:focus-within { box-shadow: 0 1px 6px rgba(32,33,36,0.28); border-color: rgba(223,225,229,0); }
        .search-box input { border: none; outline: none; width: 100%; font-size: 16px; padding: 0 10px; background: transparent; }
        
        .search-icon-left { color: #9aa0a6; font-size: 18px; }
        .mic-icon-right { color: #4285f4; font-size: 20px; cursor: pointer; }

        .btn-group-google { margin-top: 28px; }
        .btn-google { background-color: #f8f9fa; border: 1px solid #f8f9fa; border-radius: 4px; color: #3c4043; font-size: 14px; padding: 10px 16px; margin: 4px 6px; cursor: pointer; text-decoration: none; display: inline-block; }
        .btn-google:hover { border: 1px solid #dadce0; color: #202124; }

        /* Search Results Page Layout */
        .results-wrapper { max-width: 650px; margin-left: 160px; padding: 20px 0; }
        @media (max-width: 768px) { .results-wrapper { margin-left: 0; padding: 15px; } }
        .ai-card { background: #f8f9fa; border-left: 4px solid #1a73e8; border-radius: 8px; padding: 16px; margin-bottom: 20px; }
        .result-card { margin-bottom: 28px; word-break: break-word; }
        .result-url { color: #202124; font-size: 12px; margin-bottom: 4px; line-height: 1.3; }
        .result-title { color: #1a0dab; text-decoration: none; font-size: 20px; font-weight: 400; line-height: 1.3; display: block; }
        .result-title:hover { text-decoration: underline; }
        .result-snippet { color: #4d5156; font-size: 14px; line-height: 1.58; margin-top: 4px; }
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

@app.route("/")
def home():
    user_logged = session.get('user_logged')
    username = session.get('username', '')

    if user_logged:
        nav_links = f'''
            <span class="user-email-badge" title="{username}">👤 {username}</span> 
            <a href="/my_history" class="btn btn-outline-secondary btn-sm ms-1">History</a>
            <a href="/logout_verify" class="btn btn-outline-danger btn-sm ms-1">Logout</a>
        '''
    else:
        nav_links = '<a href="/user_login" class="btn btn-primary btn-sm px-3" style="border-radius:4px;">Sign in</a>'

    return HTML_HEADER + f"""
    <div class="google-header">
        <div class="creator-info">🚀 Created by <b>Aman Giri</b></div>
        <div class="top-right-nav">{nav_links}</div>
    </div>

    <div class="main-container">
        <div class="bharat-logo">
            <span style="color:#4285F4">B</span><span style="color:#EA4335">h</span><span style="color:#FBBC05">a</span><span style="color:#4285F4">r</span><span style="color:#34A853">a</span><span style="color:#EA4335">t</span>
        </div>
        <p class="text-muted small mt-1 mb-4">India's Safe & Educational AI Search Engine 🇮🇳</p>

        <div class="search-wrapper">
            <form action="/search" method="GET" id="searchForm">
                <div class="search-box">
                    <i class="bi bi-search search-icon-left"></i>
                    <input type="text" name="q" id="searchInput" placeholder="" required autocomplete="off">
                    <i class="bi bi-mic-fill mic-icon-right" onclick="startVoiceSearch()" title="Search by voice"></i>
                </div>
                
                <div class="btn-group-google">
                    <button type="submit" class="btn-google">Bharat Search</button>
                    <a href="/admin_login" class="btn-google text-decoration-none">Admin Portal</a>
                </div>
            </form>
        </div>
    </div>
    """ + HTML_FOOTER

@app.route("/search")
def search():
    query = request.args.get('q', '').strip()
    if not query:
        return redirect("/")

    if not is_safe_query(query):
        return HTML_HEADER + f"""
        <div class="container pt-5 text-center">
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

    ai_summary = f"✨ <b>Bharat Educational Overview:</b> Verified insights for <b>{query}</b>."

    header_nav = f"""
    <div class="border-bottom py-2 px-3">
        <div class="d-flex align-items-center flex-wrap gap-3">
            <a href="/" class="bharat-logo text-decoration-none me-3" style="font-size: 28px;">
                <span style="color:#4285F4">B</span><span style="color:#EA4335">h</span><span style="color:#FBBC05">a</span><span style="color:#4285F4">r</span><span style="color:#34A853">a</span><span style="color:#EA4335">t</span>
            </a>
            <form action="/search" method="GET" id="searchForm" class="flex-grow-1" style="max-width: 600px;">
                <div class="search-box" style="height: 40px;">
                    <input type="text" name="q" id="searchInput" value="{query}" required>
                    <i class="bi bi-mic-fill mic-icon-right" onclick="startVoiceSearch()"></i>
                </div>
            </form>
        </div>
    </div>
    
    <div class="results-wrapper">
        <div class="ai-card">
            <div class="text-dark" style="font-size: 14px; line-height: 1.6;">{ai_summary}</div>
        </div>
        <p class="text-muted small mb-4">About {len(rows)} educational results for: <b>{query}</b></p>
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
                <div class="result-snippet">{snippet}</div>
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

@app.route("/logout_verify", methods=['GET', 'POST'])
def logout_verify():
    if not session.get('user_logged'):
        return redirect("/")
    
    username = session.get('username')
    login_type = session.get('login_type')
    error = ""
    
    if request.method == 'POST':
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

@app.route("/social_login/google", methods=['GET', 'POST'])
def google_login():
    error = ""
    if request.method == 'POST':
        user_email = request.form.get('email', '').strip()
        if user_email and "@" in user_email:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO users (username, password, login_type) VALUES (?, ?, ?)", 
                           (user_email, 'google_verified', 'google'))
            conn.commit()
            conn.close()

            session.permanent = True
            session['user_logged'] = True
            session['username'] = user_email
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
            <div class="mt-3"><a href="/user_login" class="text-decoration-none small">← Back to Login</a></div>
        </div>
    </div>
    """ + HTML_FOOTER

@app.route("/user_signup", methods=['GET', 'POST'])
def user_signup():
    msg = ""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, password, login_type) VALUES (?, ?, ?)", (username, password, 'manual'))
            conn.commit()
            conn.close()
            return redirect("/user_login")
        except:
            msg = "Yeh username pehle se registered hai!"

    error_div = f'<div class="alert alert-danger">{msg}</div>' if msg else ''
    return HTML_HEADER + f"""
    <div class="container mt-5" style="max-width: 400px;">
        <h3 class="mb-3 text-center">📝 User Sign Up</h3>
        {error_div}
        <form method="POST">
            <div class="mb-3"><label>Username / Email</label><input type="text" name="username" class="form-control" required></div>
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
            session.permanent = True
            session['user_logged'] = True
            session['username'] = username
            session['login_type'] = 'manual'
            return redirect("/")
        else:
            error = "Galat username ya password!"

    error_div = f'<div class="alert alert-danger">{error}</div>' if error else ''
    return HTML_HEADER + f"""
    <div class="container mt-5" style="max-width: 400px;">
        <h3 class="mb-3 text-center">👤 User Login</h3>
        {error_div}
        
        <div class="mb-3">
            <a href="/social_login/google" class="btn btn-outline-danger social-btn">
                <i class="bi bi-google me-2"></i> Continue with Gmail
            </a>
            <a href="/social_login/phone" class="btn btn-outline-success social-btn">
                <i class="bi bi-phone-fill me-2"></i> Continue with Phone Number
            </a>
        </div>
        
        <div class="text-center mb-3 text-muted">— OR Manual Login —</div>

        <form method="POST">
            <div class="mb-3"><label>Username</label><input type="text" name="username" class="form-control" required></div>
            <div class="mb-3"><label>Password</label><input type="password" name="password" class="form-control" required></div>
            <button type="submit" class="btn btn-success w-100">Login</button>
        </form>
        <div class="text-center mt-3"><a href="/user_signup" class="text-decoration-none">Create Account</a> | <a href="/" class="text-decoration-none">Home</a></div>
    </div>
    """ + HTML_FOOTER

@app.route("/admin_login", methods=['GET', 'POST'])
def admin_login():
    error = ""
    if request.method == 'POST':
        if request.form.get('username') == "admin" and request.form.get('password') == "Bharat123@#$":
            session['admin_logged'] = True
            return redirect("/admin_dashboard")
        else:
            error = "Galat Admin Credentials!"

    error_div = f'<div class="alert alert-danger">{error}</div>' if error else ''
    return HTML_HEADER + f"""
    <div class="container mt-5" style="max-width: 400px;">
        <h3 class="mb-3 text-center">🔒 Admin Portal</h3>
        {error_div}
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
    page_count = cursor.fetchone()[0]

    cursor.execute("SELECT username, query, timestamp FROM search_history ORDER BY id DESC")
    all_histories = cursor.fetchall()
    conn.close()

    history_table = ""
    for h in all_histories:
        history_table += f"""
        <tr>
            <td><b>{h[0]}</b></td>
            <td>{h[1]}</td>
            <td><small class="text-muted">{h[2]}</small></td>
        </tr>
        """

    return HTML_HEADER + f"""
    <div class="container mt-5" style="max-width: 800px;">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h3>⚙️ Service Provider / Admin Control Center</h3>
            <a href="/admin_logout" class="btn btn-outline-danger btn-sm">Logout</a>
        </div>
        
        <div class="row mb-4">
            <div class="col-md-6">
                <div class="alert alert-success">Total Indexed Pages: <b>{page_count}</b></div>
            </div>
        </div>

        <div class="card p-4">
            <h5 class="mb-3">📊 All Users Search History</h5>
            <div class="table-responsive" style="max-height: 300px; overflow-y: auto;">
                <table class="table table-striped">
                    <thead>
                        <tr>
                            <th>Username / Email</th>
                            <th>Search Query</th>
                            <th>Time</th>
                        </tr>
                    </thead>
                    <tbody>
                        {history_table if history_table else '<tr><td colspan="3" class="text-center text-muted">Koi history available nahi hai.</td></tr>'}
                    </tbody>
                </table>
            </div>
        </div>

        <div class="mt-4 text-center"><a href="/" class="btn btn-light border">Go to Search Engine</a></div>
    </div>
    """ + HTML_FOOTER

@app.route("/admin_logout")
def admin_logout():
    session.pop('admin_logged', None)
    return redirect("/")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
