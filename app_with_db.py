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

# 🕷️ Advanced Recursive Web Crawler (Admin Controlled)
def crawl_and_index_url(target_url):
    try:
        # Browser-like headers to avoid website blocking
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(target_url, headers=headers, timeout=6)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            title = soup.title.string.strip() if soup.title and soup.title.string else target_url
            paragraphs = [p.get_text().strip() for p in soup.find_all('p')]
            content = ' '.join(paragraphs)
            
            if len(content) > 100:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO pages (url, title, content)
                    VALUES (?, ?, ?)
                ''', (target_url, title, content))
                
                # 🔄 Automatic Sub-Links Crawling (1 लिंक से 5 और पेजों को ऑटोमैटिक लाना)
                sub_links = []
                for a_tag in soup.find_all('a', href=True):
                    link = a_tag['href']
                    if link.startswith('/wiki/') and ':' not in link:
                        full_url = f"https://en.wikipedia.org{link}"
                        if full_url not in sub_links and full_url != target_url:
                            sub_links.append(full_url)
                    elif link.startswith('http') and target_url in link:
                        if link not in sub_links and link != target_url:
                            sub_links.append(link)
                            
                    if len(sub_links) >= 5:
                        break
                
                # Sub-links को क्रॉल करना
                for sub_url in sub_links:
                    try:
                        sub_res = requests.get(sub_url, headers=headers, timeout=4)
                        if sub_res.status_code == 200:
                            sub_soup = BeautifulSoup(sub_res.text, 'html.parser')
                            sub_title = sub_soup.title.string.strip() if sub_soup.title else sub_url
                            sub_content = ' '.join([p.get_text().strip() for p in sub_soup.find_all('p')])
                            if len(sub_content) > 100:
                                cursor.execute('''
                                    INSERT OR REPLACE INTO pages (url, title, content)
                                    VALUES (?, ?, ?)
                                ''', (sub_url, sub_title, sub_content))
                    except Exception as sub_e:
                        print(f"Sub-link crawl error: {sub_e}")
                
                conn.commit()
                conn.close()
                return True
    except Exception as e:
        print(f"Crawling Error: {e}")
    return False

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

        /* Fixed Bottom Nav Bar */
        .bottom-nav-bar { position: fixed; bottom: 0; left: 0; right: 0; background: #ffffff; border-top: 1px solid #dadce0; display: flex; justify-content: space-around; padding: 8px 0; z-index: 9999; transform: translateZ(0); }
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

// 📱 Keyboard Hide/Show Logic for Mobile Navigation
var navBar = document.getElementById('bottomNav');
if (window.visualViewport) {{
    window.visualViewport.addEventListener('resize', function() {{
        if (window.visualViewport.height < window.innerHeight - 100) {{
            navBar.style.display = 'none';
        }} else {{
            navBar.style.display = 'flex';
        }}
    }});
}} else {{
    window.addEventListener('focusin', function(e) {{
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {{
            navBar.style.display = 'none';
        }}
    }});
    window.addEventListener('focusout', function(e) {{
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {{
            navBar.style.display = 'flex';
        }}
    }});
}}
</script>
</body>
</html>
"""

@app.route("/")
def home():
    user_logged = session.get('user_logged')
    username = session.get('username', '')

    if user_logged:
        user_info_section = f'<div class="px-3 py-2 mb-2 text-primary bg-light rounded-3 small">👤 <b>{username}</b></div>'
        login_logout_option = '<a href="/logout_verify" class="chrome-menu-item text-danger"><i class="bi bi-box-arrow-right text-danger"></i>Logout</a>'
    else:
        user_info_section = ''
        login_logout_option = '<a href="/user_login" class="chrome-menu-item"><i class="bi bi-box-arrow-in-right"></i>Login / Sign Up</a>'

    top_bar_html = f"""
    <div class="top-bar-chrome">
        <div class="creator-badge">🚀 Created by <b>Aman Giri</b></div>
        <button class="dots-btn" type="button" data-bs-toggle="offcanvas" data-bs-target="#chromeMenu" aria-controls="chromeMenu">
            <i class="bi bi-three-dots-vertical"></i>
        </button>
    </div>

    <div class="offcanvas offcanvas-end chrome-menu p-2" tabindex="-1" id="chromeMenu">
        <div class="offcanvas-body p-2">
            <div class="chrome-action-bar">
                <a href="/" class="chrome-action-icon" title="Home"><i class="bi bi-house"></i></a>
                <a href="/my_history" class="chrome-action-icon" title="Bookmarks"><i class="bi bi-star"></i></a>
                <a href="/" class="chrome-action-icon" title="Download"><i class="bi bi-download"></i></a>
                <a href="/" class="chrome-action-icon" title="Info"><i class="bi bi-info-circle"></i></a>
                <a href="javascript:location.reload()" class="chrome-action-icon" title="Reload"><i class="bi bi-arrow-clockwise"></i></a>
            </div>

            {user_info_section}

            <a href="/" class="chrome-menu-item"><i class="bi bi-plus-square"></i> New tab</a>
            <a href="/my_history" class="chrome-menu-item"><i class="bi bi-clock-history"></i> History</a>
            
            <div class="chrome-divider"></div>

            {login_logout_option}
            <a href="/admin_login" class="chrome-menu-item"><i class="bi bi-gear"></i> Admin Settings</a>
            <a href="#" class="chrome-menu-item"><i class="bi bi-question-circle"></i> Help & feedback</a>
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
            <input type="text" name="q" id="searchInput" class="form-control google-input" placeholder="Search books, science, history or concepts..." required autocomplete="off">
            <i class="bi bi-mic-fill mic-right-icon" onclick="startVoiceSearch()" title="Voice Search"></i>
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
            No records found. Contact Admin to crawl/index content for <b>"{query}"</b>.
        </div>
        """

    body_results += "</div>"
    return HTML_HEADER + header_search + body_results + get_footer('search')

@app.route("/user_login", methods=['GET', 'POST'])
def user_login():
    # 👤 User Profile Panel if Already Logged In
    if session.get('user_logged'):
        username = session.get('username', 'User')
        login_type = session.get('login_type', 'manual')
        
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
                    <span class="badge bg-secondary mt-1">{login_type.upper()} Account</span>
                </div>
                
                <a href="/my_history" class="btn btn-outline-primary w-100 mb-2" style="border-radius: 20px;">
                    <i class="bi bi-clock-history me-1"></i> Search History
                </a>
                <a href="/logout_verify" class="btn btn-outline-danger w-100" style="border-radius: 20px;">
                    <i class="bi bi-box-arrow-right me-1"></i> Logout
                </a>
            </div>
        </div>
        """ + get_footer('account')

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
            error = "Galat details!"

    return HTML_HEADER + f"""
    <div class="container mt-4" style="max-width: 380px;">
        <div class="bg-white p-4 rounded-4 shadow-sm border text-center">
            <h4 class="mb-3">Welcome Back</h4>
            {f'<div class="alert alert-danger small">{error}</div>' if error else ''}
            
            <a href="/social_login/google" class="btn btn-outline-danger w-100 mb-2" style="border-radius: 20px;">
                <i class="bi bi-google me-2"></i> Gmail Login
            </a>
            <a href="/social_login/phone" class="btn btn-outline-success w-100 mb-3" style="border-radius: 20px;">
                <i class="bi bi-phone me-2"></i> Mobile Login
            </a>
            
            <div class="text-muted small mb-3">— OR —</div>

            <form method="POST">
                <input type="text" name="username" class="form-control mb-2" placeholder="Username" required style="border-radius: 12px;">
                <input type="password" name="password" class="form-control mb-3" placeholder="Password" required style="border-radius: 12px;">
                <button type="submit" class="btn btn-primary w-100 mb-2" style="border-radius: 20px;">Login</button>
            </form>
            <a href="/user_signup" class="small text-decoration-none">New user? Register here</a>
        </div>
    </div>
    """ + get_footer('account')

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
            <li class="list-group-item d-flex justify-content-between align-items-center py-3">
                <span>🔍 <b>{item[0]}</b></span>
                <span class="text-muted small">{item[1]}</span>
            </li>
            """
    else:
        history_html = '<li class="list-group-item text-muted text-center py-4">Aapne abhi tak kuch search nahi kiya hai.</li>'

    return HTML_HEADER + f"""
    <div class="container mt-4" style="max-width: 600px;">
        <div class="d-flex justify-content-between align-items-center mb-3">
            <h4 class="m-0">📜 Search History</h4>
            <a href="/" class="btn btn-outline-primary btn-sm" style="border-radius: 16px;">← Back</a>
        </div>
        <ul class="list-group shadow-sm border-0" style="border-radius: 12px; overflow: hidden;">
            {history_html}
        </ul>
    </div>
    """ + get_footer('history')

@app.route("/logout_verify", methods=['GET', 'POST'])
def logout_verify():
    session.clear()
    return redirect("/")

@app.route("/social_login/google", methods=['GET', 'POST'])
def google_login():
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

    return HTML_HEADER + f"""
    <div class="container mt-5" style="max-width: 380px;">
        <div class="bg-white p-4 rounded-4 shadow-sm border text-center">
            <h5 class="mb-3"><i class="bi bi-google text-danger me-2"></i>Google Sign-In</h5>
            <form method="POST">
                <input type="email" name="email" class="form-control mb-3" placeholder="example@gmail.com" required style="border-radius: 12px;">
                <button type="submit" class="btn btn-danger w-100" style="border-radius: 20px;">Continue</button>
            </form>
            <div class="mt-3"><a href="/user_login" class="small text-decoration-none">Cancel</a></div>
        </div>
    </div>
    """ + get_footer('account')

@app.route("/social_login/phone", methods=['GET', 'POST'])
def phone_login():
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

    return HTML_HEADER + f"""
    <div class="container mt-5" style="max-width: 380px;">
        <div class="bg-white p-4 rounded-4 shadow-sm border text-center">
            <h5 class="mb-3"><i class="bi bi-phone text-success me-2"></i>Phone Sign-In</h5>
            <form method="POST">
                <input type="tel" name="phone" class="form-control mb-3" placeholder="Mobile Number" maxlength="10" required style="border-radius: 12px;">
                <button type="submit" class="btn btn-success w-100" style="border-radius: 20px;">Continue</button>
            </form>
            <div class="mt-3"><a href="/user_login" class="small text-decoration-none">Cancel</a></div>
        </div>
    </div>
    """ + get_footer('account')

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
            msg = "Username pehle se registered hai!"

    return HTML_HEADER + f"""
    <div class="container mt-5" style="max-width: 380px;">
        <div class="bg-white p-4 rounded-4 shadow-sm border">
            <h4 class="mb-3 text-center">Create Account</h4>
            {f'<div class="alert alert-danger small">{msg}</div>' if msg else ''}
            <form method="POST">
                <div class="mb-3"><input type="text" name="username" class="form-control" placeholder="Username / Email" required style="border-radius: 12px;"></div>
                <div class="mb-3"><input type="password" name="password" class="form-control" placeholder="Password" required style="border-radius: 12px;"></div>
                <button type="submit" class="btn btn-primary w-100" style="border-radius: 20px;">Register</button>
            </form>
            <div class="mt-3 text-center"><a href="/user_login" class="small text-decoration-none">Already have account? Login</a></div>
        </div>
    </div>
    """ + get_footer('account')

@app.route("/admin_login", methods=['GET', 'POST'])
def admin_login():
    error = ""
    if request.method == 'POST':
        if request.form.get('username') == "admin" and request.form.get('password') == "Bharat123@#$":
            session['admin_logged'] = True
            return redirect("/admin_dashboard")
        else:
            error = "Galat credentials!"

    return HTML_HEADER + f"""
    <div class="container mt-5" style="max-width: 380px;">
        <div class="bg-white p-4 rounded-4 shadow-sm border">
            <h4 class="mb-3 text-center">🔒 Admin Portal</h4>
            {f'<div class="alert alert-danger small">{error}</div>' if error else ''}
            <form method="POST">
                <input type="text" name="username" class="form-control mb-2" placeholder="Admin ID" required style="border-radius: 12px;">
                <input type="password" name="password" class="form-control mb-3" placeholder="Password" required style="border-radius: 12px;">
                <button type="submit" class="btn btn-dark w-100" style="border-radius: 20px;">Login</button>
            </form>
        </div>
    </div>
    """ + get_footer()

# ⚙️ ADMIN DASHBOARD WITH CRAWLER & PAGE ADDING CONTROL
@app.route("/admin_dashboard", methods=['GET', 'POST'])
def admin_dashboard():
    if not session.get('admin_logged'):
        return redirect("/admin_login")

    msg = ""
    if request.method == 'POST':
        action = request.form.get('action')
        
        # 🕷️ Multi-Page Auto-Crawler
        if action == 'crawl_url':
            url_to_crawl = request.form.get('target_url')
            if crawl_and_index_url(url_to_crawl):
                msg = '<div class="alert alert-success">URL & internal sub-links successfully crawled and indexed!</div>'
            else:
                msg = '<div class="alert alert-danger">Crawling failed or URL blocked/invalid.</div>'
                
        # 📝 Custom Page Creation
        elif action == 'add_page':
            custom_url = request.form.get('custom_url')
            custom_title = request.form.get('custom_title')
            custom_content = request.form.get('custom_content')
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO pages (url, title, content) VALUES (?, ?, ?)", 
                           (custom_url, custom_title, custom_content))
            conn.commit()
            conn.close()
            msg = '<div class="alert alert-success">Custom page added successfully!</div>'

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM pages")
    page_count = cursor.fetchone()[0]

    cursor.execute("SELECT username, query, timestamp FROM search_history ORDER BY id DESC")
    all_histories = cursor.fetchall()
    conn.close()

    history_table = ""
    for h in all_histories:
        history_table += f"<tr><td>{h[0]}</td><td>{h[1]}</td><td><small>{h[2]}</small></td></tr>"

    return HTML_HEADER + f"""
    <div class="container mt-4 mb-5" style="max-width: 750px;">
        <div class="d-flex justify-content-between align-items-center mb-3">
            <h3>⚙️ Admin Panel</h3>
            <a href="/admin_logout" class="btn btn-outline-danger btn-sm" style="border-radius:16px;">Logout</a>
        </div>
        
        {msg}

        <div class="alert alert-info mb-4">Total Indexed Web Pages: <b>{page_count}</b></div>
        
        <div class="bg-white p-3 rounded-3 shadow-sm border mb-4">
            <h6 class="fw-bold mb-2">🕷️ Advanced Multi-Page Crawler</h6>
            <p class="text-muted extra-small mb-2" style="font-size: 12px;">Link daalne par ye us page + uske andar ke 5 aur related pages ko automatically index kar leta hai.</p>
            <form method="POST" class="d-flex gap-2">
                <input type="hidden" name="action" value="crawl_url">
                <input type="url" name="target_url" class="form-control" placeholder="https://en.wikipedia.org/wiki/India" required style="border-radius: 12px;">
                <button type="submit" class="btn btn-primary text-nowrap" style="border-radius: 12px;">Start Crawling</button>
            </form>
        </div>

        <div class="bg-white p-3 rounded-3 shadow-sm border mb-4">
            <h6 class="fw-bold mb-2">➕ Add Custom Page Content</h6>
            <form method="POST">
                <input type="hidden" name="action" value="add_page">
                <input type="text" name="custom_url" class="form-control mb-2" placeholder="Page URL (e.g., https://bharat.com/about)" required style="border-radius: 12px;">
                <input type="text" name="custom_title" class="form-control mb-2" placeholder="Page Title" required style="border-radius: 12px;">
                <textarea name="custom_content" class="form-control mb-2" rows="3" placeholder="Page Content/Summary..." required style="border-radius: 12px;"></textarea>
                <button type="submit" class="btn btn-success w-100" style="border-radius: 12px;">Save Page</button>
            </form>
        </div>

        <div class="bg-white p-3 rounded-3 shadow-sm border">
            <h6 class="fw-bold mb-3">📜 User Search Logs</h6>
            <div class="table-responsive" style="max-height: 250px;">
                <table class="table table-sm align-middle">
                    <thead><tr><th>User</th><th>Query</th><th>Time</th></tr></thead>
                    <tbody>{history_table if history_table else '<tr><td colspan="3">No history found.</td></tr>'}</tbody>
                </table>
            </div>
        </div>
    </div>
    """ + get_footer()

@app.route("/admin_logout")
def admin_logout():
    session.pop('admin_logged', None)
    return redirect("/")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
