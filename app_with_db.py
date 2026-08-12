import io
import os
import re
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import quote_plus, urlparse

from flask import Flask, jsonify, redirect, request, send_file, session, url_for

try:
    from PIL import Image
except ImportError:
    Image = None

import requests

# 🤖 GOOGLE GENAI SDK IMPORT (Gemini Multi-Model Fallback)
try:
    from google import genai
    genai_client = genai.Client()
except Exception as e:
    genai_client = None

# 🤖 ADVANCED SEARCH ENGINE IMPORT
from engine import bharat_engine, sync_db_to_vector_engine

# -------------------------------------------------------------
# 🔑 CONFIGURATION & CONSTANTS
# -------------------------------------------------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")
app = Flask(__name__)
app.permanent_session_lifetime = 365 * 24 * 60 * 60
app.secret_key = os.environ.get("SECRET_KEY", "bharat_search_permanent_session_key_2026")

DB_PATH = os.environ.get("DB_PATH", "search_engine.db")
db_dir = os.path.dirname(DB_PATH)
if db_dir and not os.path.exists(db_dir):
    os.makedirs(db_dir)

# 👑 OWNER & ADMIN CREDENTIALS
OWNER_USERNAME = "Aman Giri"
OWNER_PASSWORD = "@Aman2007"

BLOCKED_KEYWORDS = ["porn", "xxx", "sex", "adult", "nsfw", "nude", "hot video"]

# -------------------------------------------------------------
# 🤖 GEMINI MULTI-MODEL FALLBACK ENGINE WITH LIVE LINKING
# -------------------------------------------------------------
GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-3.6-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro"
]

def format_markdown_to_html(text):
    if not text: return ""
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    return text.replace('\n', '<br>')

def generate_gemini_smart_search(query):
    if not genai_client:
        return "<p class='text-muted'>AI सर्विस अभी उपलब्ध नहीं है।</p>"
    
    prompt = f"""
    यूज़र ने सर्च किया है: '{query}'
    1. अगर यह किसी सवाल का जवाब है, तो विस्तृत और सटीक उत्तर हिंदी में दें।
    2. अगर यह किसी ऐप, वेबसाइट या सर्विस (जैसे Banking, Video, Loan, AI Tools) के बारे में है, तो उत्तर के साथ-साथ उसकी ऑफिसियल वेबसाइट/ऐप का पूरा URL (लिंक) भी HTML <a> टैग के साथ दें ताकि यूज़र उसपर क्लिक कर सके।
    """

    for model_name in GEMINI_MODELS:
        try:
            response = genai_client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            if response and response.text:
                return format_markdown_to_html(response.text)
        except Exception:
            continue
            
    return "<p class='text-danger'>सभी AI मॉडल्स अभी व्यस्त हैं। कृपया थोड़ी देर बाद पुनः प्रयास करें।</p>"

def is_safe_query(query):
    query_lower = query.lower()
    for word in BLOCKED_KEYWORDS:
        if word in query_lower:
            return False
    return True

