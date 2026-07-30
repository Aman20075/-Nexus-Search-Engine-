from flask import Flask, request, redirect, url_for, session
import sqlite3
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import threading
import os
from urllib.parse import urljoin, urlparse
import time

app = Flask(__name__)
app.permanent_session_lifetime = 365 * 24 * 60 * 60  
app.secret_key = 'bharat_search_permanent_session_key_2026'
DB_PATH = 'search_engine.db'

# 👑 Owner Credentials
OWNER_USERNAME = "Aman Giri"
OWNER_PASSWORD = "@Aman2007"

# 🚫 Safe Search Blocklist
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
            role TEXT DEFAULT 'user'
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

# 🕷️ Advanced Automatic Recursive Crawler Logic
def perform_multi_page_crawl(start_url, max_pages=5, max_depth=2):
    visited = set()
    queue = [(start_url, 1)]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    pages_crawled = 0

    while queue and pages_crawled < max_pages:
        current_url, depth = queue.pop(0)

        if current_url in visited or depth > max_depth:
            continue

        visited.add(current_url)

        try:
            print(f"🕷️ Crawling URL: {current_url}")
            response = requests.get(current_url, headers=headers, timeout=5)
            print(f"📡 Status Code: {response.status_code}")

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                title = soup.title.string.strip() if soup.title and soup.title.string else current_url
                
                # सभी पैराग्राफ और हेडिंग्स से टेक्स्ट कलेक्ट करें ताकि डेटा खाली न रहे
                all_text_elements = soup.find_all(['p', 'span', 'div', 'h1', 'h2', 'h3'])
                paragraphs = [elem.get_text().strip() for elem in all_text_elements if len(elem.get_text().strip()) > 20]
                content = ' '.join(paragraphs)
                
                print(f"📝 Extracted Content Length: {len(content)} characters")

                if len(content) > 30:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT OR REPLACE INTO pages (url, title, content)
                        VALUES (?, ?, ?)
                    ''', (current_url, title, content))
                    conn.commit()
                    conn.close()
                    pages_crawled += 1
                    print(f"✅ Successfully Saved to Database: {title}")
                else:
                    print("⚠️ Content is too short, skipping save.")

                if depth < max_depth:
                    for a_tag in soup.find_all('a', href=True):
                        href = a_tag['href'].strip()
                        full_url = urljoin(current_url, href)
                        parsed_url = urlparse(full_url)

                        if parsed_url.scheme in ['http', 'https'] and full_url not in visited:
                            if not any(blocked in full_url for blocked in ['facebook.com', 'instagram.com', 'twitter.com', 'youtube.com']):
                                queue.append((full_url, depth + 1))

            time.sleep(1)

        except Exception as e:
            print(f"❌ Error crawling {current_url}: {e}")

def crawl_and_index_url(target_url):
    thread = threading.Thread(target=perform_multi_page_crawl, args=(target_url, 5, 2))
    thread.daemon = True
    thread.start()
    return True

HTML_HEADER = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Bharat AI Search Engine</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css">
    <style>
        html, body { height: 100%; margin: 0; background: #ffffff; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
        body { padding-bottom: 75px; }
        
        .top-bar-chrome { display: flex; justify-content: space-between; align-items: center; padding: 12px 18px; background: #ffffff; }
        .creator-badge { font-size: 13px; font-weight: 600; color: #5f6368; }
        
        .dots-btn { background: none; border: none; font-size: 22px; color: #444746; cursor: pointer; padding: 4px 8px; border-radius: 50%; }
        .dots-btn:hover { background: #f1f3f4; }
        
        .chrome-menu { border-radius: 20px 0 0 20px; width: 280px !important; }
        .chrome-action-bar { display: flex; justify-content: space-between; background: #f0f4f9; padding: 8px; border-radius: 24px; margin-bottom: 15px; }
        .chrome-action-icon { width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #444746; text-decoration: none; font-size: 16px; }
        .chrome-action-icon:hover { background: #e0e4e9; }
        
        .chrome-menu-item { display: flex; align-items: center; gap: 16px; padding: 12px 16px; font-size: 15px; color: #1f1f1f; text-decoration: none; border-radius: 12px; font-weight: 400; }
        .chrome-menu-item:hover { background: #f0f4f9; }
        .chrome-menu-item i { font-size: 18px; color: #444746; }
        .chrome-divider { height: 1px; background: #e0e4e9; margin: 8px 0; }
        
        .bharat-logo { font-size: 52px; font-weight: 700; letter-spacing: -1.5px; margin-top: 20px; }
        
        .google-search-container { max-width: 580px; width: 92%; margin: 24px auto 16px auto; position: relative; }
        .google-input { height: 54px; border-radius: 27px; padding-left: 52px; padding-right: 52px; border: 1px solid #dfe1e5; background: #ffffff; box-shadow: 0 1px 6px rgba(32,33,36,0.12); font-size: 16px; }
        .google-input:focus { outline: none; border-color: #4285f4; box-shadow: 0 2px 8px rgba(32,33,36,0.2); }
        .search-left-icon { position: absolute; left: 18px; top: 17px; color: #9aa0a6; font-size: 18px; }
        .mic-right-icon { position: absolute; right: 18px; top: 15px; color: #ea4335; font-size: 22px; cursor: pointer; }

        .chips-row { display: flex; justify-content: center; gap: 10px; flex-wrap: wrap; margin-bottom: 30px; }
        .chip-card { background: #f8f9fa; border: 1px solid #e8eaed; border-radius: 20px; padding: 10px 18px; font-size: 14px; font-weight: 500; color: #3c4043; text-decoration: none; display: flex; align-items: center; gap: 8px; }
        .chip-card:hover { background: #f1f3f4; }

        .bottom-nav-bar { position: fixed; bottom: 0; left: 0; right: 0; background: #ffffff; border-top: 1px solid #dadce0; display: flex; justify-content: space-around; padding: 8px 0; z-index: 9999; }
        .nav-link-item { text-decoration: none; color: #5f6368; font-size: 11px; text-align: center; display: flex; flex-direction: column; align-items: center; flex: 1; }
        .nav-link-item i { font-size: 20px; margin-bottom: 2px; }
        .nav-link-item.active { color: #1a73e8; font-weight: 600; }

        .results-wrapper { max-width: 680px; margin: 0 auto; padding: 0 16px; }
        .result-card { background: #fff; border-radius: 12px; padding: 16px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); border: 1px solid #f1f3f4; }
        .result-title { color: #1a0dab; font-size: 18px; text-decoration: none; font-weight: 400; }
        .result-url { color: #202124; font-size: 12px; margin-bottom: 4px; }
        .result-snippet { color: #4d5156; font-size: 14px; line-height: 1.5; }
    </style>
</head>
<body>
"""

def get_footer(active_tab='home'):
    home_active = 'active' if active_tab == 'home' else ''
    search_active = 'active' if active_tab == 'search' else ''
    history_active = 'active' if active_tab == 'history' else ''
    account_active = 'active' if active_tab == 'account' else ''

    return f"""
<div class="bottom-nav-bar" id="bottomNav">
    <a href="/" class="nav-link-item {home_active}"><i class="bi bi-house-door-fill"></i>Home</a>
    <a href="javascript:void(0)" onclick="focusSearchInput()" class="nav-link-item {search_active}"><i class="bi bi-search"></i>Search</a>
    <a href="/my_history" class="nav-link-item {history_active}"><i class="bi bi-clock-history"></i>History</a>
    <a href="/user_login" class="nav-link-item {account_active}"><i class="bi bi-person-circle"></i>Account</a>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
function focusSearchInput() {{
    var input = document.getElementById('searchInput');
    if (input) {{
        input.focus();
    }} else {{
        window.location.href = '/';
    }}
}}

function startVoiceSearch() {{
    if ('webkitSpeechRecognition' in window) {{
        var recognition = new webkitSpeechRecognition();
        recognition.lang = 'en-IN';
        recognition.start();
        recognition.onresult = function(event) {{
            document.getElementById('searchInput').value = event.results[0][0].transcript;
            document.getElementById('searchForm').submit();
        }};
    }} else {{
        alert("Voice search aapke browser me supported nahi hai.");
    }}
}}
</script>
</body>
</html>
"""

@app.route("/")
def home():
    user_logged = session.get('user_logged')
    admin_logged = session.get('admin_logged')
    owner_logged = session.get('owner_logged')
    username = session.get('username', '')

    if user_logged:
        user_info_section = f'<div class="px-3 py-2 mb-2 text-primary bg-light rounded-3 small">👤 <b>{username}</b></div>'
        login_logout_option = '<a href="/confirm_logout?type=user" class="chrome-menu-item text-danger"><i class="bi bi-box-arrow-right text-danger"></i>Logout</a>'
    else:
        user_info_section = ''
        login_logout_option = '<a href="/user_login" class="chrome-menu-item"><i class="bi bi-box-arrow-in-right"></i>User Login</a>'

    role_options = ''
    if owner_logged:
        role_options += '<a href="/owner_dashboard" class="chrome-menu-item text-warning"><i class="bi bi-crown-fill"></i> Owner Dashboard</a>'
        role_options += '<a href="/confirm_logout?type=owner" class="chrome-menu-item text-danger"><i class="bi bi-box-arrow-left"></i> Owner Logout</a>'
    else:
        if not user_logged:
            role_options += '<a href="/owner_login" class="chrome-menu-item"><i class="bi bi-shield-lock-fill"></i> Owner Login</a>'

    if not user_logged:
        if admin_logged or owner_logged:
            role_options += '<a href="/add_url" class="chrome-menu-item text-success"><i class="bi bi-gear-fill"></i> Admin Crawl Panel</a>'
            if admin_logged:
                role_options += '<a href="/confirm_logout?type=admin" class="chrome-menu-item text-danger"><i class="bi bi-lock-fill"></i> Admin Logout</a>'
        else:
            role_options += '<a href="/admin_login" class="chrome-menu-item"><i class="bi bi-shield-lock"></i> Admin Login</a>'

    top_bar_html = f"""
    <div class="top-bar-chrome">
        <div class="creator-badge">🚀 Created by <b>Aman Giri</b></div>
        <button class="dots-btn" type="button" data-bs-toggle="offcanvas" data-bs-target="#chromeMenu">
            <i class="bi bi-three-dots-vertical"></i>
        </button>
    </div>

    <div class="offcanvas offcanvas-end chrome-menu p-2" tabindex="-1" id="chromeMenu">
        <div class="offcanvas-body p-2">
            <div class="chrome-action-bar">
                <a href="/" class="chrome-action-icon"><i class="bi bi-house"></i></a>
                <a href="/my_history" class="chrome-action-icon"><i class="bi bi-star"></i></a>
                <a href="/" class="chrome-action-icon"><i class="bi bi-download"></i></a>
                <a href="/" class="chrome-action-icon"><i class="bi bi-info-circle"></i></a>
                <a href="javascript:location.reload()" class="chrome-action-icon"><i class="bi bi-arrow-clockwise"></i></a>
            </div>

            {user_info_section}

            <a href="/" class="chrome-menu-item"><i class="bi bi-plus-square"></i> New tab</a>
            <a href="/my_history" class="chrome-menu-item"><i class="bi bi-clock-history"></i> History</a>
            
            <div class="chrome-divider"></div>

            {login_logout_option}
            {role_options}
        </div>
    </div>
    """

    return HTML_HEADER + top_bar_html + f"""
    <div class="container text-center">
        <div class="bharat-logo mb-1">
            <span style="color:#FF9933">B</span><span style="color:#FF9933">h</span><span style="color:#000080">a</span><span style="color:#138808">r</span><span style="color:#138808">a</span><span style="color:#138808">t</span>
        </div>
        <p class="text-muted small mb-3">India's Safe AI Search Engine 🇮🇳</p>

        <form action="/search" method="GET" id="searchForm" class="google-search-container">
            <i class="bi bi-search search-left-icon"></i>
            <input type="text" name="q" id="searchInput" class="form-control google-input" placeholder="Search books, science, history..." required autocomplete="off">
            <i class="bi bi-mic-fill mic-right-icon" onclick="startVoiceSearch()"></i>
        </form>

        <div class="chips-row">
            <a href="#" class="chip-card"><i class="bi bi-stars text-primary"></i> AI Mode</a>
            <a href="#" class="chip-card"><i class="bi bi-book text-success"></i> Education</a>
            <a href="#" class="chip-card"><i class="bi bi-lightning text-warning"></i> Trending</a>
        </div>
    </div>
    """ + get_footer('home')

@app.route("/search")
def search():
    query = request.args.get('q', '').strip()
    if not query:
        return redirect("/")

    if not is_safe_query(query):
        return HTML_HEADER + f"""
        <div class="results-wrapper pt-5 text-center">
            <div class="alert alert-danger p-4 shadow-sm" style="border-radius: 16px;">
                <h5 class="alert-heading">🚫 Safe Search Active</h5>
                <p class="mb-0 small">Aapki search query <b>Bharat Safety Policy</b> ke khilaf hai.</p>
                <a href="/" class="btn btn-primary btn-sm mt-3" style="border-radius: 20px;">Back to Home</a>
            </div>
        </div>
        """ + get_footer('search')

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

    header_search = f"""
    <div class="bg-white border-bottom p-3 mb-3">
        <div class="d-flex align-items-center gap-2">
            <a href="/" class="bharat-logo text-decoration-none my-0 me-2" style="font-size: 26px;">
                <span style="color:#FF9933">B</span><span style="color:#000080">h</span><span style="color:#138808">at</span>
            </a>
            <form action="/search" method="GET" class="google-search-container my-0 flex-grow-1" style="max-width: 100%;">
                <i class="bi bi-search search-left-icon" style="top:12px;"></i>
                <input type="text" name="q" id="searchInput" value="{query}" class="form-control google-input" style="height: 42px; font-size: 14px;">
            </form>
        </div>
    </div>
    <div class="results-wrapper">
        <div class="alert alert-light border p-3 mb-3" style="border-radius: 12px;">
            ✨ <b>Bharat AI Overview:</b> Verified insights for <b>{query}</b>.
        </div>
    """

    body_results = ""
    if rows:
        for row in rows:
            url, title, content = row[0], row[1], row[2]
            snippet = content[:160] + "..." if len(content) > 160 else content
            body_results += f"""
            <div class="result-card">
                <div class="result-url">{url}</div>
                <a href="{url}" target="_blank" class="result-title">{title}</a>
                <div class="result-snippet mt-1">{snippet}</div>
            </div>
            """
    else:
        body_results += f"""
        <div class="text-center text-muted p-4">
            No records found for "{query}".
        </div>
        """

    body_results += "</div>"
    return HTML_HEADER + header_search + body_results + get_footer('search')

# 🔒 PASSWORD CONFIRMATION BEFORE LOGOUT ROUTE
@app.route("/confirm_logout", methods=['GET', 'POST'])
def confirm_logout():
    account_type = request.args.get('type', 'user')
    error = ""

    if request.method == 'POST':
        entered_password = request.form.get('password')

        if account_type == 'owner' and session.get('owner_logged'):
            if entered_password == OWNER_PASSWORD:
                session.pop('owner_logged', None)
                return redirect("/")
            else:
                error = "Incorrect Owner Password!"

        elif account_type == 'admin' and session.get('admin_logged'):
            admin_username = session.get('admin_username', 'admin')
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ? AND password = ? AND role = 'admin'", (admin_username, entered_password))
            admin = cursor.fetchone()
            conn.close()

            if admin:
                session.pop('admin_logged', None)
                session.pop('admin_username', None)
                return redirect("/")
            else:
                error = "Incorrect Admin Password!"

        elif account_type == 'user' and session.get('user_logged'):
            current_user = session.get('username')
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (current_user, entered_password))
            user = cursor.fetchone()
            conn.close()

            if user:
                session.pop('user_logged', None)
                session.pop('username', None)
                return redirect("/")
            else:
                error = "Incorrect Password!"

    return HTML_HEADER + f"""
    <div class="container mt-5" style="max-width: 400px;">
        <form method="POST" class="bg-white p-4 rounded-4 shadow-sm border">
            <h4 class="mb-3 text-center text-danger">🔒 Security Check</h4>
            <p class="text-muted small text-center mb-3">Logout karne ke liye apna Password darj karein.</p>
            {f'<div class="alert alert-danger small">{error}</div>' if error else ''}
            <input type="password" name="password" class="form-control mb-3" placeholder="Enter Password to Logout" required>
            <button type="submit" class="btn btn-danger w-100 mb-2" style="border-radius: 20px;">Confirm Logout</button>
            <a href="/" class="btn btn-light w-100" style="border-radius: 20px;">Cancel</a>
        </form>
    </div>
    """ + get_footer('home')

# 👑 OWNER LOGIN ROUTE
@app.route("/owner_login", methods=['GET', 'POST'])
def owner_login():
    error = ""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username == OWNER_USERNAME and password == OWNER_PASSWORD:
            session.permanent = True
            session['owner_logged'] = True
            return redirect("/owner_dashboard")
        else:
            error = "Invalid Owner Credentials!"

    return HTML_HEADER + f"""
    <div class="container mt-5" style="max-width: 400px;">
        <form method="POST" class="bg-white p-4 rounded-4 shadow-sm border">
            <h4 class="mb-3 text-center text-warning">👑 Owner Login</h4>
            {f'<div class="alert alert-danger">{error}</div>' if error else ''}
            <input type="text" name="username" class="form-control mb-3" placeholder="Owner Username" required>
            <input type="password" name="password" class="form-control mb-3" placeholder="Owner Password" required>
            <button type="submit" class="btn btn-warning w-100 fw-bold" style="border-radius: 20px;">Login as Owner</button>
        </form>
    </div>
    """ + get_footer('home')

# 📊 OWNER DASHBOARD
@app.route("/owner_dashboard", methods=['GET', 'POST'])
def owner_dashboard():
    if not session.get('owner_logged'):
        return redirect("/owner_login")

    message = ""
    if request.method == 'POST':
        if 'url' in request.form:
            new_url = request.form.get('url', '').strip()
            if new_url:
                crawl_and_index_url(new_url)
                message = "✅ Link successfully added and multi-page crawling started in background!"
        else:
            new_user = request.form.get('username', '').strip()
            new_pass = request.form.get('password', '').strip()
            new_role = request.form.get('role', 'user')

            if new_user and new_pass:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                try:
                    cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (new_user, new_pass, new_role))
                    conn.commit()
                    message = f"✅ Added new {new_role.upper()}: {new_user} successfully!"
                except sqlite3.IntegrityError:
                    message = "⚠️ Username already exists!"
                conn.close()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, password, role FROM users")
    users_list = cursor.fetchall()
    conn.close()

    users_rows = ""
    for u in users_list:
        badge_color = 'bg-danger' if u[3] == 'admin' else 'bg-primary'
        users_rows += f"""
        <tr>
            <td>{u[0]}</td>
            <td><b>{u[1]}</b></td>
            <td><code>{u[2]}</code></td>
            <td><span class='badge {badge_color}'>{u[3].upper()}</span></td>
            <td><a href="/delete_account/{u[0]}" class="btn btn-danger btn-sm py-0" onclick="return confirm('Delete this account permanently?')">Delete</a></td>
        </tr>
        """

    return HTML_HEADER + f"""
    <div class="container mt-4 mb-5" style="max-width: 750px;">
        <div class="bg-white p-4 rounded-4 shadow-sm border mb-4">
            <h4 class="mb-3 text-center">👑 Owner Control Center ({OWNER_USERNAME})</h4>
            {f'<div class="alert alert-info">{message}</div>' if message else ''}
            
            <form method="POST" class="border p-3 rounded-3 mb-4 bg-light">
                <h6>🔗 Add Direct Link (Crawl Panel)</h6>
                <div class="input-group">
                    <input type="url" name="url" class="form-control" placeholder="https://example.com" required>
                    <button type="submit" class="btn btn-primary">Add Link</button>
                </div>
            </form>

            <form method="POST" class="row g-2 border p-3 rounded-3 mb-4">
                <h6>➕ Add New Admin or User</h6>
                <div class="col-md-4">
                    <input type="text" name="username" class="form-control" placeholder="Username" required>
                </div>
                <div class="col-md-4">
                    <input type="text" name="password" class="form-control" placeholder="Set Password" required>
                </div>
                <div class="col-md-2">
                    <select name="role" class="form-select">
                        <option value="admin">Admin</option>
                        <option value="user">User</option>
                    </select>
                </div>
                <div class="col-md-2">
                    <button type="submit" class="btn btn-success w-100">Add</button>
                </div>
            </form>

            <h5 class="text-secondary">👥 Managed Accounts List</h5>
            <div class="table-responsive">
                <table class="table table-bordered table-striped mt-2 align-middle">
                    <thead class="table-dark">
                        <tr><th>ID</th><th>Username</th><th>Password</th><th>Role</th><th>Action</th></tr>
                    </thead>
                    <tbody>
                        {users_rows if users_rows else '<tr><td colspan="5" class="text-center text-muted">No accounts added yet.</td></tr>'}
                    </tbody>
                </table>
            </div>
            
            <div class="mt-3 text-center">
                <a href="/confirm_logout?type=owner" class="btn btn-outline-danger btn-sm" style="border-radius: 20px;">Owner Logout</a>
            </div>
        </div>
    </div>
    """ + get_footer('home')

@app.route("/delete_account/<int:user_id>")
def delete_account(user_id):
    if not session.get('owner_logged'):
        return redirect("/owner_login")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT username, role FROM users WHERE id = ?", (user_id,))
    target_user = cursor.fetchone()

    if target_user:
        target_username, target_role = target_user[0], target_user[1]
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()

        if target_role == 'admin' and session.get('admin_username') == target_username:
            session.pop('admin_logged', None)
            session.pop('admin_username', None)
            
        elif target_role == 'user' and session.get('username') == target_username:
            session.pop('user_logged', None)
            session.pop('username', None)

    conn.close()
    return redirect("/owner_dashboard")

@app.route("/admin_login", methods=['GET', 'POST'])
def admin_login():
    error = ""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND password = ? AND role = 'admin'", (username, password))
        admin = cursor.fetchone()
        conn.close()

        if admin:
            session.permanent = True
            session['admin_logged'] = True
            session['admin_username'] = username
            return redirect("/add_url")
        else:
            error = "Invalid Admin Credentials!"

    return HTML_HEADER + f"""
    <div class="container mt-5" style="max-width: 400px;">
        <form method="POST" class="bg-white p-4 rounded-4 shadow-sm border">
            <h4 class="mb-3 text-center">🔐 Admin Login</h4>
            {f'<div class="alert alert-danger">{error}</div>' if error else ''}
            <input type="text" name="username" class="form-control mb-3" placeholder="Admin Username" required>
            <input type="password" name="password" class="form-control mb-3" placeholder="Admin Password" required>
            <button type="submit" class="btn btn-dark w-100" style="border-radius: 20px;">Login as Admin</button>
        </form>
    </div>
    """ + get_footer('home')

@app.route("/add_url", methods=['GET', 'POST'])
def add_url():
    if not session.get('admin_logged') and not session.get('owner_logged'):
        return redirect("/admin_login")

    message = ""
    if request.method == 'POST':
        url_to_crawl = request.form.get('url', '').strip()
        if url_to_crawl:
            crawl_and_index_url(url_to_crawl)
            message = "✅ Automatic Multi-Page Crawling Started in Background!"

    return HTML_HEADER + f"""
    <div class="container mt-5" style="max-width: 500px;">
        <div class="bg-white p-4 rounded-4 shadow-sm border">
            <h4 class="mb-3 text-center">⚙️ Admin Crawl Panel</h4>
            {f'<div class="alert alert-success">{message}</div>' if message else ''}
            <form method="POST">
                <div class="mb-3">
                    <label class="form-label">Target URL to Auto-Crawl</label>
                    <input type="url" name="url" class="form-control" placeholder="https://example.com" required>
                </div>
                <button type="submit" class="btn btn-success w-100" style="border-radius: 20px;">Start Auto-Crawl</button>
            </form>
        </div>
    </div>
    """ + get_footer('home')

@app.route("/user_login", methods=['GET', 'POST'])
def user_login():
    if session.get('user_logged'):
        username = session.get('username', 'User')
        
        return HTML_HEADER + f"""
        <div class="container mt-5" style="max-width: 400px;">
            <div class="bg-white p-4 rounded-4 shadow-sm border text-center">
                <div class="mb-3">
                    <i class="bi bi-person-circle text-primary" style="font-size: 64px;"></i>
                </div>
                <h4>My Profile</h4>
                <div class="alert alert-light border my-3">
                    <div class="small text-muted mb-1">Logged in as</div>
                    <div class="fw-bold text-dark fs-5">{username}</div>
                </div>
                <a href="/confirm_logout?type=user" class="btn btn-outline-danger w-100" style="border-radius: 20px;">Logout</a>
            </div>
        </div>
        """ + get_footer('account')

    error = ""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND password = ? AND role = 'user'", (username, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session.permanent = True
            session['user_logged'] = True
            session['username'] = username
            return redirect("/")
        else:
            error = "Invalid Credentials! Contact Owner to get an account."

    return HTML_HEADER + f"""
    <div class="container mt-5" style="max-width: 400px;">
        <form method="POST" class="bg-white p-4 rounded-4 shadow-sm border">
            <h4 class="mb-3 text-center">User Login</h4>
            {f'<div class="alert alert-danger small">{error}</div>' if error else ''}
            <input type="text" name="username" class="form-control mb-3" placeholder="Username" required>
            <input type="password" name="password" class="form-control mb-3" placeholder="Password" required>
            <button type="submit" class="btn btn-primary w-100" style="border-radius: 20px;">Login</button>
        </form>
    </div>
    """ + get_footer('account')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
