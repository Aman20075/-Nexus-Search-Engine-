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

# 🚫 Content Blocklist for Safe Search
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
        body { background: #f8f9fa; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; padding-bottom: 70px; }
        .top-header { display: flex; justify-content: space-between; align-items: center; padding: 12px 20px; background: #ffffff; }
        .creator-tag { font-size: 13px; font-weight: 600; color: #5f6368; }
        .user-profile-badge { background: #e8f0fe; color: #1a73e8; padding: 4px 12px; border-radius: 16px; font-size: 12px; font-weight: 500; }
        
        .bharat-brand { font-size: 48px; font-weight: 700; letter-spacing: -1.5px; margin-top: 15px; }
        
        .google-search-card { max-width: 580px; width: 90%; margin: 20px auto; position: relative; }
        .google-input { height: 52px; border-radius: 26px; padding-left: 50px; padding-right: 50px; border: 1px solid #dfe1e5; background: #ffffff; box-shadow: 0 1px 6px rgba(32,33,36,0.1); font-size: 16px; }
        .google-input:focus { outline: none; border-color: #4285f4; box-shadow: 0 2px 8px rgba(32,33,36,0.2); }
        .search-icon-left { position: absolute; left: 18px; top: 16px; color: #9aa0a6; font-size: 18px; }
        .mic-icon-right { position: absolute; right: 18px; top: 14px; color: #ea4335; font-size: 22px; cursor: pointer; }
        
        .quick-chips { display: flex; justify-content: center; gap: 10px; margin-bottom: 25px; flex-wrap: wrap; }
        .chip-btn { background: #ffffff; border: 1px solid #e0e0e0; border-radius: 20px; padding: 8px 16px; font-size: 14px; color: #3c4043; font-weight: 500; text-decoration: none; display: flex; align-items: center; gap: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
        .chip-btn:hover { background: #f1f3f4; }

        /* Bottom Navigation Bar like Google App */
        .bottom-nav { position: fixed; bottom: 0; left: 0; right: 0; background: #ffffff; border-top: 1px solid #dadce0; display: flex; justify-content: space-around; padding: 8px 0; z-index: 1000; }
        .nav-item-link { text-decoration: none; color: #5f6368; font-size: 11px; text-align: center; display: flex; flex-direction: column; align-items: center; }
        .nav-item-link i { font-size: 20px; margin-bottom: 2px; }
        .nav-item-link.active { color: #1a73e8; font-weight: 600; }

        .results-wrapper { max-width: 680px; margin: 0 auto; padding: 0 15px; }
        .result-card { background: #fff; border-radius: 12px; padding: 15px; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
        .result-title { color: #1a0dab; font-size: 17px; text-decoration: none; font-weight: 500; }
        .result-url { color: #202124; font-size: 12px; }
        .result-snippet { color: #4d5156; font-size: 13.5px; margin-top: 5px; }
    </style>
</head>
<body>
"""

HTML_FOOTER = """
<div class="bottom-nav">
    <a href="/" class="nav-item-link active"><i class="bi bi-house-door-fill"></i>Home</a>
    <a href="/my_history" class="nav-item-link"><i class="bi bi-clock-history"></i>History</a>
    <a href="/user_login" class="nav-item-link"><i class="bi bi-person-circle"></i>Account</a>
    <a href="/admin_login" class="nav-item-link"><i class="bi bi-shield-lock"></i>Admin</a>
</div>

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
        user_info_html = f'''
            <span class="user-profile-badge"><i class="bi bi-person-fill me-1"></i>{username}</span>
            <a href="/logout_verify" class="btn btn-outline-danger btn-sm ms-2" style="border-radius: 12px; font-size: 11px;">Logout</a>
        '''
    else:
        user_info_html = '<a href="/user_login" class="btn btn-primary btn-sm px-3" style="border-radius: 16px;">Sign in</a>'

    return HTML_HEADER + f"""
    <div class="top-header">
        <div class="creator-tag">🚀 Built by <b>Aman Giri</b></div>
        <div>{user_info_html}</div>
    </div>

    <div class="container text-center">
        <div class="bharat-brand">
            <span style="color:#FF9933">B</span><span style="color:#FF9933">h</span><span style="color:#000080">a</span><span style="color:#138808">r</span><span style="color:#138808">a</span><span style="color:#138808">t</span>
        </div>
        <p class="text-muted small mb-3">India's Safe AI Search Portal 🇮🇳</p>

        <form action="/search" method="GET" id="searchForm" class="google-search-card">
            <i class="bi bi-search search-icon-left"></i>
            <input type="text" name="q" id="searchInput" class="form-control google-input" placeholder="Search anything..." required autocomplete="off">
            <i class="bi bi-mic-fill mic-icon-right" onclick="startVoiceSearch()" title="Voice Search"></i>
        </form>

        <div class="quick-chips">
            <a href="#" class="chip-btn"><i class="bi bi-stars text-primary"></i> AI Search</a>
            <a href="#" class="chip-btn"><i class="bi bi-book text-success"></i> Education</a>
            <a href="#" class="chip-btn"><i class="bi bi-newspaper text-danger"></i> History</a>
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
        <div class="results-wrapper pt-5 text-center">
            <div class="alert alert-danger p-4 shadow-sm">
                <h5 class="alert-heading">🚫 Safe Search Active</h5>
                <p class="mb-0 small">Aapki search query <b>Bharat Safety Rules</b> ke tahat block kar di gayi hai.</p>
                <a href="/" class="btn btn-primary btn-sm mt-3">Back to Home</a>
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

    header_search = f"""
    <div class="bg-white border-bottom p-3 mb-3">
        <div class="d-flex align-items-center gap-3">
            <a href="/" class="bharat-brand text-decoration-none my-0" style="font-size: 24px;">
                <span style="color:#FF9933">B</span><span style="color:#000080">h</span><span style="color:#138808">at</span>
            </a>
            <form action="/search" method="GET" class="google-search-card my-0 flex-grow-1">
                <i class="bi bi-search search-icon-left" style="top:12px;"></i>
                <input type="text" name="q" value="{query}" class="form-control google-input" style="height: 42px; font-size: 14px;">
            </form>
        </div>
    </div>
    <div class="results-wrapper">
        <div class="alert alert-light border p-3 mb-3" style="border-radius: 12px;">
            ✨ <b>AI Insights:</b> Verified information index for <b>{query}</b>.
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
                <div class="result-snippet">{snippet}</div>
            </div>
            """
    else:
        body_results += f"""
        <div class="text-center text-muted p-4">
            No instant local records. Academic crawler is fetching more details.
        </div>
        """

    body_results += "</div>"
    return HTML_HEADER + header_search + body_results + HTML_FOOTER

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
        history_html = '<li class="list-group-item text-muted text-center py-4">Koi search history nahi hai.</li>'

    return HTML_HEADER + f"""
    <div class="container mt-4" style="max-width: 600px;">
        <h4 class="mb-3">📜 Search History</h4>
        <ul class="list-group shadow-sm border-0" style="border-radius: 12px; overflow: hidden;">
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
            session.clear()
            return redirect("/")
            
        password = request.form.get('password')
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            session.clear()
            return redirect("/")
        else:
            error = "Galat password!"

    return HTML_HEADER + f"""
    <div class="container mt-5" style="max-width: 380px;">
        <div class="bg-white p-4 rounded-4 shadow-sm border text-center">
            <h5 class="text-danger mb-3">Logout Confirm Karein</h5>
            {f'<div class="alert alert-danger small">{error}</div>' if error else ''}
            <form method="POST">
                {'<div class="mb-3"><input type="password" name="password" class="form-control" placeholder="Enter Password" required></div>' if login_type == 'manual' else ''}
                <button type="submit" class="btn btn-danger w-100 mb-2" style="border-radius: 20px;">Logout</button>
                <a href="/" class="btn btn-light w-100" style="border-radius: 20px;">Cancel</a>
            </form>
        </div>
    </div>
    """ + HTML_FOOTER

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
                <input type="email" name="email" class="form-control mb-3" placeholder="Gmail Address" required style="border-radius: 12px;">
                <button type="submit" class="btn btn-danger w-100" style="border-radius: 20px;">Continue</button>
            </form>
        </div>
    </div>
    """ + HTML_FOOTER

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
            msg = "Username already exists!"

    return HTML_HEADER + f"""
    <div class="container mt-5" style="max-width: 380px;">
        <div class="bg-white p-4 rounded-4 shadow-sm border">
            <h4 class="mb-3 text-center">Create Account</h4>
            {f'<div class="alert alert-danger small">{msg}</div>' if msg else ''}
            <form method="POST">
                <div class="mb-3"><input type="text" name="username" class="form-control" placeholder="Username / Email" required></div>
                <div class="mb-3"><input type="password" name="password" class="form-control" placeholder="Password" required></div>
                <button type="submit" class="btn btn-primary w-100" style="border-radius: 20px;">Sign Up</button>
            </form>
        </div>
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
                <input type="text" name="username" class="form-control mb-2" placeholder="Username" required>
                <input type="password" name="password" class="form-control mb-3" placeholder="Password" required>
                <button type="submit" class="btn btn-primary w-100 mb-2" style="border-radius: 20px;">Login</button>
            </form>
            <a href="/user_signup" class="small text-decoration-none">New user? Register here</a>
        </div>
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
            error = "Galat credentials!"

    return HTML_HEADER + f"""
    <div class="container mt-5" style="max-width: 380px;">
        <div class="bg-white p-4 rounded-4 shadow-sm border">
            <h4 class="mb-3 text-center">🔒 Admin Portal</h4>
            {f'<div class="alert alert-danger small">{error}</div>' if error else ''}
            <form method="POST">
                <input type="text" name="username" class="form-control mb-2" placeholder="Admin ID" required>
                <input type="password" name="password" class="form-control mb-3" placeholder="Password" required>
                <button type="submit" class="btn btn-dark w-100" style="border-radius: 20px;">Login</button>
            </form>
        </div>
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
        history_table += f"<tr><td>{h[0]}</td><td>{h[1]}</td><td><small>{h[2]}</small></td></tr>"

    return HTML_HEADER + f"""
    <div class="container mt-4" style="max-width: 700px;">
        <div class="d-flex justify-content-between align-items-center mb-3">
            <h3>⚙️ Admin Panel</h3>
            <a href="/admin_logout" class="btn btn-outline-danger btn-sm">Logout</a>
        </div>
        <div class="alert alert-info">Indexed Web Pages: <b>{page_count}</b></div>
        <div class="bg-white p-3 rounded-3 shadow-sm">
            <h6 class="mb-3">Search History Logs</h6>
            <div class="table-responsive" style="max-height: 300px;">
                <table class="table table-sm">
                    <thead><tr><th>User</th><th>Query</th><th>Time</th></tr></thead>
                    <tbody>{history_table if history_table else '<tr><td colspan="3">No history found.</td></tr>'}</tbody>
                </table>
            </div>
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