# -------------------------------------------------------------
# 🗄️ DATABASE & TABLES INITIALIZATION
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
            tier TEXT DEFAULT 'Free'
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

    # 📺 BHARAT STUDIO MULTI-CONTENT TABLE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bharat_videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            media_url TEXT,
            description TEXT,
            content_type TEXT DEFAULT 'shorts',
            uploader TEXT,
            timestamp TEXT
        )
    """)

    conn.commit()
    conn.close()
    auto_seed_master_data()
    sync_db_to_vector_engine(DB_PATH)

def auto_seed_master_data():
    master_apps = [
        ("Bharat Studio", "/studio", "Shorts, Videos, Podcasts, Posts & Live Streaming", "Studio", "📺"),
        ("Bharat AI Chat", "/ai_chat", "Multi-Model Gemini AI Assistant", "AI Tools", "🤖"),
        ("SBI Net Banking", "https://sbi.co.in/", "Official banking & loan portal", "Bank", "🏧"),
        ("Piramal Finance", "https://www.piramalfinance.com/", "Personal & home loans easily", "Loans", "🏦")
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

# -------------------------------------------------------------
# 🎨 HEADER & FOOTER ENGINE (ADMIN SECURED & KEYBOARD PROOF)
# -------------------------------------------------------------
def get_html_header():
    is_owner = session.get("owner_logged", False)
    owner_badge = '<span class="badge bg-danger rounded-pill ms-1" style="font-size:10px;">👑 ADMIN</span>' if is_owner else ''
    owner_menu_item = '<a class="chrome-menu-item text-danger fw-bold" href="/owner_dashboard"><i class="bi bi-speedometer2 fs-5"></i> Owner Dashboard</a>' if is_owner else ''
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
    </style>
</head>
<body>

<div class="sticky-top-header">
    {tabs_bar}
    <div class="top-bar-chrome">
        <div class="d-flex align-items-center gap-2">
            <span class="fw-bold text-dark" style="font-size:14px;">🚀 Bharat OS</span>
            {owner_badge}
        </div>
        <div class="d-flex align-items-center gap-2">
            <a href="/app_store" class="icon-btn text-success" title="Play Store"><i class="bi bi-bag-check-fill"></i></a>
            <a href="/studio" class="icon-btn text-danger" title="Bharat Studio"><i class="bi bi-youtube"></i></a>
            <a href="/ai_chat" class="icon-btn text-primary" title="Gemini AI Chat"><i class="bi bi-robot"></i></a>
            
            <div class="dropdown">
                <button class="icon-btn" type="button" data-bs-toggle="dropdown"><i class="bi bi-three-dots-vertical"></i></button>
                <div class="dropdown-menu dropdown-menu-end chrome-menu shadow-lg">
                    <a class="chrome-menu-item" href="/app_store"><i class="bi bi-bag-check-fill fs-5 text-success"></i> Bharat Play Store</a>
                    <a class="chrome-menu-item" href="/studio"><i class="bi bi-youtube fs-5 text-danger"></i> Bharat Studio (YouTube OS)</a>
                    <a class="chrome-menu-item" href="/ai_chat"><i class="bi bi-robot fs-5 text-primary"></i> Direct Gemini AI Chat</a>
                    <a class="chrome-menu-item" href="/api/tab/new"><i class="bi bi-plus-square fs-5"></i> New tab</a>
                    <div class="chrome-menu-divider"></div>
                    <a class="chrome-menu-item" href="/my_history"><i class="bi bi-clock-history fs-5"></i> History</a>
                    <a class="chrome-menu-item" href="/bookmarks"><i class="bi bi-star-fill fs-5 text-warning"></i> Bookmarks</a>
                    {owner_menu_item}
                </div>
            </div>
            {f'<a href="/owner_dashboard" class="icon-btn text-danger" title="Admin Panel"><i class="bi bi-speedometer2"></i></a>' if is_owner else ''}
        </div>
    </div>
</div>
"""

