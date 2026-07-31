from flask import Flask, request
import requests

app = Flask(__name__)

# Home Page (Choice 2: User Input Form)
@app.route("/")
def home():
    return """
    <div style='text-align: center; font-family: Arial; margin-top: 50px;'>
        <h1 style='color: #6c5ce7;'>Welcome to Python Web App! 🚀</h1>
        <p style='font-size: 18px;'>Apna naam enter karke personalised greeting dekhein:</p>
        
        <form action='/greet' method='GET' style='margin-top: 20px;'>
            <input type='text' name='username' placeholder='Enter your name...' style='padding: 10px; font-size: 16px; border-radius: 5px; border: 1px solid #ccc;' required>
            <button type='submit' style='padding: 10px 20px; font-size: 16px; background-color: #6c5ce7; color: white; border: none; border-radius: 5px; cursor: pointer;'>Submit</button>
        </form>
        
        <br><br>
        <a href='/crypto' style='color: #00b894; font-size: 18px; font-weight: bold;'>📈 Check Live Crypto Prices Page ➔</a>
    </div>
    """

# Personalised Greeting Page
@app.route("/greet")
def greet():
    name = request.args.get('username', 'Guest')
    return f"""
    <div style='text-align: center; font-family: Arial; margin-top: 50px;'>
        <h1 style='color: #00b894;'>Hello, {name}! 👋</h1>
        <p style='font-size: 18px;'>Aapka Python backend successful input handle kar raha hai.</p>
        <br>
        <a href='/' style='color: #6c5ce7;'>← Back to Home Page</a>
    </div>
    """

# Crypto Tracker Page (Choice 1)
@app.route("/crypto")
def crypto():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd"
        res = requests.get(url).json()
        btc = res['bitcoin']['usd']
        eth = res['ethereum']['usd']
        status = f"<p style='color: green;'>Live Data Fetched Successfully!</p>"
    except:
        btc, eth = "N/A", "N/A"
        status = f"<p style='color: red;'>API Connection Error</p>"

    return f"""
    <div style='text-align: center; font-family: Arial; margin-top: 50px;'>
        <h1 style='color: #f39c12;'>📈 Live Crypto Rates (Web Portal)</h1>
        {status}
        <div style='display: inline-block; background: #2c3e50; color: white; padding: 20px; border-radius: 10px; margin: 10px;'>
            <h3>Bitcoin (BTC)</h3>
            <p style='font-size: 24px;'>${btc}</p>
        </div>
        <div style='display: inline-block; background: #2c3e50; color: white; padding: 20px; border-radius: 10px; margin: 10px;'>
            <h3>Ethereum (ETH)</h3>
            <p style='font-size: 24px;'>${eth}</p>
        </div>
        <br><br>
        <a href='/' style='color: #6c5ce7;'>← Back to Home Page</a>
    </div>
    """

if __name__ == "__main__":
    app.run(debug=True)import tkinter as tk
from tkinter import messagebox
import sqlite3
import webbrowser

