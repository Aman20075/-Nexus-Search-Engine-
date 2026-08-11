import io
import os
import re
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from urllib.parse import quote_plus, urlparse

from bs4 import BeautifulSoup
from flask import Flask, jsonify, redirect, request, send_file, session, url_for

try:
    from PIL import Image
except ImportError:
    Image = None

import requests

# 🤖 GOOGLE GENAI SDK IMPORT
try:
    from google import genai
    genai_client = genai.Client()
except Exception as e:
    genai_client = None

# 🤖 ADVANCED SEARCH ENGINE & CRAWLER IMPORT
from engine import bharat_engine, sync_db_to_vector_engine

# -------------------------------------------------------------
# 🔑 CONFIGURATION & CONSTANTS
# -------------------------------------------------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")
YOUR_UPI_ID = os.environ.get("YOUR_UPI_ID", "giriji5626@okaxis")
YOUR_UPI_NAME = os.environ.get("YOUR_UPI_NAME", "Sandesh Giri")

app = Flask(__name__)
app.permanent_session_lifetime = 365 * 24 * 60 * 60
app.secret_key = os.environ.get("SECRET_KEY", "bharat_search_permanent_session_key_2026")

DB_PATH = os.environ.get("DB_PATH", "search_engine.db")
db_dir = os.path.dirname(DB_PATH)
if db_dir and not os.path.exists(db_dir):
    os.makedirs(db_dir)

OWNER_USERNAME = "Aman Giri"
OWNER_PASSWORD = "@Aman2007"

BLOCKED_KEYWORDS = ["porn", "xxx", "sex", "adult", "nsfw", "nude", "hot video"]

def is_safe_query(query):
    query_lower = query.lower()
    for word in BLOCKED_KEYWORDS:
        if word in query_lower:
            return False
    return True

def format_markdown_to_html(text):
    if not text: return ""
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    return text.replace('\n', '<br>')