def get_footer(active_tab="home"):
    is_owner = session.get("owner_logged", False)
    owner_footer_btn = '<a href="/owner_dashboard" class="nav-link-item"><i class="bi bi-speedometer2 fs-5 d-block text-danger"></i><span>Admin</span></a>' if is_owner else ''

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
    <a href="/studio" class="nav-link-item {'active' if active_tab == 'studio' else ''}">
        <i class="bi bi-youtube fs-5 d-block text-danger"></i>
        <span>Studio</span>
    </a>
    <a href="/ai_chat" class="nav-link-item {'active' if active_tab == 'chat' else ''}">
        <i class="bi bi-robot fs-5 d-block text-primary"></i>
        <span>AI Chat</span>
    </a>
    {owner_footer_btn}
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
    function addNewTab() {{ window.location.href = "/api/tab/new"; }}
    function switchTab(tabId) {{ window.location.href = "/api/tab/switch/" + tabId; }}
    function closeTab(tabId) {{ window.location.href = "/api/tab/close/" + tabId; }}

    // 📱 KEYBOARD PROOF NAVBAR SCRIPT
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
</script>
</body>
</html>
"""

# -------------------------------------------------------------
# 🏠 HOME ROUTE
# -------------------------------------------------------------
@app.route("/")
def home():
    return get_html_header() + f"""
    <div class="container text-center pt-3">
        <div class="bharat-logo mb-1" style="font-size: 52px; font-weight: 700;">
            <span style="color:#FF9933">B</span><span style="color:#000080">h</span><span style="color:#138808">arat</span> 🛕
        </div>
        <p class="fw-medium small mb-2" style="color: #d95100;">Universal AI Search Engine & SuperApp 🇮🇳</p>

        <form action="/search" method="GET" id="searchForm" class="google-search-container">
            <i class="bi bi-search search-left-icon"></i>
            <input type="text" id="searchInput" name="q" class="form-control google-input" placeholder="सर्च करें, वीडियो या सवाल पूछें..." autocomplete="off" required>
        </form>

        <div class="container my-3" style="max-width: 680px;">
            <div class="row g-2 text-start">
                <div class="col-6 col-md-3"><a href="/app_store" class="card p-2 text-decoration-none text-dark shadow-sm text-center rounded-3 bg-white"><div class="fs-4 text-success">🛍️</div><div class="fw-bold small">Play Store</div></a></div>
                <div class="col-6 col-md-3"><a href="/studio" class="card p-2 text-decoration-none text-dark shadow-sm text-center rounded-3 bg-white"><div class="fs-4 text-danger">📺</div><div class="fw-bold small">Studio</div></a></div>
                <div class="col-6 col-md-3"><a href="/ai_chat" class="card p-2 text-decoration-none text-dark shadow-sm text-center rounded-3 bg-white"><div class="fs-4 text-primary">🤖</div><div class="fw-bold small">Gemini AI</div></a></div>
                <div class="col-6 col-md-3"><a href="/owner_login" class="card p-2 text-decoration-none text-dark shadow-sm text-center rounded-3 bg-white"><div class="fs-4 text-warning">🔑</div><div class="fw-bold small">Admin</div></a></div>
            </div>
        </div>
    </div>
    """ + get_footer("home")

# -------------------------------------------------------------
# 💎 EXACT MATCH + GEMINI LIVE ASSISTANT SEARCH
# -------------------------------------------------------------
@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    if not query or not is_safe_query(query): return redirect("/")

    # 1. Exact Match Search in Local DB
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT title, url, snippet, category, logo_url FROM local_search_index WHERE title LIKE ? COLLATE NOCASE", (f"%{query}%",))
    exact_matches = cursor.fetchall()
    conn.close()

    local_html = ""
    for item in exact_matches:
        title, url, snippet, category, logo = item[0], item[1], item[2], item[3], item[4] or "🌐"
        local_html += f"""
        <div class="card p-3 mb-3 border-0 shadow-sm rounded-4 bg-white">
            <div class="d-flex align-items-center gap-2 mb-1">
                <span class="fs-5">{logo}</span>
                <span class="badge bg-success bg-opacity-10 text-success">Exact DB Match</span>
            </div>
            <h5 class="mb-1"><a href="{url}" target="_blank" class="text-primary text-decoration-none fw-bold">{title}</a></h5>
            <p class="text-secondary small mb-2">{snippet}</p>
            <span class="badge bg-light text-dark border">{category}</span>
        </div>
        """

    # 2. Gemini Multi-Model Live AI Answer & Direct Linking
    ai_answer = generate_gemini_smart_search(query)

    return get_html_header() + f"""
    <div class="container mt-4 mb-5" style="max-width: 720px;">
        <div class="d-flex align-items-center justify-content-between mb-3">
            <h5 class="fw-bold text-dark mb-0">🔍 सर्च परिणाम: "{query}"</h5>
            <a href="/" class="btn btn-outline-warning btn-sm rounded-pill">नया सर्च करें</a>
        </div>

        {local_html}

        <div class="card p-4 rounded-4 shadow-sm border-0 bg-white mb-4" style="border-left: 4px solid #ff7700 !important;">
            <div class="d-flex align-items-center justify-content-between mb-2">
                <div class="d-flex align-items-center gap-2">
                    <span class="fs-4">🤖</span>
                    <h6 class="fw-bold text-primary mb-0">Bharat Gemini Live Intelligence</h6>
                </div>
                <span class="badge bg-primary bg-opacity-10 text-primary">Live Response</span>
            </div>
            <hr class="my-2 text-muted">
            <div style="line-height: 1.7; font-size: 15px; color: #202124;">
                {ai_answer}
            </div>
        </div>
    </div>
    """ + get_footer("home")

# -------------------------------------------------------------
# 🤖 DIRECT GEMINI AI CHAT ROUTE
# -------------------------------------------------------------
@app.route("/ai_chat", methods=["GET", "POST"])
def ai_chat():
    if "gemini_chat" not in session:
        session["gemini_chat"] = [{"sender": "recv", "text": "नमस्ते! मैं आपका Gemini AI असिस्टेंट हूँ। मुझसे कुछ भी पूछें।"}]

    if request.method == "POST":
        user_msg = request.form.get("message", "").strip()
        if user_msg:
            session["gemini_chat"].append({"sender": "sent", "text": user_msg})
            ai_reply = generate_gemini_smart_search(user_msg)
            session["gemini_chat"].append({"sender": "recv", "text": ai_reply})
            session.modified = True
        return redirect("/ai_chat")

    msgs_html = "".join([f'<div class="msg msg-{m["sender"]}">{m["text"]}</div>' for m in session["gemini_chat"]])

    return get_html_header() + f"""
    <div class="container mt-2 mb-5" style="max-width: 650px;">
        <div class="d-flex align-items-center justify-content-between bg-white p-3 rounded-top-4 shadow-sm border-bottom">
            <div class="d-flex align-items-center gap-2">
                <span class="fs-3">🤖</span>
                <h5 class="fw-bold mb-0 text-primary">Bharat Gemini AI Chat</h5>
            </div>
            <span class="badge bg-primary px-2 py-1 rounded-pill">Multi-Model Active</span>
        </div>
        <div class="chat-container shadow-sm mb-2" id="chatBox">
            {msgs_html}
        </div>
        <form method="POST" class="input-group bg-white p-2 rounded-bottom-4 shadow-sm">
            <input type="text" name="message" class="form-control rounded-pill border-0 bg-light px-3" placeholder="Gemini से कुछ भी पूछें..." autocomplete="off" required>
            <button type="submit" class="btn btn-primary rounded-circle ms-2 shadow-sm" style="width:42px; height:42px;"><i class="bi bi-send-fill"></i></button>
        </form>
    </div>
    """ + get_footer("chat")

# -------------------------------------------------------------
# 📺 BHARAT STUDIO (YOUTUBE OS: SHORTS, VIDEOS, LIVE, PODCASTS, POSTS)
# -------------------------------------------------------------
@app.route("/studio", methods=["GET", "POST"])
def studio():
    message = ""
    active_tab = request.args.get("tab", "shorts")

    if request.method == "POST":
        title = request.form.get("title")
        media_url = request.form.get("media_url")
        description = request.form.get("description")
        content_type = request.form.get("content_type", "shorts")
        uploader = session.get("username", "Aman Giri (Creator)")

        if title:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO bharat_videos (title, media_url, description, content_type, uploader, timestamp) VALUES (?, ?, ?, ?, ?, ?)", 
                           (title, media_url, description, content_type, uploader, datetime.now().strftime("%Y-%m-%d %H:%M")))
            conn.commit()
            conn.close()
            message = f"✅ आपका {content_type.upper()} सफलतापूर्वक पब्लिश हो गया!"

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT title, media_url, description, content_type, uploader, timestamp FROM bharat_videos WHERE content_type = ? ORDER BY id DESC", (active_tab,))
    items = cursor.fetchall()
    conn.close()

    feed_html = ""
    for item in items:
        title, url, desc, c_type, uploader, time_str = item[0], item[1], item[2], item[3], item[4], item[5]
        badge_cls = "bg-danger" if c_type == "live" else ("bg-warning text-dark" if c_type == "shorts" else "bg-primary")
        feed_html += f"""
        <div class="card p-3 mb-3 border-0 shadow-sm rounded-4 bg-white">
            <div class="d-flex align-items-center justify-content-between mb-2">
                <span class="badge {badge_cls} text-uppercase">{c_type}</span>
                <small class="text-muted">{time_str}</small>
            </div>
            <h6 class="fw-bold mb-1">{title}</h6>
            <p class="text-secondary small mb-2">{desc}</p>
            <div class="d-flex justify-content-between align-items-center mt-2">
                <small class="text-muted">By <b>{uploader}</b></small>
                {f'<a href="{url}" target="_blank" class="btn btn-sm btn-outline-danger rounded-pill fw-bold">Watch / View</a>' if url else ''}
            </div>
        </div>
        """

    return get_html_header() + f"""
    <div class="container mt-3 mb-5" style="max-width: 700px;">
        <div class="text-center mb-3">
            <span class="badge bg-danger px-3 py-1 rounded-pill fw-bold">📺 BHARAT STUDIO ENGINE</span>
            <h3 class="fw-bold mt-2">YouTube Style Creator Hub</h3>
        </div>

        {f'<div class="alert alert-success py-2 small mb-3">{message}</div>' if message else ''}

        <div class="card p-4 border-0 shadow-sm rounded-4 bg-white mb-4">
            <h6 class="fw-bold text-danger mb-3"><i class="bi bi-cloud-upload-fill me-2"></i>Create & Upload Content</h6>
            <form method="POST">
                <div class="row g-2 mb-2">
                    <div class="col-8">
                        <input type="text" name="title" class="form-control form-control-sm" placeholder="Title (शीर्षक)" required>
                    </div>
                    <div class="col-4">
                        <select name="content_type" class="form-select form-select-sm fw-bold border-danger">
                            <option value="shorts">📱 Shorts</option>
                            <option value="videos">🎬 Long Video</option>
                            <option value="live">🔴 Live Stream</option>
                            <option value="podcasts">🎙️ Podcast</option>
                            <option value="posts">📝 Post</option>
                        </select>
                    </div>
                </div>
                <input type="url" name="media_url" class="form-control form-control-sm mb-2" placeholder="Media / Video Link (https://...)">
                <textarea name="description" class="form-control form-control-sm mb-3" rows="2" placeholder="Description / Text Content"></textarea>
                <button type="submit" class="btn btn-danger btn-sm rounded-pill fw-bold w-100">Publish to Bharat Studio</button>
            </form>
        </div>

        <div class="d-flex gap-2 overflow-auto mb-3 pb-1 no-scrollbar">
            <a href="/studio?tab=shorts" class="btn btn-sm {'btn-danger fw-bold' if active_tab == 'shorts' else 'btn-light'} rounded-pill px-3">⚡ Shorts</a>
            <a href="/studio?tab=videos" class="btn btn-sm {'btn-danger fw-bold' if active_tab == 'videos' else 'btn-light'} rounded-pill px-3">🎬 Videos</a>
            <a href="/studio?tab=live" class="btn btn-sm {'btn-danger fw-bold' if active_tab == 'live' else 'btn-light'} rounded-pill px-3">🔴 Live</a>
            <a href="/studio?tab=podcasts" class="btn btn-sm {'btn-danger fw-bold' if active_tab == 'podcasts' else 'btn-light'} rounded-pill px-3">🎙️ Podcasts</a>
            <a href="/studio?tab=posts" class="btn btn-sm {'btn-danger fw-bold' if active_tab == 'posts' else 'btn-light'} rounded-pill px-3">📝 Posts</a>
        </div>

        {feed_html if feed_html else '<div class="card p-4 text-center text-muted bg-white rounded-4">इस सेक्शन में अभी कोई कंटेंट नहीं है। पहला पोस्ट ऊपर पब्लिश करें!</div>'}
    </div>
    """ + get_footer("studio")

# -------------------------------------------------------------
# 🛍️ BHARAT PLAY STORE
# -------------------------------------------------------------
@app.route("/app_store")
def app_store():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT title, url, snippet, logo_url FROM local_search_index")
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
            </div>
            <a href="{url}" target="_blank" class="btn btn-success btn-sm rounded-pill px-3 fw-bold">Open</a>
        </div>
        """

    return get_html_header() + f"""
    <div class="container mt-3 mb-5" style="max-width: 650px;">
        <div class="text-center mb-4">
            <span class="badge bg-success px-3 py-1 rounded-pill fw-bold">🛍️ BHARAT PLAY STORE</span>
            <h3 class="fw-bold mt-2">Daily Needs & Apps Hub</h3>
        </div>
        {apps_html}
    </div>
    """ + get_footer("apps")