def search_and_rank():
    query = search_entry.get().strip().lower()
    result_box.delete("1.0", tk.END)
    
    if not query:
        result_box.insert(tk.END, "⚠️ Kripya koi word search box me type karein!\n", "warning")
        return

    try:
        conn = sqlite3.connect("search_engine.db")
        cursor = conn.cursor()
        cursor.execute("SELECT title, url, snippet FROM pages")
        rows = cursor.fetchall()
        conn.close()
    except sqlite3.OperationalError:
        messagebox.showerror("Error", "'search_engine.db' nahi mili! Pehle crawler.py chalao.")
        return

    ranked_results = []

    # Relevance Ranking Logic (Keyword Frequency Score)
    for title, url, snippet in rows:
        title_lower = title.lower()
        snippet_lower = snippet.lower()
        
        # Scoring: Title me match = 3 points, Snippet me match = 1 point
        score = (title_lower.count(query) * 3) + snippet_lower.count(query)

        if score > 0:
            ranked_results.append((score, title, url, snippet))

    # Highest score wale result ko pehle dikhana (Sorting)
    ranked_results.sort(key=lambda x: x[0], reverse=True)

    result_box.insert(tk.END, f"🔎 Search Results for: '{query}' ({len(ranked_results)} found)\n", "header")
    result_box.insert(tk.END, "━"*55 + "\n\n", "border")

    if not ranked_results:
        result_box.insert(tk.END, "❌ Koi bhi matching result nahi mila.", "warning")
        return

    for rank, (score, title, url, snippet) in enumerate(ranked_results, start=1):
        result_box.insert(tk.END, f"[{rank}] {title} (Score: {score})\n", "title")
        
        # Clickable URL Link create karna
        start_idx = result_box.index(tk.END)
        result_box.insert(tk.END, f"🔗 {url}\n", "url")
        end_idx = result_box.index(tk.END)
        
        # Hyperlink Tag Assignment
        tag_name = f"link_{rank}"
        result_box.tag_add(tag_name, start_idx, end_idx)
        result_box.tag_config(tag_name, foreground="#89b4fa", underline=True)
        
        # Click handler attach karna
        result_box.tag_bind(tag_name, "<Button-1>", lambda e, link=url: open_browser(link))
        result_box.tag_bind(tag_name, "<Enter>", lambda e: result_box.config(cursor="hand2"))
        result_box.tag_bind(tag_name, "<Leave>", lambda e: result_box.config(cursor=""))

        result_box.insert(tk.END, f"📄 {snippet}\n", "snippet")
        result_box.insert(tk.END, "-"*55 + "\n\n", "border")

def open_browser(url):
    webbrowser.open(url)

# GUI Dark Theme Setup
root = tk.Tk()
root.title("Nexus Search Engine Pro ⚡")
root.geometry("680x580")
root.configure(bg="#1e1e2e")

title_label = tk.Label(
    root, text="⚡ NEXUS SEARCH PRO", 
    font=("Segoe UI", 18, "bold"), 
    bg="#1e1e2e", fg="#cba6f7"
)
title_label.pack(pady=15)

frame = tk.Frame(root, bg="#1e1e2e")
frame.pack(pady=5)

search_entry = tk.Entry(
    frame, font=("Segoe UI", 12), width=35, 
    bg="#313244", fg="#cdd6f4", insertbackground="white", 
    relief="flat", bd=5
)
search_entry.pack(side=tk.LEFT, padx=5)

search_button = tk.Button(
    frame, text="Search 🔍", font=("Segoe UI", 10, "bold"), 
    bg="#89b4fa", fg="#11111b", activebackground="#b4befe", 
    relief="flat", cursor="hand2", command=search_and_rank
)
search_button.pack(side=tk.LEFT, padx=5)

result_box = tk.Text(
    root, font=("Consolas", 10), width=75, height=21, 
    bg="#181825", fg="#cdd6f4", relief="flat", bd=10, padx=10, pady=10
)
result_box.pack(pady=15, padx=15)

# Styling Tags
result_box.tag_config("header", foreground="#f9e2af", font=("Segoe UI", 11, "bold"))
result_box.tag_config("title", foreground="#a6e3a1", font=("Segoe UI", 10, "bold"))
result_box.tag_config("snippet", foreground="#bac2de")
result_box.tag_config("border", foreground="#45475a")
result_box.tag_config("warning", foreground="#f38ba8")

root.mainloop()import requests
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
print("-----------------------------------")from flask import Flask, request, redirect, url_for, session
import sqlite3
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import os

# 🤖 Safe Gemini AI Client Setup
try:
    from google import genai
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")
    ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY != "YOUR_GEMINI_API_KEY_HERE" else None