# -------------------------------------------------------------
# 🗄️ DATABASE & VECTOR ENGINE INITIALIZATION
# -------------------------------------------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT DEFAULT 'user',
            tier TEXT DEFAULT 'Free',
            is_premium INTEGER DEFAULT 0,
            vip_expires_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            query TEXT,
            timestamp TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bookmarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            title TEXT,
            url TEXT,
            timestamp TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS local_search_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            url TEXT UNIQUE,
            snippet TEXT,
            category TEXT,
            logo_url TEXT
        )
    """)

    conn.commit()
    conn.close()
    auto_seed_master_data()
    sync_db_to_vector_engine(DB_PATH)

def auto_seed_master_data():
    master_links = [
        ("ChatGPT", "https://chatgpt.com/", "Official ChatGPT AI chatbot for writing, coding, and query resolution.", "AI Tools"),
        ("Google Gemini", "https://gemini.google.com/", "Google's official advanced multimodal AI assistant.", "AI Tools"),
        ("Piramal Finance", "https://www.piramalfinance.com/", "Official site for Piramal personal, home, and business loans.", "Loans/NBFC"),
        ("Aavas Financiers", "https://www.aavas.in/", "Official site for Aavas home loans and loan against property.", "Housing Finance"),
        ("State Bank of India (SBI)", "https://sbi.co.in/", "Official SBI Internet Banking and loan services portal.", "Bank"),
        ("Khan Academy", "https://www.khanacademy.org/", "Free online education courses, math, and science tutorials.", "Education")
    ]

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        for title, url, snippet, category in master_links:
            domain = urlparse(url).netloc
            logo = f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
            cursor.execute("""
                INSERT OR IGNORE INTO local_search_index (title, url, snippet, category, logo_url)
                VALUES (?, ?, ?, ?, ?)
            """, (title, url, snippet, category, logo))
        conn.commit()
        conn.close()
    except Exception:
        pass

init_db()

# -------------------------------------------------------------
# 🌐 CHROME MULTI-TAB CONTROLLER
# -------------------------------------------------------------
def get_chrome_tabs_html():
    if "tabs" not in session:
        session["tabs"] = [{"id": 1, "title": "New Tab", "query": "", "incognito": False}]
        session["active_tab"] = 1

    tabs_html = '<div class="d-flex align-items-center bg-dark text-white px-2 py-1 gap-1 overflow-auto no-scrollbar" style="font-size:12px;">'
    for t in session["tabs"]:
        is_active = (t["id"] == session.get("active_tab", 1))
        bg_cls = "bg-secondary text-white fw-bold" if is_active else "bg-black text-muted"
        icon = "🕶️" if t.get("incognito") else "🌐"
        tabs_html += f"""
        <div class="d-flex align-items-center rounded-top px-3 py-1 gap-2 {bg_cls}" style="cursor:pointer;" onclick="switchTab({t['id']})">
            <span>{icon} {t['title'][:12]}</span>
            {f'<span onclick="event.stopPropagation(); closeTab({t["id"]})" class="text-danger fw-bold ms-1">&times;</span>' if len(session["tabs"]) > 1 else ''}
        </div>
        """
    tabs_html += '<button class="btn btn-sm btn-outline-warning py-0 px-2 rounded-circle ms-1" onclick="addNewTab()">+</button></div>'
    return tabs_html

@app.route("/api/tab/new")
def api_new_tab():
    incognito = request.args.get("incognito", "false") == "true"
    if "tabs" not in session: session["tabs"] = []
    new_id = len(session["tabs"]) + 1
    title = "Incognito" if incognito else f"Tab {new_id}"
    session["tabs"].append({"id": new_id, "title": title, "query": "", "incognito": incognito})
    session["active_tab"] = new_id
    session.modified = True
    return redirect("/")

@app.route("/api/tab/switch/<int:tab_id>")
def api_switch_tab(tab_id):
    session["active_tab"] = tab_id
    session.modified = True
    return redirect("/")

@app.route("/api/tab/close/<int:tab_id>")
def api_close_tab(tab_id):
    if "tabs" in session and len(session["tabs"]) > 1:
        session["tabs"] = [t for t in session["tabs"] if t["id"] != tab_id]
        session["active_tab"] = session["tabs"][-1]["id"]
        session.modified = True
    return redirect("/")

# -------------------------------------------------------------
# 🔍 SUGGESTIONS & NEWS API
# -------------------------------------------------------------
@app.route("/api/suggestions")
def suggestions():
    q = request.args.get("q", "").strip()
    if not q: return jsonify([])
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        search_kw = f"%{q}%"
        cursor.execute("SELECT DISTINCT title FROM local_search_index WHERE title LIKE ? OR category LIKE ? LIMIT 6", (search_kw, search_kw))
        results = [r[0] for r in cursor.fetchall()]
        conn.close()
        return jsonify(results)
    except Exception:
        return jsonify([])

NEWS_CATEGORIES = {
    "top": "https://news.google.com/rss?hl=hi&gl=IN&ceid=IN:hi",
    "tech": "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=hi&gl=IN&ceid=IN:hi",
    "sports": "https://news.google.com/rss/headlines/section/topic/SPORTS?hl=hi&gl=IN&ceid=IN:hi"
}

def fetch_unlimited_news(category="top"):
    news_items = []
    rss_url = NEWS_CATEGORIES.get(category, NEWS_CATEGORIES["top"])
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(rss_url, headers=headers, timeout=5)
        if resp.status_code == 200:
            root = ET.fromstring(resp.content)
            for item in root.findall(".//item"):
                title = item.find("title").text if item.find("title") is not None else "Bharat Live News"
                link = item.find("link").text if item.find("link") is not None else "#"
                pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
                parsed = urlparse(link)
                news_items.append({
                    "title": title,
                    "link": link,
                    "date": pub_date[:16] if pub_date else "Live",
                    "image": f"https://www.google.com/s2/favicons?domain={parsed.netloc}&sz=128",
                    "source": parsed.netloc.replace("www.", "")
                })
    except Exception: pass
    return news_items

# -------------------------------------------------------------
# 🎨 HEADER & FOOTER ENGINE
# -------------------------------------------------------------
def get_html_header():
    is_owner = session.get("owner_logged", False)
    username = session.get("username", "Owner" if is_owner else "Guest User")
    tabs_bar = get_chrome_tabs_html()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Bharat OS | Advanced SuperApp Engine</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css">
    <style>
        :root {{ --bg-color: #fff9f2; --text-color: #202124; --card-bg: rgba(255, 255, 255, 0.95); --border-color: #f1d3b3; }}
        html {{ height: 100%; margin: 0; }}
        body {{ 
            min-height: 100%; 
            margin: 0; 
            background-color: var(--bg-color); 
            color: var(--text-color); 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            padding-bottom: 90px !important; 
        }}
        .sticky-top-header {{ position: sticky; top: 0; z-index: 9999; background-color: var(--bg-color); box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
        .top-bar-chrome {{ display: flex; justify-content: space-between; align-items: center; padding: 10px 16px; background-color: var(--bg-color); }}
        .icon-btn {{ background: none; border: none; font-size: 22px; color: #d96b00; cursor: pointer; text-decoration: none; padding: 4px; }}
        
        .google-search-container {{ max-width: 620px; width: 92%; margin: 15px auto; position: relative; }}
        .google-input {{ height: 50px; border-radius: 25px; padding-left: 45px; padding-right: 85px; border: 2px solid #ffaa44; font-size: 15px; background: #fff; }}
        .search-left-icon {{ position: absolute; left: 16px; top: 16px; color: #e67300; font-size: 18px; z-index: 10; }}
        .search-right-actions {{ position: absolute; right: 14px; top: 10px; display: flex; align-items: center; gap: 6px; z-index: 10; }}
        .search-action-btn {{ background: none; border: none; font-size: 20px; color: #e67300; cursor: pointer; padding: 4px; }}
        
        .suggestions-box {{ position: absolute; top: 55px; left: 0; right: 0; background: #fff; border-radius: 14px; box-shadow: 0 8px 20px rgba(0,0,0,0.15); border: 1px solid #ffe0b2; z-index: 9999; display: none; text-align: left; overflow: hidden; }}
        .suggestion-item {{ padding: 10px 18px; cursor: pointer; font-size: 14px; border-bottom: 1px solid #fff3e0; display: flex; align-items: center; gap: 10px; color: #333; }}
        .suggestion-item:hover {{ background-color: #fff3e0; color: #d96b00; }}

        .bottom-nav-bar {{ 
            position: fixed; 
            bottom: 0; 
            left: 0; 
            right: 0; 
            background: #ffffff; 
            border-top: 1px solid #ddd; 
            display: flex; 
            justify-content: space-around; 
            padding: 8px 0; 
            z-index: 9999; 
            box-shadow: 0 -4px 10px rgba(0, 0, 0, 0.05);
        }}
        .nav-link-item {{ text-decoration: none; color: #5f6368; font-size: 11px; text-align: center; flex: 1; }}
        .nav-link-item.active {{ color: #ff7700 !important; font-weight: 700; }}
        
        .chat-container {{ height: calc(100vh - 180px); overflow-y: auto; padding: 15px; display: flex; flex-direction: column; background: #e5ddd5; border-radius: 12px; }}
        .msg {{ padding: 10px 14px; border-radius: 8px; margin-bottom: 8px; max-width: 75%; font-size: 14px; }}
        .msg-sent {{ align-self: flex-end; background: #dcf8c6; color: #000; }}
        .msg-recv {{ align-self: flex-start; background: #ffffff; color: #000; }}

        .chrome-menu {{ width: 280px; border-radius: 20px; padding: 8px 0; border: none; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }}
        .chrome-menu-header {{ display: flex; justify-content: space-between; padding: 8px 16px; border-bottom: 1px solid #f0f0f0; margin-bottom: 6px; }}
        .chrome-top-icon {{ width: 36px; height: 36px; border-radius: 50%; background: #f1f3f4; display: flex; align-items: center; justify-content: center; color: #3c4043; text-decoration: none; font-size: 16px; }}
        .chrome-menu-item {{ padding: 10px 20px; font-size: 14px; color: #3c4043; display: flex; align-items: center; gap: 14px; text-decoration: none; font-weight: 500; }}
        .chrome-menu-item:hover {{ background-color: #f8f9fa; color: #000; }}
        .chrome-menu-divider {{ height: 1px; background: #e8eaed; margin: 6px 0; }}
    </style>
</head>
<body>

<div class="sticky-top-header">
    {tabs_bar}
    <div class="top-bar-chrome">
        <div class="fw-bold text-dark" style="font-size:15px;">🚀 Bharat OS</div>
        <div class="d-flex align-items-center gap-2">
            <a href="/app_store" class="icon-btn text-success" title="App Store"><i class="bi bi-bag-check-fill"></i></a>
            <a href="/research" class="icon-btn text-info" title="Research Workspace"><i class="bi bi-journal-bookmark-fill"></i></a>
            <a href="/chats" class="icon-btn text-primary" title="Bharat Chat"><i class="bi bi-chat-dots-fill"></i></a>
            
            <div class="dropdown">
                <button class="icon-btn" type="button" data-bs-toggle="dropdown"><i class="bi bi-three-dots-vertical"></i></button>
                <div class="dropdown-menu dropdown-menu-end chrome-menu shadow-lg">
                    <div class="chrome-menu-header">
                        <a href="javascript:history.forward()" class="chrome-top-icon"><i class="bi bi-arrow-right"></i></a>
                        <a href="/add_bookmark" class="chrome-top-icon"><i class="bi bi-star"></i></a>
                        <a href="/research" class="chrome-top-icon"><i class="bi bi-journal-check"></i></a>
                        <a href="javascript:location.reload()" class="chrome-top-icon"><i class="bi bi-arrow-clockwise"></i></a>
                    </div>
                    <a class="chrome-menu-item" href="/app_store"><i class="bi bi-bag-check-fill fs-5 text-success"></i> App Store</a>
                    <a class="chrome-menu-item" href="/research"><i class="bi bi-journal-bookmark fs-5 text-info"></i> Research Workspace</a>
                    <a class="chrome-menu-item" href="/api/tab/new"><i class="bi bi-plus-square fs-5"></i> New tab</a>
                    <a class="chrome-menu-item" href="/my_history"><i class="bi bi-clock-history fs-5"></i> History</a>
                    <a class="chrome-menu-item" href="/clear_browsing_data"><i class="bi bi-trash fs-5 text-danger"></i> Clear Data</a>
                </div>
            </div>

            {f'<a href="/owner_dashboard" class="icon-btn text-danger" title="Owner Panel"><i class="bi bi-speedometer2"></i></a>' if is_owner else ''}
        </div>
    </div>
</div>
"""

