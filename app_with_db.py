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
# 🗄️ DATABASE & CRAWLER INITIALIZATION
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
    master_apps = [
        ("Bharat Chat AI", "/chats", "WhatsApp style secure chat & calls", "Apps", "💬"),
        ("SBI Net Banking", "https://sbi.co.in/", "Official banking & loan portal", "Apps", "🏧"),
        ("Piramal Finance", "https://www.piramalfinance.com/", "Personal & home loans easily", "Apps", "🏦"),
        ("Research Workspace", "/research", "Academic Research & Summarizer", "Apps", "📚"),
        ("JPG to PDF Tool", "/converters", "Fast offline document converter", "Apps", "📄")
    ]

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        for title, url, snippet, category, logo in master_apps:
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

@app.route("/api/suggestions")
def suggestions():
    q = request.args.get("q", "").strip()
    if not q: return jsonify([])
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        search_kw = f"%{q}%"
        cursor.execute("SELECT DISTINCT title FROM local_search_index WHERE title LIKE ? LIMIT 6", (search_kw,))
        results = [r[0] for r in cursor.fetchall()]
        conn.close()
        return jsonify(results)
    except Exception:
        return jsonify([])

def fetch_unlimited_news(category="top"):
    news_items = []
    rss_url = "https://news.google.com/rss?hl=hi&gl=IN&ceid=IN:hi"
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
    badge_label = "👑 OWNER (Aman Giri)" if is_owner else "🟢 USER"
    badge_cls = "bg-danger" if is_owner else "bg-secondary"
    tabs_bar = get_chrome_tabs_html()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Bharat OS | Universal SuperApp Engine</title>
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
            padding-bottom: 95px !important; 
        }}
        .sticky-top-header {{ position: sticky; top: 0; z-index: 9999; background-color: var(--bg-color); box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
        .top-bar-chrome {{ display: flex; justify-content: space-between; align-items: center; padding: 10px 16px; background-color: var(--bg-color); }}
        .icon-btn {{ background: none; border: none; font-size: 22px; color: #d96b00; cursor: pointer; text-decoration: none; padding: 4px; }}
        
        .google-search-container {{ max-width: 620px; width: 92%; margin: 15px auto; position: relative; }}
        .google-input {{ height: 54px; border-radius: 27px; padding-left: 48px; padding-right: 90px; border: 2px solid #ffaa44; background: var(--card-bg); color: var(--text-color); box-shadow: 0 4px 12px rgba(255, 153, 51, 0.2); font-size: 15px; }}
        .search-left-icon {{ position: absolute; left: 18px; top: 18px; color: #e67300; font-size: 18px; z-index: 10; }}
        
        .suggestions-box {{ position: absolute; top: 58px; left: 0; right: 0; background: #fff; border-radius: 16px; box-shadow: 0 8px 24px rgba(0,0,0,0.15); border: 1px solid #ffe0b2; z-index: 9999; display: none; text-align: left; overflow: hidden; }}
        .suggestion-item {{ padding: 12px 20px; cursor: pointer; font-size: 14px; border-bottom: 1px solid #fff3e0; display: flex; align-items: center; gap: 10px; color: #333; }}
        .suggestion-item:hover {{ background-color: #fff3e0; color: #d96b00; }}

        .bottom-nav-bar {{ 
            position: fixed; 
            bottom: 0; 
            left: 0; 
            right: 0; 
            background: var(--bg-color); 
            border-top: 1px solid var(--border-color); 
            display: flex; 
            justify-content: space-around; 
            padding: 8px 0; 
            z-index: 9998; 
            box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.08);
        }}
        .nav-link-item {{ text-decoration: none; color: #5f6368; font-size: 11px; text-align: center; flex: 1; }}
        .nav-link-item.active {{ color: #ff7700 !important; font-weight: 700; transform: translateY(-2px); }}
        
        .chat-container {{ height: calc(100vh - 230px); overflow-y: auto; padding: 15px; display: flex; flex-direction: column; background: #efeae2; border-radius: 12px; }}
        .msg {{ padding: 8px 12px; border-radius: 8px; margin-bottom: 6px; max-width: 75%; font-size: 14px; }}
        .msg-sent {{ align-self: flex-end; background: #d9fdd3; color: #000; }}
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
        <div class="d-flex align-items-center gap-2">
            <span class="fw-bold text-dark" style="font-size:14px;">🚀 Bharat OS</span>
            <span class="badge {badge_cls} rounded-pill" style="font-size:10px;">{badge_label}</span>
        </div>
        <div class="d-flex align-items-center gap-2">
            <a href="/app_store" class="icon-btn text-success" title="Play Store"><i class="bi bi-bag-check-fill"></i></a>
            <a href="/chats" class="icon-btn text-primary" title="Bharat Chat"><i class="bi bi-chat-dots-fill"></i></a>
            
            <div class="dropdown">
                <button class="icon-btn" type="button" data-bs-toggle="dropdown"><i class="bi bi-three-dots-vertical"></i></button>
                <div class="dropdown-menu dropdown-menu-end chrome-menu shadow-lg">
                    <div class="chrome-menu-header">
                        <a href="javascript:history.forward()" class="chrome-top-icon" title="Forward"><i class="bi bi-arrow-right"></i></a>
                        <a href="/bookmarks" class="chrome-top-icon" title="Bookmarks"><i class="bi bi-star"></i></a>
                        <a href="/converters" class="chrome-top-icon" title="Downloads"><i class="bi bi-download"></i></a>
                        <a href="javascript:location.reload()" class="chrome-top-icon" title="Reload"><i class="bi bi-arrow-clockwise"></i></a>
                    </div>
                    <a class="chrome-menu-item" href="/app_store"><i class="bi bi-bag-check-fill fs-5 text-success"></i> Bharat Play Store</a>
                    <a class="chrome-menu-item" href="/api/tab/new"><i class="bi bi-plus-square fs-5"></i> New tab</a>
                    <a class="chrome-menu-item" href="/api/tab/new?incognito=true"><i class="bi bi-incognito fs-5"></i> New Incognito tab</a>
                    <div class="chrome-menu-divider"></div>
                    <a class="chrome-menu-item" href="/my_history"><i class="bi bi-clock-history fs-5"></i> History</a>
                    <a class="chrome-menu-item" href="/bookmarks"><i class="bi bi-star-fill fs-5 text-warning"></i> Bookmarks</a>
                    <a class="chrome-menu-item" href="/converters"><i class="bi bi-file-earmark-pdf fs-5 text-primary"></i> Downloads / Tools</a>
                    <a class="chrome-menu-item" href="/clear_browsing_data"><i class="bi bi-trash fs-5 text-danger"></i> Clear browsing data</a>
                    <div class="chrome-menu-divider"></div>
                    <a class="chrome-menu-item text-danger fw-bold" href="/owner_login"><i class="bi bi-speedometer2 fs-5"></i> Owner Control Center</a>
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
        <span>Play Store</span>
    </a>
    <a href="/chats" class="nav-link-item {'active' if active_tab == 'chats' else ''}">
        <i class="bi bi-chat-dots-fill fs-5 d-block text-primary"></i>
        <span>Chats</span>
    </a>
    <a href="/owner_dashboard" class="nav-link-item {'active' if active_tab == 'owner' else ''}">
        <i class="bi bi-speedometer2 fs-5 d-block text-danger"></i>
        <span>Owner</span>
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
    <div class="container text-center pt-2">
        <div class="bharat-logo mb-1" style="font-size: 52px; font-weight: 700;">
            <span style="color:#FF9933">B</span><span style="color:#000080">h</span><span style="color:#138808">arat</span> 🛕
        </div>
        <p class="fw-medium small mb-2" style="color: #d95100;">Universal AI Search Engine 🇮🇳</p>

        <form action="/search" method="GET" id="searchForm" class="google-search-container">
            <i class="bi bi-search search-left-icon"></i>
            <input type="text" id="searchInput" name="q" class="form-control google-input" placeholder="कुछ भी टाइप करें (जैसे: इतिहास, विज्ञान, कोडिंग)..." autocomplete="off" required>
            <div id="suggestionsBox" class="suggestions-box"></div>
        </form>

        <div class="container my-3" style="max-width: 680px;">
            <div class="row g-2 text-start">
                <div class="col-6 col-md-3"><a href="/app_store" class="card p-2 text-decoration-none text-dark shadow-sm text-center rounded-3 bg-white"><div class="fs-4 text-success">🛍️</div><div class="fw-bold small" style="font-size:12px;">Play Store</div></a></div>
                <div class="col-6 col-md-3"><a href="/chats" class="card p-2 text-decoration-none text-dark shadow-sm text-center rounded-3 bg-white"><div class="fs-4 text-primary">💬</div><div class="fw-bold small" style="font-size:12px;">Bharat Chat</div></a></div>
                <div class="col-6 col-md-3"><a href="/research" class="card p-2 text-decoration-none text-dark shadow-sm text-center rounded-3 bg-white"><div class="fs-4 text-info">📚</div><div class="fw-bold small" style="font-size:12px;">Research</div></a></div>
                <div class="col-6 col-md-3"><a href="/owner_dashboard" class="card p-2 text-decoration-none text-dark shadow-sm text-center rounded-3 bg-white"><div class="fs-4 text-danger">👑</div><div class="fw-bold small" style="font-size:12px;">Owner Panel</div></a></div>
            </div>
        </div>

        <div class="container text-start mt-2 mb-5" style="max-width: 720px;">
            <h6 class="fw-bold text-muted mb-2"><i class="bi bi-newspaper text-warning me-2"></i>Discover Feed</h6>
            <div class="row">{news_html}</div>
        </div>
    </div>
    """ + get_footer("home")

# -------------------------------------------------------------
# 💎 UNIVERSAL SEARCH & AI ENGINE (ANY QUERY ANSWERED)
# -------------------------------------------------------------
@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    if not query or not is_safe_query(query): return redirect("/")

    if "tabs" in session:
        for t in session["tabs"]:
            if t["id"] == session.get("active_tab", 1):
                t["title"] = query
        session.modified = True

    username = session.get("username", "Guest")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO search_history (username, query, timestamp) VALUES (?, ?, ?)", (username, query, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
    except Exception: pass

    # 1. Local Database / Vector Engine Search
    engine_data = bharat_engine.process_super_search(query)
    kg_card = engine_data.get("knowledge_card")
    vector_results = engine_data.get("results", [])

    kg_html = ""
    if kg_card:
        kg_html = f"""
        <div class="card p-3 mb-4 rounded-4 shadow-sm border-warning bg-warning bg-opacity-10">
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
        <div class="card p-3 mb-3 border-0 shadow-sm rounded-4 bg-white">
            <div class="d-flex align-items-center gap-2 mb-2">
                <img src="{favicon}" width="22" height="22" class="rounded-circle border p-1">
                <div>
                    <div class="fw-bold text-dark" style="font-size: 12px; line-height: 1;">{domain.replace('www.', '')}</div>
                    <small class="text-muted" style="font-size: 10px;">{url[:45]}...</small>
                </div>
            </div>
            <h5 class="mb-1"><a href="{url}" class="text-primary text-decoration-none fw-bold" style="font-size:16px;">{title}</a></h5>
            <p class="text-secondary small mb-2" style="font-size: 13px; line-height: 1.5;">{snippet}</p>
            <span class="badge bg-light text-dark border">{category}</span>
        </div>
        """

    # 2. Universal AI Engine (Answers ANY question typed by user)
    ai_answer = ""
    if genai_client:
        models_to_try = ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-3.6-flash"]
        for m_name in models_to_try:
            try:
                response = genai_client.models.generate_content(
                    model=m_name,
                    contents=f"यूज़र ने सर्च किया है: '{query}'. इस विषय पर एक सटीक, विस्तृत और उपयोगी उत्तर हिंदी में दें।"
                )
                if response and response.text:
                    ai_answer = format_markdown_to_html(response.text)
                    break
            except Exception:
                continue

    if not ai_answer:
        ai_answer = f"<b>'{query}'</b> के संबंध में जानकारी प्राप्त की जा रही है।"

    return get_html_header() + f"""
    <div class="container mt-4 mb-5" style="max-width: 720px;">
        <div class="d-flex align-items-center justify-content-between mb-3">
            <h5 class="fw-bold text-dark mb-0">🔍 परिणाम: "{query}"</h5>
            <a href="/" class="btn btn-outline-warning btn-sm rounded-pill">नया सर्च करें</a>
        </div>

        {kg_html}

        <!-- UNIVERSAL AI ANSWER CARD (Answers anything typed) -->
        <div class="card p-4 rounded-4 shadow-sm border-0 bg-white mb-4" style="border-left: 4px solid #ff7700 !important;">
            <div class="d-flex align-items-center justify-content-between mb-2">
                <div class="d-flex align-items-center gap-2">
                    <span class="fs-4">🤖</span>
                    <h6 class="fw-bold text-primary mb-0">Bharat AI Universal Assistant</h6>
                </div>
                <span class="badge bg-success bg-opacity-10 text-success">Live Answer</span>
            </div>
            <hr class="my-2 text-muted">
            <div style="line-height: 1.7; font-size: 15px; color: #202124;">
                {ai_answer}
            </div>
        </div>

        <h6 class="fw-bold text-muted mb-3"><i class="bi bi-cpu me-2"></i>संबंधित लिंक्स और ऐप्स</h6>
        {local_html if local_html else '<div class="card p-4 text-center text-muted bg-white rounded-4">इस विषय पर कोई अतिरिक्त लोकल लिंक नहीं है, लेकिन ऊपर AI उत्तर उपलब्ध है।</div>'}
    </div>
    """ + get_footer("home")

# -------------------------------------------------------------
# 🛍️ BHARAT PLAY STORE
# -------------------------------------------------------------
@app.route("/app_store")
def app_store():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT title, url, snippet, logo_url FROM local_search_index WHERE category = 'Apps' OR category = 'AI Tools' OR category = 'Bank'")
    apps_data = cursor.fetchall()
    conn.close()

    apps_html = ""
    for app_item in apps_data:
        title, url, snippet, logo = app_item[0], app_item[1], app_item[2], app_item[3] or "📦"
        icon_display = f"<span class='fs-2'>{logo}</span>" if len(logo) <= 2 else f"<img src='{logo}' width='40' height='40' class='rounded-3'>"
        
        apps_html += f"""
        <div class="card p-3 mb-3 border-0 shadow-sm rounded-4 bg-white d-flex flex-row align-items-center gap-3">
            <div class="p-2 bg-light rounded-4 d-flex align-items-center justify-content-center" style="width:55px; height:55px;">{icon_display}</div>
            <div class="flex-grow-1">
                <h6 class="fw-bold mb-0 text-dark">{title}</h6>
                <small class="text-muted d-block" style="font-size:12px;">{snippet}</small>
                <small class="text-success fw-bold" style="font-size:10px;">★ 4.9 • Instant Verified App</small>
            </div>
            <a href="{url}" target="_blank" class="btn btn-success btn-sm rounded-pill px-3 fw-bold shadow-sm">
                <i class="bi bi-download me-1"></i> Open / Install
            </a>
        </div>
        """

    return get_html_header() + f"""
    <div class="container mt-3 mb-5" style="max-width: 650px;">
        <div class="text-center mb-4">
            <span class="badge bg-success px-3 py-1 rounded-pill fw-bold">🛍️ OFFICIAL BHARAT PLAY STORE</span>
            <h3 class="fw-bold mt-2">Daily Needs & Super Apps</h3>
        </div>
        {apps_html if apps_html else '<div class="card p-4 text-center text-muted bg-white rounded-4">कोई ऐप उपलब्ध नहीं है।</div>'}
    </div>
    """ + get_footer("apps")

# -------------------------------------------------------------
# 💬 BHARAT WHATSAPP CHAT
# -------------------------------------------------------------
CONTACTS_LIST = [
    {"id": "aman", "name": "Aman Giri (Owner)", "phone": "+919876543210", "status": "Online 🟢", "avatar": "👑"},
    {"id": "support", "name": "Bharat Support", "phone": "+919123456789", "status": "Available", "avatar": "📞"},
    {"id": "piramal", "name": "Piramal Loan Help", "phone": "+919988776655", "status": "Bank Support", "avatar": "🏦"}
]

@app.route("/chats")
def chats():
    return get_html_header() + f"""
    <div class="container mt-3 mb-5" style="max-width: 600px;">
        <div class="d-flex justify-content-between align-items-center bg-white p-3 rounded-4 shadow-sm mb-3">
            <h5 class="fw-bold mb-0 text-success"><i class="bi bi-whatsapp me-2"></i>Bharat WhatsApp</h5>
            <span class="badge bg-success px-2 py-1 rounded-pill">SIM & WhatsApp Link</span>
        </div>
        <div class="list-group shadow-sm rounded-4 overflow-hidden border-0">
            {''.join([f'''
            <a href="/chat_room/{c['id']}" class="list-group-item list-group-item-action d-flex align-items-center gap-3 py-3 border-0 border-bottom bg-white">
                <div class="fs-2 p-2 bg-light rounded-circle">{c['avatar']}</div>
                <div class="flex-grow-1">
                    <h6 class="fw-bold mb-0 text-dark">{c['name']}</h6>
                    <small class="text-muted">{c['phone']} • {c['status']}</small>
                </div>
                <i class="bi bi-chevron-right text-muted small"></i>
            </a>
            ''' for c in CONTACTS_LIST])}
        </div>
    </div>
    """ + get_footer("chats")

@app.route("/chat_room/<contact_id>", methods=["GET", "POST"])
def chat_room(contact_id):
    contact = next((c for c in CONTACTS_LIST if c["id"] == contact_id), CONTACTS_LIST[0])
    session_key = f"chat_{contact_id}"
    
    if session_key not in session:
        session[session_key] = [{"sender": "recv", "text": f"नमस्ते! मैं {contact['name']} हूँ।"}]

    if request.method == "POST":
        msg = request.form.get("message")
        if msg:
            session[session_key].append({"sender": "sent", "text": msg})
            session[session_key].append({"sender": "recv", "text": f"ऑटो-रिप्लाई [{contact['name']}]: संदेश मिल गया!"})
            session.modified = True
        return redirect(f"/chat_room/{contact_id}")

    msgs_html = "".join([f'<div class="msg msg-{m["sender"]}">{m["text"]}</div>' for m in session[session_key]])
    wa_link = f"https://wa.me/{contact['phone'].replace('+', '')}?text=Hello%20{quote_plus(contact['name'])}"
    tel_link = f"tel:{contact['phone']}"

    return get_html_header() + f"""
    <div class="container mt-2 mb-5" style="max-width: 600px;">
        <div class="d-flex align-items-center justify-content-between bg-white p-2 px-3 rounded-top-4 shadow-sm border-bottom">
            <div class="d-flex align-items-center gap-2">
                <a href="/chats" class="text-dark fs-5 me-1"><i class="bi bi-arrow-left"></i></a>
                <span class="fs-4">{contact['avatar']}</span>
                <div>
                    <h6 class="fw-bold mb-0 text-dark" style="font-size:14px;">{contact['name']}</h6>
                    <small class="text-success" style="font-size:10px;">{contact['phone']}</small>
                </div>
            </div>
            <div class="d-flex align-items-center gap-3">
                <a href="{tel_link}" class="text-success fs-5" title="Direct Phone Call"><i class="bi bi-telephone-fill"></i></a>
                <a href="{wa_link}" target="_blank" class="text-success fs-5" title="Open Real WhatsApp"><i class="bi bi-whatsapp"></i></a>
            </div>
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

# -------------------------------------------------------------
# 👑 OWNER LOGIN & CONTROL CENTER
# -------------------------------------------------------------
@app.route("/owner_login", methods=["GET", "POST"])
def owner_login():
    error = ""
    if request.method == "POST":
        u = request.form.get("username")
        p = request.form.get("password")
        if u == OWNER_USERNAME and p == OWNER_PASSWORD:
            session["owner_logged"] = True
            return redirect("/owner_dashboard")
        else:
            error = "गलत यूज़रनेम या पासवर्ड! (Aman Giri / @Aman2007)"

    return get_html_header() + f"""
    <div class="container mt-5" style="max-width: 400px;">
        <form method="POST" class="bg-white p-4 rounded-4 shadow-sm border">
            <h4 class="mb-3 text-center text-danger fw-bold">👑 Owner Login</h4>
            <p class="text-muted small text-center mb-3">Aman Giri के लिए सुरक्षित पोर्टल</p>
            {f'<div class="alert alert-danger py-1 small">{error}</div>' if error else ''}
            <input type="text" name="username" class="form-control mb-3" placeholder="Username (Aman Giri)" required>
            <input type="password" name="password" class="form-control mb-3" placeholder="Password (@Aman2007)" required>
            <button type="submit" class="btn btn-danger w-100 rounded-pill fw-bold">Login as Owner</button>
        </form>
    </div>
    """ + get_footer("home")

@app.route("/owner_dashboard", methods=["GET", "POST"])
def owner_dashboard():
    if not session.get("owner_logged"): 
        return redirect("/owner_login")

    message = ""
    if request.method == "POST":
        form_type = request.form.get("form_type")
        if form_type == "run_crawler":
            try:
                sync_db_to_vector_engine(DB_PATH)
                message = "🕷️ <b>Web Crawler Resync Complete!</b>"
            except Exception as e:
                message = f"⚠️ एरर: {str(e)}"
        elif form_type == "add_link":
            title, url, snippet, category, logo = request.form.get("title"), request.form.get("url"), request.form.get("snippet"), request.form.get("category", "Apps"), request.form.get("logo_url", "📱")
            if title and url:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO local_search_index (title, url, snippet, category, logo_url) VALUES (?, ?, ?, ?, ?)", (title, url, snippet, category, logo))
                conn.commit()
                conn.close()
                bharat_engine.index_item(title, url, snippet, category)
                message = f"✅ नया ऐप/लिंक Bharat Play Store में जोड़ा गया: {title}"

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users_count = cursor.fetchone()[0]
    cursor.execute("SELECT id, username, tier FROM users ORDER BY id DESC")
    all_users_list = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) FROM local_search_index")
    total_indexed_count = cursor.fetchone()[0]
    conn.close()

    users_table_rows = "".join([f"<tr><td>#{u[0]}</td><td><b>{u[1]}</b></td><td><span class='badge bg-secondary'>{u[2] or 'Free'}</span></td></tr>" for u in all_users_list]) if all_users_list else "<tr><td colspan='3' class='text-center text-muted'>कोई यूज़र नहीं है।</td></tr>"

    return get_html_header() + f"""
    <div class="container mt-4 mb-5" style="max-width: 800px;">
        <div class="bg-white p-4 rounded-4 shadow-sm border mb-4">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h4 class="fw-bold text-danger mb-0"><i class="bi bi-speedometer2 me-2"></i>Owner Control Center</h4>
                <a href="/logout" class="btn btn-outline-danger btn-sm rounded-pill">Logout (Aman Giri)</a>
            </div>
            {f'<div class="alert alert-success py-2 small mb-3">{message}</div>' if message else ''}
            
            <div class="card p-3 border-secondary bg-white mb-4 rounded-4">
                <h6 class="fw-bold text-dark mb-2"><i class="bi bi-bag-plus-fill text-success me-2"></i>Add App to Bharat Play Store</h6>
                <form method="POST">
                    <input type="hidden" name="form_type" value="add_link">
                    <input type="hidden" name="category" value="Apps">
                    <div class="row g-2 mb-2">
                        <div class="col-12 col-md-6"><input type="text" name="title" class="form-control form-control-sm" placeholder="App Name (e.g. YouTube)" required></div>
                        <div class="col-12 col-md-6"><input type="url" name="url" class="form-control form-control-sm" placeholder="App URL (https://...)" required></div>
                    </div>
                    <div class="row g-2 mb-3">
                        <div class="col-12 col-md-8"><input type="text" name="snippet" class="form-control form-control-sm" placeholder="Short Description" required></div>
                        <div class="col-12 col-md-4"><input type="text" name="logo_url" class="form-control form-control-sm" placeholder="Icon Emoji" value="📱" required></div>
                    </div>
                    <button type="submit" class="btn btn-success btn-sm rounded-pill fw-bold w-100">Publish App to Play Store</button>
                </form>
            </div>

            <div class="card p-3 border-warning bg-warning bg-opacity-10 mb-4 rounded-4">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <h6 class="fw-bold text-dark mb-0"><i class="bi bi-bug-fill text-warning me-2"></i>Bharat Web Crawler Engine</h6>
                        <small class="text-muted">इंडेक्स सिंक करें (कुल इंडेक्स: {total_indexed_count})</small>
                    </div>
                    <form method="POST" class="mb-0">
                        <input type="hidden" name="form_type" value="run_crawler">
                        <button type="submit" class="btn btn-warning btn-sm rounded-pill fw-bold px-3">Run Crawler</button>
                    </form>
                </div>
            </div>
            
            <div class="card p-3 border-secondary bg-light rounded-4">
                <h6 class="fw-bold text-dark mb-2"><i class="bi bi-people-fill text-primary me-2"></i>Registered App Users ({total_users_count})</h6>
                <div class="table-responsive" style="max-height: 200px; overflow-y: auto;">
                    <table class="table table-sm table-hover align-middle small mb-0 bg-white rounded-3">
                        <thead class="table-dark"><tr><th>ID</th><th>Username</th><th>Tier</th></tr></thead>
                        <tbody>{users_table_rows}</tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
    """ + get_footer("owner")

# -------------------------------------------------------------
# 📌 HELPER PAGES
# -------------------------------------------------------------
@app.route("/bookmarks")
def bookmarks(): return get_html_header() + '<div class="container mt-4 text-center" style="max-width:600px;"><h5 class="fw-bold mb-3"><i class="bi bi-star-fill text-warning me-2"></i>Bookmarked Pages</h5><p class="text-muted">कोई बुकमार्क सेव नहीं है।</p></div>' + get_footer("home")

@app.route("/my_history")
def my_history(): return get_html_header() + '<div class="container mt-4 text-center" style="max-width:600px;"><h5 class="fw-bold mb-3"><i class="bi bi-clock-history me-2 text-warning"></i>Search History</h5><p class="text-muted">हिस्ट्री खाली है।</p></div>' + get_footer("home")

@app.route("/converters")
def converters():
    return get_html_header() + """
    <div class="container mt-4 mb-5" style="max-width: 750px;">
        <div class="text-center mb-4">
            <span class="badge bg-warning text-dark px-3 py-2 rounded-pill fw-bold">🚀 FREE TOOLS</span>
            <h3 class="fw-bold mt-2">Bharat AI Master Toolkit Suite</h3>
        </div>
        <div class="card p-3 shadow-sm rounded-4 border bg-white">
            <h6 class="fw-bold text-primary"><i class="bi bi-file-earmark-pdf me-2"></i>JPG to PDF Converter</h6>
            <form action="/convert_jpg_to_pdf" method="POST" enctype="multipart/form-data" class="mt-2">
                <input type="file" name="image_file" accept="image/*" class="form-control form-control-sm mb-2" required>
                <button type="submit" class="btn btn-primary btn-sm w-100 rounded-pill fw-bold">Convert to PDF</button>
            </form>
        </div>
    </div>
    """ + get_footer("tools")

@app.route("/convert_jpg_to_pdf", methods=["POST"])
def convert_jpg_to_pdf():
    if not Image: return "Image library missing."
    file = request.files.get('image_file')
    if not file: return redirect("/converters")
    try:
        image = Image.open(file.stream)
        if image.mode != 'RGB': image = image.convert('RGB')
        pdf_bytes = io.BytesIO()
        image.save(pdf_bytes, format='PDF')
        pdf_bytes.seek(0)
        return send_file(pdf_bytes, mimetype='application/pdf', as_attachment=True, download_name='converted.pdf')
    except Exception as e: return str(e)

@app.route("/research")
def research(): return get_html_header() + '<div class="container mt-4 text-center" style="max-width:600px;"><h4 class="fw-bold">📚 Research Workspace</h4><p class="text-muted">Academic AI helper ready.</p></div>' + get_footer("research")

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