except ImportError:
    ai_client = None
    print("⚠️ Warning: google-genai module not found. AI features will be disabled.")

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
        CREATE TABLE IF NOT EXISTS local_search_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            url TEXT,
            snippet TEXT,
            category TEXT
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
        .chrome-menu-item { display: flex; align-items: center; gap: 16px; padding: 12px 16px; font-size: 15px; color: #1f1f1f; text-decoration: none; border-radius: 12px; font-weight: 400; }
        .chrome-menu-item:hover { background: #f0f4f9; }
        .chrome-menu-item i { font-size: 18px; color: #444746; }
        .chrome-divider { height: 1px; background: #e0e4e9; margin: 8px 0; }
        
        .bharat-logo { font-size: 52px; font-weight: 700; letter-spacing: -1.5px; margin-top: 20px; }
        
        .google-search-container { max-width: 580px; width: 92%; margin: 24px auto 16px auto; position: relative; }
        .google-input { height: 54px; border-radius: 27px; padding-left: 52px; padding-right: 52px; border: 1px solid #dfe1e5; background: #ffffff; box-shadow: 0 1px 6px rgba(32,33,36,0.12); font-size: 16px; }
        .google-input:focus { outline: none; border-color: #4285f4; box-shadow: 0 2px 8px rgba(32,33,36,0.2); }
        .search-left-icon { position: absolute; left: 18px; top: 17px; color: #9aa0a6; font-size: 18px; }
        .mic-btn { position: absolute; right: 18px; top: 15px; background: none; border: none; color: #4285f4; font-size: 20px; cursor: pointer; }

        .search-filters { display: flex; gap: 8px; overflow-x: auto; padding-bottom: 8px; border-bottom: 1px solid #e0e0e0; margin-bottom: 16px; }
        .filter-chip { padding: 6px 16px; border-radius: 20px; background: #f1f3f4; color: #3c4043; text-decoration: none; font-size: 14px; white-space: nowrap; font-weight: 500; }
        .filter-chip.active { background: #e8f0fe; color: #1967d2; border: 1px solid #d2e3fc; }

        .bottom-nav-bar { position: fixed; bottom: 0; left: 0; right: 0; background: #ffffff; border-top: 1px solid #dadce0; display: flex; justify-content: space-around; padding: 8px 0; z-index: 9999; }
        .nav-link-item { text-decoration: none; color: #5f6368; font-size: 11px; text-align: center; display: flex; flex-direction: column; align-items: center; flex: 1; }
        .nav-link-item i { font-size: 20px; margin-bottom: 2px; }
        .nav-link-item.active { color: #1a73e8; font-weight: 600; }

        .results-wrapper { max-width: 680px; margin: 0 auto; padding: 0 16px; }
        .result-card { background: #fff; border-radius: 12px; padding: 16px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); border: 1px solid #f1f3f4; }
        .ai-card { background: #f0f4f9; border-radius: 16px; padding: 20px; margin-bottom: 20px; border: 1px solid #d3e3fd; }
        .result-title { color: #1a0dab; font-size: 18px; text-decoration: none; font-weight: 400; }
        .result-url { color: #202124; font-size: 12px; margin-bottom: 4px; }
        .result-snippet { color: #4d5156; font-size: 14px; line-height: 1.5; }
    </style>
</head>
<body>
"""

def get_footer(active_tab='home'):
    return f"""
<div class="bottom-nav-bar" id="bottomNav">
    <a href="/" class="nav-link-item {'active' if active_tab == 'home' else ''}"><i class="bi bi-house-door-fill"></i>Home</a>
    <a href="/games" class="nav-link-item {'active' if active_tab == 'games' else ''}"><i class="bi bi-controller"></i>Games</a>
    <a href="/my_history" class="nav-link-item {'active' if active_tab == 'history' else ''}"><i class="bi bi-clock-history"></i>History</a>
    <a href="/user_login" class="nav-link-item {'active' if active_tab == 'account' else ''}"><i class="bi bi-person-circle"></i>Account</a>
</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
function startVoiceSearch() {{
    const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
    recognition.lang = 'hi-IN';
    recognition.onresult = function(event) {{
        document.getElementById('searchInput').value = event.results[0][0].transcript;
        document.getElementById('searchForm').submit();
    }};
    recognition.start();
}}
</script>
</body>
</html>
"""

@app.route("/")
def home():
    user_logged = session.get('user_logged')
    owner_logged = session.get('owner_logged')
    username = session.get('username', '')

    user_info = f'<div class="px-3 py-2 mb-2 text-primary bg-light rounded-3 small">👤 <b>{username}</b></div>' if user_logged else ''
    login_logout = '<a href="/confirm_logout?type=user" class="chrome-menu-item text-danger"><i class="bi bi-box-arrow-right"></i>Logout</a>' if user_logged else '<a href="/user_login" class="chrome-menu-item"><i class="bi bi-box-arrow-in-right"></i>User Login</a>'
    
    role_options = ''
    if owner_logged:
        role_options += '<a href="/owner_dashboard" class="chrome-menu-item text-warning"><i class="bi bi-crown-fill"></i> Owner Dashboard</a>'
        role_options += '<a href="/confirm_logout?type=owner" class="chrome-menu-item text-danger"><i class="bi bi-box-arrow-left"></i> Owner Logout</a>'
    else:
        if not user_logged:
            role_options += '<a href="/owner_login" class="chrome-menu-item"><i class="bi bi-shield-lock-fill"></i> Owner Login</a>'

    top_bar = f"""
    <div class="top-bar-chrome">
        <div class="creator-badge">🚀 Created by <b>Aman Giri</b></div>
        <button class="dots-btn" type="button" data-bs-toggle="offcanvas" data-bs-target="#chromeMenu">
            <i class="bi bi-three-dots-vertical"></i>
        </button>
    </div>
    <div class="offcanvas offcanvas-end chrome-menu p-2" tabindex="-1" id="chromeMenu">
        <div class="offcanvas-body p-2">
            {user_info}
            <a href="/" class="chrome-menu-item"><i class="bi bi-plus-square"></i> New tab</a>
            <a href="/games" class="chrome-menu-item"><i class="bi bi-controller"></i> Play Snake Game</a>
            <a href="/my_history" class="chrome-menu-item"><i class="bi bi-clock-history"></i> History</a>
            <div class="chrome-divider"></div>
            {login_logout}
            {role_options}
        </div>
    </div>
    """

    return HTML_HEADER + top_bar + f"""
    <div class="container text-center">
        <div class="bharat-logo mb-1">
            <span style="color:#FF9933">B</span><span style="color:#FF9933">h</span><span style="color:#000080">a</span><span style="color:#138808">r</span><span style="color:#138808">a</span><span style="color:#138808">t</span>
        </div>
        <p class="text-muted small mb-3">India's Instant Category & Voice Search Engine 🇮🇳</p>

        <form action="/search" method="GET" id="searchForm" class="google-search-container">
            <i class="bi bi-search search-left-icon"></i>
            <input type="text" name="q" id="searchInput" class="form-control google-input" placeholder="Search Web, Apps, Games, Books..." required autocomplete="off">
            <button type="button" onclick="startVoiceSearch()" class="mic-btn" title="Search by Voice"><i class="bi bi-mic-fill"></i></button>
        </form>
    </div>
    """ + get_footer('home')

@app.route("/search")
def search():
    query = request.args.get('q', '').strip()
    category = request.args.get('cat', 'all').strip().lower()
    
    if not query:
        return redirect("/")

    if not is_safe_query(query):
        return HTML_HEADER + f"""
        <div class="results-wrapper pt-5 text-center">
            <div class="alert alert-danger p-4 shadow-sm">
                <h5>🚫 Safe Search Active</h5>
                <p class="small">Aapki search query Bharat Safety Policy ke khilaf hai.</p>
                <a href="/" class="btn btn-primary btn-sm mt-3">Back to Home</a>
            </div>
        </div>
        """ + get_footer('search')

    if session.get('user_logged'):
        current_user = session.get('username')
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO search_history (username, query, timestamp) VALUES (?, ?, ?)", (current_user, query, current_time))
        conn.commit()
        conn.close()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if category == 'all':
        cursor.execute("SELECT title, url, snippet, category FROM local_search_index WHERE title LIKE ? OR snippet LIKE ?", (f'%{query}%', f'%{query}%'))
    else:
        cursor.execute("SELECT title, url, snippet, category FROM local_search_index WHERE category = ? AND (title LIKE ? OR snippet LIKE ?)", (category, f'%{query}%', f'%{query}%'))
    rows = cursor.fetchall()
    conn.close()

    ai_response_html = ""
    if ai_client and category in ['all', 'web']:
        try:
            ai_prompt = f"Provide a crisp, clear overview for: '{query}'"
            response = ai_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=ai_prompt,
            )
            ai_text = response.text if response and response.text else ""
            if ai_text:
                ai_response_html = f"""
                <div class="ai-card shadow-sm">
                    <h6 class="text-primary fw-bold mb-2"><i class="bi bi-stars"></i> Bharat AI Overview</h6>
                    <p class="mb-0 text-dark small" style="line-height: 1.6;">{ai_text}</p>
                </div>
                """
        except Exception:
            pass

    chips = f"""
    <div class="search-filters">
        <a href="/search?q={query}&cat=all" class="filter-chip {'active' if category == 'all' else ''}"><i class="bi bi-search"></i> All</a>
        <a href="/search?q={query}&cat=web" class="filter-chip {'active' if category == 'web' else ''}"><i class="bi bi-globe"></i> Web</a>
        <a href="/search?q={query}&cat=apps" class="filter-chip {'active' if category == 'apps' else ''}"><i class="bi bi-phone"></i> Apps</a>
        <a href="/search?q={query}&cat=games" class="filter-chip {'active' if category == 'games' else ''}"><i class="bi bi-controller"></i> Games</a>
        <a href="/search?q={query}&cat=books" class="filter-chip {'active' if category == 'books' else ''}"><i class="bi bi-book"></i> Books</a>
    </div>
    """

    header_search = f"""
    <div class="bg-white border-bottom p-3 mb-3">
        <div class="d-flex align-items-center gap-2">
            <a href="/" class="bharat-logo text-decoration-none my-0 me-2" style="font-size: 26px;">
                <span style="color:#FF9933">B</span><span style="color:#000080">h</span><span style="color:#138808">at</span>
            </a>
            <form action="/search" method="GET" class="google-search-container my-0 flex-grow-1" style="max-width: 100%;">
                <input type="hidden" name="cat" value="{category}">
                <i class="bi bi-search search-left-icon" style="top:12px;"></i>
                <input type="text" name="q" id="searchInput" value="{query}" class="form-control google-input" style="height: 42px; font-size: 14px;">
                <button type="button" onclick="startVoiceSearch()" class="mic-btn" style="top:8px;" title="Search by Voice"><i class="bi bi-mic-fill"></i></button>
            </form>
        </div>
    </div>
    <div class="results-wrapper">
        {chips}
        {ai_response_html}
    """

    body_results = ""
    if rows:
        for row in rows:
            title, url, snippet, cat = row[0], row[1], row[2], row[3].upper()
            body_results += f"""
            <div class="result-card">
                <div class="d-flex justify-content-between align-items-center">
                    <div class="result-url">{url}</div>
                    <span class="badge bg-secondary" style="font-size: 10px;">{cat}</span>
                </div>
                <a href="{url}" target="_blank" class="result-title">{title}</a>
                <div class="result-snippet mt-1">{snippet}</div>
            </div>
            """
    else:
        body_results += f"""
        <div class="text-center text-muted p-5 bg-light rounded-4 border">
            <h5>No instant records found for "{query}" in [{category.upper()}].</h5>
            <p class="small text-muted">Owner Dashboard me jaakar is topic ka content add karein!</p>
        </div>
        """

    body_results += "</div>"
    return HTML_HEADER + header_search + body_results + get_footer('search')

# 🐍 Built-in Snake Game Route
@app.route("/games")
def games():
    return HTML_HEADER + """
    <div class="container text-center mt-4">
        <h3 class="mb-3">🎮 Bharat Arcade: Snake Game Pro</h3>
        <div class="bg-white p-3 rounded-4 shadow-sm d-inline-block border">
            <canvas id="snakeCanvas" width="300" height="300" style="background:#111; border-radius:10px;"></canvas>
            <div class="mt-2 text-muted small">Use Arrow keys on keyboard to play</div>
        </div>
        <div class="mt-3">
            <a href="/" class="btn btn-outline-primary btn-sm" style="border-radius: 20px;">Back to Home</a>
        </div>
    </div>
    <script>
        const canvas = document.getElementById("snakeCanvas");
        const ctx = canvas.getContext("2d");
        let box = 20;
        let snake = [{x: 9 * box, y: 10 * box}];
        let food = {x: Math.floor(Math.random() * 15) * box, y: Math.floor(Math.random() * 15) * box};
        let score = 0;
        let d = "RIGHT";

        document.addEventListener("keydown", direction);
        function direction(event) {
            if(event.keyCode == 37 && d != "RIGHT") d = "LEFT";
            else if(event.keyCode == 38 && d != "DOWN") d = "UP";
            else if(event.keyCode == 39 && d != "LEFT") d = "RIGHT";
            else if(event.keyCode == 40 && d != "UP") d = "DOWN";
        }

        function draw() {
            ctx.fillStyle = "#111";
            ctx.fillRect(0, 0, 300, 300);

            for(let i = 0; i < snake.length; i++) {
                ctx.fillStyle = (i == 0) ? "#138808" : "#FF9933";
                ctx.fillRect(snake[i].x, snake[i].y, box, box);
            }

            ctx.fillStyle = "red";
            ctx.fillRect(food.x, food.y, box, box);

            let snakeX = snake[0].x;
            let snakeY = snake[0].y;

            if(d == "LEFT") snakeX -= box;
            if(d == "UP") snakeY -= box;
            if(d == "RIGHT") snakeX += box;
            if(d == "DOWN") snakeY += box;

            if(snakeX == food.x && snakeY == food.y) {
                score++;
                food = {x: Math.floor(Math.random() * 15) * box, y: Math.floor(Math.random() * 15) * box};
            } else {
                snake.pop();
            }

            let newHead = {x: snakeX, y: snakeY};

            if(snakeX < 0 || snakeX >= 300 || snakeY < 0 || snakeY >= 300 || collision(newHead, snake)) {
                clearInterval(game);
                alert("Game Over! Score: " + score);
                location.reload();
            }

            snake.unshift(newHead);
        }

        function collision(head, array) {
            for(let i = 0; i < array.length; i++) {
                if(head.x == array[i].x && head.y == array[i].y) return true;
            }
            return false;
        }

        let game = setInterval(draw, 100);
    </script>
    """ + get_footer('games')

@app.route("/my_history")
def my_history():
    if not session.get('user_logged'):
        return redirect("/user_login")
    
    current_user = session.get('username')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT query, timestamp FROM search_history WHERE username = ? ORDER BY id DESC", (current_user,))
    history_list = cursor.fetchall()
    conn.close()

    history_rows = ""
    for h in history_list:
        history_rows += f"""
        <li class="list-group-item d-flex justify-content-between align-items-center">
            <span>🔍 <b>{h[0]}</b></span>
            <span class="text-muted small">{h[1]}</span>
        </li>
        """

    return HTML_HEADER + f"""
    <div class="container mt-4 mb-5" style="max-width: 600px;">
        <div class="bg-white p-4 rounded-4 shadow-sm border">
            <h4 class="mb-3 text-center">📜 Search History ({current_user})</h4>
            <ul class="list-group list-group-flush mb-3">
                {history_rows if history_rows else '<li class="list-group-item text-center text-muted">No search history found.</li>'}
            </ul>
            <div class="text-center">
                <a href="/" class="btn btn-outline-primary btn-sm" style="border-radius: 20px;">Back to Home</a>
            </div>
        </div>
    </div>
    """ + get_footer('history')

@app.route("/confirm_logout", methods=['GET', 'POST'])
def confirm_logout():
    account_type = request.args.get('type', 'user')
    error = ""
    if request.method == 'POST':
        entered_password = request.form.get('password')
        if account_type == 'owner' and entered_password == OWNER_PASSWORD:
            session.pop('owner_logged', None)
            return redirect("/")
        elif account_type == 'user':
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
        error = "Incorrect Password!"

    return HTML_HEADER + f"""
    <div class="container mt-5" style="max-width: 400px;">
        <form method="POST" class="bg-white p-4 rounded-4 shadow-sm border">
            <h4 class="mb-3 text-center text-danger">🔒 Security Check</h4>
            {f'<div class="alert alert-danger small">{error}</div>' if error else ''}
            <input type="password" name="password" class="form-control mb-3" placeholder="Enter Password to Logout" required>
            <button type="submit" class="btn btn-danger w-100 mb-2" style="border-radius: 20px;">Confirm Logout</button>
            <a href="/" class="btn btn-light w-100" style="border-radius: 20px;">Cancel</a>
        </form>
    </div>
    """ + get_footer('home')

@app.route("/owner_login", methods=['GET', 'POST'])
def owner_login():
    error = ""
    if request.method == 'POST':
        if request.form.get('username') == OWNER_USERNAME and request.form.get('password') == OWNER_PASSWORD:
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
            <input type="text" name="username" class="form-control mb-3" placeholder="Username" required>
            <input type="password" name="password" class="form-control mb-3" placeholder="Password" required>
            <button type="submit" class="btn btn-warning w-100 fw-bold" style="border-radius: 20px;">Login</button>
        </form>
    </div>
    """ + get_footer('home')

@app.route("/owner_dashboard", methods=['GET', 'POST'])
def owner_dashboard():
    if not session.get('owner_logged'):
        return redirect("/owner_login")
    
    message = ""
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        if form_type == 'add_index':
            title = request.form.get('title', '').strip()
            url = request.form.get('url', '').strip()
            snippet = request.form.get('snippet', '').strip()
            category = request.form.get('category', 'web').strip()
            
            if title and url:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("INSERT INTO local_search_index (title, url, snippet, category) VALUES (?, ?, ?, ?)", (title, url, snippet, category))
                conn.commit()
                conn.close()
                message = f"✅ Added to [{category.upper()}] successfully!"
        elif form_type == 'add_user':
            new_user = request.form.get('username', '').strip()
            new_pass = request.form.get('password', '').strip()
            new_role = request.form.get('role', 'user')
            if new_user and new_pass:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                try:
                    cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (new_user, new_pass, new_role))
                    conn.commit()
                    message = f"✅ Added user: {new_user}"
                except sqlite3.IntegrityError:
                    message = "⚠️ Username already exists!"
                conn.close()

    return HTML_HEADER + f"""
    <div class="container mt-4 mb-5" style="max-width: 750px;">
        <div class="bg-white p-4 rounded-4 shadow-sm border">
            <h4 class="mb-3 text-center">👑 Owner Control Center</h4>
            {f'<div class="alert alert-info">{message}</div>' if message else ''}
            
            <form method="POST" class="border p-3 rounded-3 mb-4 bg-light">
                <input type="hidden" name="form_type" value="add_index">
                <h6 class="text-primary mb-3">⚡ Add Instant Result (Web, Apps, Games, Books)</h6>
                <div class="row g-2">
                    <div class="col-md-6"><input type="text" name="title" class="form-control mb-2" placeholder="Title (e.g. Free Fire)" required></div>
                    <div class="col-md-6"><input type="url" name="url" class="form-control mb-2" placeholder="URL (https://...)" required></div>
                    <div class="col-md-8"><input type="text" name="snippet" class="form-control mb-2" placeholder="Short description..." required></div>
                    <div class="col-md-4">
                        <select name="category" class="form-select mb-2">
                            <option value="web">Web</option>
                            <option value="apps">Apps</option>
                            <option value="games">Games</option>
                            <option value="books">Books</option>
                        </select>
                    </div>
                </div>
                <button type="submit" class="btn btn-primary w-100 mt-2">Add to Instant Database</button>
            </form>

            <form method="POST" class="row g-2 border p-3 rounded-3 mb-4">
                <input type="hidden" name="form_type" value="add_user">
                <h6 class="text-success mb-2">➕ Add New User</h6>
                <div class="col-md-4"><input type="text" name="username" class="form-control" placeholder="Username" required></div>
                <div class="col-md-4"><input type="text" name="password" class="form-control" placeholder="Password" required></div>
                <div class="col-md-2"><select name="role" class="form-select"><option value="user">User</option><option value="admin">Admin</option></select></div>
                <div class="col-md-2"><button type="submit" class="btn btn-success w-100">Add</button></div>
            </form>

            <div class="text-center">
                <a href="/" class="btn btn-outline-secondary btn-sm" style="border-radius: 20px;">Back to Home</a>
            </div>
        </div>
    </div>
    """ + get_footer('home')

@app.route("/user_login", methods=['GET', 'POST'])
def user_login():
    if session.get('user_logged'):
        return redirect("/")
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
            return redirect("/")
        else:
            error = "Invalid Credentials!"
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