def get_footer(active_tab="home"):
    return f"""
<div class="bottom-nav-bar" id="bottomNavBar">
    <a href="/" class="nav-link-item {'active' if active_tab == 'home' else ''}">
        <i class="bi bi-house-door-fill fs-5 d-block"></i>
        <span>Home</span>
    </a>
    <a href="/app_store" class="nav-link-item {'active' if active_tab == 'apps' else ''}">
        <i class="bi bi-bag-check-fill fs-5 d-block text-success"></i>
        <span>Apps</span>
    </a>
    <a href="/research" class="nav-link-item {'active' if active_tab == 'research' else ''}">
        <i class="bi bi-journal-bookmark fs-5 d-block text-info"></i>
        <span>Research</span>
    </a>
    <a href="/chats" class="nav-link-item {'active' if active_tab == 'chats' else ''}">
        <i class="bi bi-chat-dots-fill fs-5 d-block text-primary"></i>
        <span>Chats</span>
    </a>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
    function addNewTab() {{ window.location.href = "/api/tab/new"; }}
    function switchTab(tabId) {{ window.location.href = "/api/tab/switch/" + tabId; }}
    function closeTab(tabId) {{ window.location.href = "/api/tab/close/" + tabId; }}

    const navBar = document.getElementById("bottomNavBar");
    if (window.visualViewport) {{
        window.visualViewport.addEventListener('resize', () => {{
            if (window.visualViewport.height < window.innerHeight - 150) {{
                if (navBar) navBar.style.display = "none";
            }} else {{
                if (navBar) navBar.style.display = "flex";
            }}
        }});
    }}

    const searchInput = document.getElementById("searchInput");
    const suggestionsBox = document.getElementById("suggestionsBox");
    const searchForm = document.getElementById("searchForm");

    if (searchInput) {{
        searchInput.addEventListener("input", async function() {{
            const query = this.value.trim();
            if (query.length < 1) {{ if(suggestionsBox) suggestionsBox.style.display = "none"; return; }}
            try {{
                const res = await fetch('/api/suggestions?q=' + encodeURIComponent(query));
                const data = await res.json();
                if (data.length > 0) {{
                    suggestionsBox.innerHTML = data.map(item => `
                        <div class="suggestion-item" onclick="selectAndSearch('${{item}}')">
                            <i class="bi bi-search text-muted"></i> 
                            <span>${{item}}</span>
                        </div>
                    `).join('');
                    suggestionsBox.style.display = "block";
                }} else {{
                    suggestionsBox.style.display = "none";
                }}
            }} catch(e) {{ if(suggestionsBox) suggestionsBox.style.display = "none"; }}
        }});

        document.addEventListener("click", function(e) {{
            if (e.target !== searchInput && suggestionsBox && !suggestionsBox.contains(e.target)) {{
                suggestionsBox.style.display = "none";
            }}
        }});
    }}

    function selectAndSearch(text) {{
        if (searchInput) searchInput.value = text;
        if (suggestionsBox) suggestionsBox.style.display = "none";
        if (searchForm) searchForm.submit();
    }}

    function startVoiceSearch() {{
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {{ alert("सपोर्ट नहीं है।"); return; }}
        const recognition = new SpeechRecognition();
        recognition.lang = 'hi-IN';
        recognition.onresult = function(event) {{
            if(searchInput) {{
                searchInput.value = event.results[0][0].transcript;
                if(searchForm) searchForm.submit();
            }}
        }};
        recognition.start();
    }}
</script>
</body>
</html>
"""