# -------------------------------------------------------------
# 👑 SECURE ADMIN / OWNER DASHBOARD (AMAN GIRI)
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
            error = "गलत यूज़रनेम या पासवर्ड! (केवल Admin Aman Giri के लिए)"

    return get_html_header() + f"""
    <div class="container mt-5" style="max-width: 400px;">
        <form method="POST" class="bg-white p-4 rounded-4 shadow-sm border">
            <h4 class="mb-3 text-center text-danger fw-bold">👑 Admin / Owner Login</h4>
            {f'<div class="alert alert-danger py-1 small">{error}</div>' if error else ''}
            <input type="text" name="username" class="form-control mb-3" placeholder="Username (Aman Giri)" required>
            <input type="password" name="password" class="form-control mb-3" placeholder="Password (@Aman2007)" required>
            <button type="submit" class="btn btn-danger w-100 rounded-pill fw-bold">Login as Admin</button>
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
                message = f"✅ नया ऐप/लिंक सिस्टम में पब्लिश किया गया: {title}"

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
                <h4 class="fw-bold text-danger mb-0"><i class="bi bi-speedometer2 me-2"></i>Admin Control Center</h4>
                <a href="/logout" class="btn btn-outline-danger btn-sm rounded-pill">Logout (Aman Giri)</a>
            </div>
            {f'<div class="alert alert-success py-2 small mb-3">{message}</div>' if message else ''}
            
            <div class="card p-3 border-secondary bg-white mb-4 rounded-4">
                <h6 class="fw-bold text-dark mb-2"><i class="bi bi-bag-plus-fill text-success me-2"></i>Add App / Link to System</h6>
                <form method="POST">
                    <input type="hidden" name="form_type" value="add_link">
                    <div class="row g-2 mb-2">
                        <div class="col-12 col-md-6"><input type="text" name="title" class="form-control form-control-sm" placeholder="Title / App Name" required></div>
                        <div class="col-12 col-md-6"><input type="url" name="url" class="form-control form-control-sm" placeholder="URL (https://...)" required></div>
                    </div>
                    <div class="row g-2 mb-3">
                        <div class="col-12 col-md-8"><input type="text" name="snippet" class="form-control form-control-sm" placeholder="Description" required></div>
                        <div class="col-12 col-md-4"><input type="text" name="logo_url" class="form-control form-control-sm" placeholder="Icon Emoji" value="📱" required></div>
                    </div>
                    <button type="submit" class="btn btn-success btn-sm rounded-pill fw-bold w-100">Publish to System</button>
                </form>
            </div>

            <div class="card p-3 border-warning bg-warning bg-opacity-10 mb-4 rounded-4">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <h6 class="fw-bold text-dark mb-0"><i class="bi bi-bug-fill text-warning me-2"></i>Web Crawler Engine</h6>
                        <small class="text-muted">इंडेक्स सिंक करें (कुल इंडेक्स: {total_indexed_count})</small>
                    </div>
                    <form method="POST" class="mb-0">
                        <input type="hidden" name="form_type" value="run_crawler">
                        <button type="submit" class="btn btn-warning btn-sm rounded-pill fw-bold px-3">Run Crawler</button>
                    </form>
                </div>
            </div>
            
            <div class="card p-3 border-secondary bg-light rounded-4">
                <h6 class="fw-bold text-dark mb-2"><i class="bi bi-people-fill text-primary me-2"></i>Registered Users ({total_users_count})</h6>
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
# 📌 HELPER ROUTES
# -------------------------------------------------------------
@app.route("/bookmarks")
def bookmarks(): return get_html_header() + '<div class="container mt-4 text-center" style="max-width:600px;"><h5 class="fw-bold mb-3"><i class="bi bi-star-fill text-warning me-2"></i>Bookmarked Pages</h5><p class="text-muted">कोई बुकमार्क सेव नहीं है।</p></div>' + get_footer("home")

@app.route("/my_history")
def my_history(): return get_html_header() + '<div class="container mt-4 text-center" style="max-width:600px;"><h5 class="fw-bold mb-3"><i class="bi bi-clock-history me-2 text-warning"></i>Search History</h5><p class="text-muted">हिस्ट्री खाली है।</p></div>' + get_footer("home")

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