# -------------------------------------------------------------
# 🏠 HOME ROUTE
# -------------------------------------------------------------
@app.route("/")
def home():
    news_list = fetch_unlimited_news("top")
    news_html = "".join([f"""
    <div class="col-12 col-md-6 mb-2">
        <a href="{n['link']}" target="_blank" class="text-decoration-none text-dark">
            <div class="card p-2 border-0 shadow-sm rounded-3 bg-white d-flex flex-row align-items-center gap-2">
                <img src="{n['image']}" width="45" height="45" class="rounded-2" style="object-fit:cover;">
                <div class="flex-grow-1">
                    <h6 class="fw-bold mb-0" style="font-size:12px; line-height:1.3;">{n['title']}</h6>
                    <small class="text-muted" style="font-size:10px;">{n['source']}</small>
                </div>
            </div>
        </a>
    </div>
    """ for n in news_list[:4]])

    return get_html_header() + f"""
    <div class="container text-center pt-3" style="max-width: 650px;">
        <h1 class="fw-bold mb-1" style="color: #d95100; letter-spacing: -1px;">Bharat OS 🇮🇳</h1>
        <p class="text-muted small mb-3">Advanced SuperApp & In-App Search Engine</p>

        <form action="/search" method="GET" id="searchForm" class="google-search-container">
            <i class="bi bi-search search-left-icon"></i>
            <input type="text" id="searchInput" name="q" class="form-control google-input" placeholder="सर्च करें (जैसे: SBI, Piramal, ChatGPT)..." autocomplete="off" required>
            <div id="suggestionsBox" class="suggestions-box"></div>
        </form>

        <div class="row g-2 text-start mt-3">
            <div class="col-6 col-md-3"><a href="/app_store" class="card p-3 text-decoration-none text-dark shadow-sm text-center rounded-4 bg-white"><div class="fs-3 text-success">🛍️</div><div class="fw-bold small mt-1">App Store</div></a></div>
            <div class="col-6 col-md-3"><a href="/research" class="card p-3 text-decoration-none text-dark shadow-sm text-center rounded-4 bg-white"><div class="fs-3 text-info">📚</div><div class="fw-bold small mt-1">Research</div></a></div>
            <div class="col-6 col-md-3"><a href="/chats" class="card p-3 text-decoration-none text-dark shadow-sm text-center rounded-4 bg-white"><div class="fs-3 text-primary">💬</div><div class="fw-bold small mt-1">Chat AI</div></a></div>
            <div class="col-6 col-md-3"><a href="/search?q=State+Bank" class="card p-3 text-decoration-none text-dark shadow-sm text-center rounded-4 bg-white"><div class="fs-3 text-warning">🏧</div><div class="fw-bold small mt-1">SBI Bank</div></a></div>
        </div>

        <div class="text-start mt-4">
            <h6 class="fw-bold text-muted mb-2"><i class="bi bi-newspaper text-warning me-1"></i> Live Feed</h6>
            <div class="row">{news_html}</div>
        </div>
    </div>
    """ + get_footer("home")

# -------------------------------------------------------------
# 💎 ADVANCED SUPER-SEARCH ROUTE (WITH BHARAT ENGINE)
# -------------------------------------------------------------
@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    file_type = request.args.get("file_type", "all")
    mode = request.args.get("mode", "fast")

    if not query or not is_safe_query(query): return redirect("/")

    if "tabs" in session:
        for t in session["tabs"]:
            if t["id"] == session.get("active_tab", 1):
                t["title"] = query
        session.modified = True

    # Save Search History
    username = session.get("username", "Guest")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO search_history (username, query, timestamp) VALUES (?, ?, ?)", (username, query, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
    except Exception: pass

    engine_data = bharat_engine.process_super_search(query)
    intent_data = engine_data.get("intent", {})
    kg_card = engine_data.get("knowledge_card")
    vector_results = engine_data.get("results", [])

    kg_html = ""
    if kg_card:
        kg_html = f"""
        <div class="card p-3 mb-3 rounded-4 shadow-sm border-warning bg-warning bg-opacity-10">
            <span class="badge bg-warning text-dark align-self-start mb-2">🇮🇳 {kg_card['category']}</span>
            <h5 class="fw-bold text-dark">{kg_card['title']}</h5>
            <p class="small mb-1"><b>विभाग:</b> {kg_card['department']}</p>
            <p class="small mb-2"><b>लाभ:</b> {kg_card['benefits']}</p>
            <a href="{kg_card['official_website']}" class="btn btn-warning btn-sm rounded-pill fw-bold">पोर्टल पर जाएँ</a>
        </div>
        """

    local_html = ""
    for item in vector_results:
        title, url, snippet, category = item["title"], item["url"], item["snippet"], item["category"]
        domain = urlparse(url).netloc if url else 'bharat.app'
        favicon = f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
        local_html += f"""
        <div class="card p-3 mb-2 border-0 shadow-sm rounded-4 bg-white">
            <div class="d-flex align-items-center gap-2 mb-1">
                <img src="{favicon}" width="18" height="18" class="rounded">
                <small class="text-muted">{url[:45]}</small>
            </div>
            <h5 class="mb-1"><a href="{url}" class="text-primary fw-bold text-decoration-none">{title}</a></h5>
            <p class="text-muted small mb-0">{snippet}</p>
        </div>
        """

    ai_answer = ""
    if genai_client:
        try:
            response = genai_client.models.generate_content(model="gemini-2.5-flash", contents=f"Provide detailed summary for: {query}. उत्तर हिंदी में दें।")
            if response and response.text: ai_answer = format_markdown_to_html(response.text)
        except Exception: ai_answer = "खोज पूर्ण हुई।"

    return get_html_header() + f"""
    <div class="container mt-3 mb-5" style="max-width: 680px;">
        <div class="d-flex gap-2 mb-3">
            <span class="badge bg-warning text-dark">Category: {intent_data.get('category', 'General').upper()}</span>
        </div>
        {kg_html}
        {f'<div class="card p-3 rounded-4 shadow-sm border-0 bg-white mb-3 border-start border-4 border-warning"><b>Bharat AI Insight:</b> {ai_answer}</div>' if ai_answer else ''}
        <h6 class="fw-bold text-muted mb-2">Smart In-App Matches</h6>
        {local_html if local_html else '<div class="card p-4 text-center text-muted bg-white rounded-4">कोई सीधा परिणाम नहीं मिला।</div>'}
    </div>
    """ + get_footer("home")

# -------------------------------------------------------------
# 📚 RESEARCH WORKSPACE ROUTE
# -------------------------------------------------------------
@app.route("/research")
def research():
    return get_html_header() + """
    <div class="container mt-3 mb-5" style="max-width: 650px;">
        <h4 class="fw-bold text-dark mb-1">📚 Research Workspace</h4>
        <p class="text-muted small mb-3">Academic Research, Summarizer & Fact Checker</p>
        <div class="card p-4 border-0 shadow-sm rounded-4 bg-white text-center">
            <p class="text-muted">अपने रिसर्च टॉपिक या डॉक्यूमेंट का विषय यहाँ दर्ज करें:</p>
            <input type="text" class="form-control mb-3" placeholder="Research Topic...">
            <button class="btn btn-info text-white rounded-pill fw-bold px-4">Generate Report</button>
        </div>
    </div>
    """ + get_footer("research")

# -------------------------------------------------------------
# 🛍️ BHARAT APP STORE
# -------------------------------------------------------------
@app.route("/app_store")
def app_store():
    daily_apps = [
        {"name": "SBI Net Banking", "desc": "Official banking portal", "icon": "🏧", "url": "https://sbi.co.in/"},
        {"name": "Piramal Finance", "desc": "Personal & home loans", "icon": "🏦", "url": "https://www.piramalfinance.com/"},
        {"name": "Bharat Chat AI", "desc": "WhatsApp style chat", "icon": "💬", "url": "/chats"},
        {"name": "Research Workspace", "desc": "Academic helper", "icon": "📚", "url": "/research"}
    ]
    apps_html = "".join([f"""
    <div class="card p-3 mb-3 border-0 shadow-sm rounded-4 bg-white d-flex flex-row align-items-center gap-3">
        <div class="fs-1 p-2 bg-light rounded-4">{a['icon']}</div>
        <div class="flex-grow-1">
            <h6 class="fw-bold mb-0 text-dark">{a['name']}</h6>
            <small class="text-muted">{a['desc']}</small>
        </div>
        <a href="{a['url']}" class="btn btn-success btn-sm rounded-pill px-3 fw-bold">Open</a>
    </div>
    """ for a in daily_apps])

    return get_html_header() + f"""
    <div class="container mt-3 mb-5" style="max-width: 650px;">
        <h4 class="fw-bold text-dark mb-1">🛍️ Bharat App Store</h4>
        <p class="text-muted small mb-3">Verified Daily Needs Apps & Tools</p>
        {apps_html}
    </div>
    """ + get_footer("apps")

# -------------------------------------------------------------
# 💬 BHARAT CHAT
# -------------------------------------------------------------
@app.route("/chats", methods=["GET", "POST"])
def chats():
    if "messages" not in session:
        session["messages"] = [{"sender": "recv", "text": "नमस्ते! Bharat Chat में आपका स्वागत है।"}]

    if request.method == "POST":
        msg = request.form.get("message")
        if msg:
            session["messages"].append({"sender": "sent", "text": msg})
            session["messages"].append({"sender": "recv", "text": f"ऑटो-रिप्लाई: '{msg}' मिला!"})
            session.modified = True
        return redirect("/chats")

    msgs_html = "".join([f'<div class="msg msg-{m["sender"]}">{m["text"]}</div>' for m in session["messages"]])

    return get_html_header() + f"""
    <div class="container mt-2 mb-5" style="max-width: 600px;">
        <div class="d-flex align-items-center bg-white p-2 rounded-top-4 shadow-sm border-bottom">
            <span class="fs-4 me-2">💬</span>
            <h6 class="fw-bold mb-0 text-success">Bharat WhatsApp Chat</h6>
        </div>
        <div class="chat-container shadow-sm mb-2" id="chatBox">
            {msgs_html}
        </div>
        <form method="POST" class="input-group bg-white p-2 rounded-bottom-4 shadow-sm">
            <input type="text" name="message" class="form-control rounded-pill border-0 bg-light px-3" placeholder="संदेश टाइप करें..." autocomplete="off" required>
            <button type="submit" class="btn btn-success rounded-circle ms-2" style="width:40px; height:40px;"><i class="bi bi-send-fill"></i></button>
        </form>
    </div>
    <script>
        const chatBox = document.getElementById("chatBox");
        if(chatBox) chatBox.scrollTop = chatBox.scrollHeight;
    </script>
    """ + get_footer("chats")

@app.route("/owner_login", methods=["GET", "POST"])
def owner_login():
    if request.method == "POST":
        if request.form.get("username") == OWNER_USERNAME and request.form.get("password") == OWNER_PASSWORD:
            session["owner_logged"] = True
            return redirect("/owner_dashboard")
    return get_html_header() + """
    <div class="container mt-5" style="max-width: 400px;">
        <form method="POST" class="bg-white p-4 rounded-4 shadow-sm border">
            <h4 class="mb-3 text-center text-danger fw-bold">👑 Owner Login</h4>
            <input type="text" name="username" class="form-control mb-3" placeholder="Username" required>
            <input type="password" name="password" class="form-control mb-3" placeholder="Password" required>
            <button type="submit" class="btn btn-danger w-100 rounded-pill fw-bold">Login</button>
        </form>
    </div>
    """ + get_footer("home")

@app.route("/owner_dashboard")
def owner_dashboard():
    if not session.get("owner_logged"): return redirect("/owner_login")
    return get_html_header() + """
    <div class="container mt-4 text-center" style="max-width: 600px;">
        <h4 class="fw-bold text-danger">👑 Owner Control Center</h4>
        <p class="text-muted">सिस्टम और क्रॉलर पूरी तरह एक्टिव हैं।</p>
        <a href="/" class="btn btn-dark rounded-pill px-4">Home</a>
    </div>
    """ + get_footer("home")

@app.route("/add_bookmark")
def add_bookmark(): return redirect("/")
@app.route("/my_history")
def my_history(): return redirect("/")
@app.route("/clear_browsing_data")
def clear_data():
    session["tabs"] = [{"id": 1, "title": "New Tab", "query": "", "incognito": False}]
    session.modified = True
    return redirect("/")
@app.route("/logout")
def logout(): session.clear(); return redirect("/")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=True)
