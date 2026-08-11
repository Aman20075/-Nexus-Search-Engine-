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

# 🤖 GOOGLE GENAI SDK IMPORT (Gemini 3.6 Flash Support)
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
VIP_DAYS = 90

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

# -------------------------------------------------------------
# 👑 HYPER-ADVANCED MEMBERSHIP MATRIX
# -------------------------------------------------------------
TIER_DETAILS = {
    "Free": {"price": 0, "days": 0, "badge": "🟢 FREE USER", "cls": "bg-secondary", "level": 0},
    "VIP": {"price": 49, "days": 90, "badge": "🔵 VIP MEMBER", "cls": "bg-warning text-dark", "level": 1},
    "VIP_PRO": {"price": 149, "days": 90, "badge": "🟣 VIP PRO", "cls": "bg-primary", "level": 2},
    "VIP_ULTRA": {"price": 299, "days": 90, "badge": "👑 VIP ULTRA", "cls": "bg-danger", "level": 3}
}

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
        CREATE TABLE IF NOT EXISTS payment_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            utr_number TEXT UNIQUE,
            plan_type TEXT DEFAULT 'VIP',
            status TEXT DEFAULT 'pending',
            timestamp TEXT
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

    try: cursor.execute("ALTER TABLE payment_requests ADD COLUMN plan_type TEXT DEFAULT 'VIP'")
    except Exception: pass

    try: cursor.execute("ALTER TABLE users ADD COLUMN tier TEXT DEFAULT 'Free'")
    except Exception: pass

    conn.commit()
    conn.close()
    auto_seed_master_data()
    sync_db_to_vector_engine(DB_PATH)

def auto_seed_master_data():
    master_links = [
        ("ChatGPT", "https://chatgpt.com/", "Official ChatGPT AI chatbot for writing, coding, and query resolution.", "AI Tools"),
        ("Google Gemini", "https://gemini.google.com/", "Google's official advanced multimodal AI assistant.", "AI Tools"),
        ("Microsoft Copilot", "https://copilot.microsoft.com/", "Official AI assistant integrated with Bing search.", "AI Tools"),
        ("Piramal Finance", "https://www.piramalfinance.com/", "Official site for Piramal personal, home, and business loans.", "Loans/NBFC"),
        ("Aavas Financiers", "https://www.aavas.in/", "Official site for Aavas home loans and loan against property.", "Housing Finance"),
        ("Bajaj Finance", "https://www.bajajfinserv.in/", "Consumer durable loans, personal credit, and EMI cards.", "Loans/NBFC"),
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

def get_user_tier_info():
    if session.get("owner_logged"):
        return "VIP_ULTRA", TIER_DETAILS["VIP_ULTRA"]
    
    username = session.get("username")
    if not username:
        return "Free", TIER_DETAILS["Free"]

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT tier, is_premium, vip_expires_at FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return "Free", TIER_DETAILS["Free"]

    tier = row[0] or "Free"
    is_prem = row[1]
    expires_at_str = row[2]

    if is_prem and expires_at_str:
        try:
            expires_at = datetime.strptime(expires_at_str, "%Y-%m-%d %H:%M:%S")
            if datetime.now() > expires_at:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET is_premium = 0, tier = 'Free' WHERE username = ?", (username,))
                conn.commit()
                conn.close()
                return "Free", TIER_DETAILS["Free"]
        except ValueError:
            pass
        return tier, TIER_DETAILS.get(tier, TIER_DETAILS["VIP"])

    return "Free", TIER_DETAILS["Free"]

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
    "national": "https://news.google.com/rss/headlines/section/topic/NATION?hl=hi&gl=IN&ceid=IN:hi",
    "tech": "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=hi&gl=IN&ceid=IN:hi",
    "sports": "https://news.google.com/rss/headlines/section/topic/SPORTS?hl=hi&gl=IN&ceid=IN:hi",
    "entertainment": "https://news.google.com/rss/headlines/section/topic/ENTERTAINMENT?hl=hi&gl=IN&ceid=IN:hi",
    "business": "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=hi&gl=IN&ceid=IN:hi"
}

def fetch_unlimited_news(category="top"):
    news_items = []
    rss_url = NEWS_CATEGORIES.get(category, NEWS_CATEGORIES["top"])
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(rss_url, headers=headers, timeout=6)
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
# 🎨 CHROME 3-DOT MENU & HEADER ENGINE
# -------------------------------------------------------------
def get_html_header():
    tier_name, tier_info = get_user_tier_info()
    is_owner = session.get("owner_logged", False)
    username = session.get("username", "Owner" if is_owner else "Guest User")
    
    badge_label = "👑 OWNER" if is_owner else tier_info["badge"]
    badge_class = "bg-danger" if is_owner else tier_info["cls"]

    adsense_script = """<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-6514818403683886" crossorigin="anonymous"></script>""" if tier_name == "Free" else "<!-- VIP Member: Ads Disabled -->"

    tabs_bar = get_chrome_tabs_html()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Bharat AI OS | Universal SuperApp Engine</title>
    {adsense_script}
    <link rel="manifest" href="/manifest.json">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css">
    <style>
        :root {{ --bg-color: #fff9f2; --text-color: #202124; --card-bg: rgba(255, 255, 255, 0.95); --border-color: #f1d3b3; }}
        body.dark-mode {{ --bg-color: #121212; --text-color: #e8eaed; --card-bg: rgba(30, 30, 30, 0.95); --border-color: #3c4043; }}
        
        html {{ height: 100%; margin: 0; }}
        body {{ 
            min-height: 100%; 
            margin: 0; 
            background-color: var(--bg-color); 
            color: var(--text-color); 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            transition: background 0.3s, color 0.3s; 
            padding-bottom: 95px !important; 
        }}

        .sticky-top-header {{
            position: sticky;
            top: 0;
            z-index: 9999;
            background-color: var(--bg-color);
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}

        .top-bar-chrome {{ display: flex; justify-content: space-between; align-items: center; padding: 10px 16px; background-color: var(--bg-color); }}
        .creator-badge {{ font-size: 13px; font-weight: 600; color: #d96b00; display: flex; align-items: center; gap: 4px; }}
        .top-actions {{ display: flex; align-items: center; gap: 10px; }}
        .icon-btn {{ background: none; border: none; font-size: 22px; color: #d96b00; cursor: pointer; text-decoration: none; padding: 4px; }}
        
        .bharat-logo {{ font-size: 52px; font-weight: 700; letter-spacing: -1.5px; margin-top: 10px; }}
        
        .google-search-container {{ max-width: 620px; width: 92%; margin: 15px auto; position: relative; }}
        .google-input {{ height: 54px; border-radius: 27px; padding-left: 48px; padding-right: 90px; border: 2px solid #ffaa44; background: var(--card-bg); color: var(--text-color); box-shadow: 0 4px 12px rgba(255, 153, 51, 0.2); font-size: 15px; }}
        .search-left-icon {{ position: absolute; left: 18px; top: 18px; color: #e67300; font-size: 18px; z-index: 10; }}
        
        .search-right-actions {{ position: absolute; right: 16px; top: 12px; display: flex; align-items: center; gap: 8px; z-index: 10; }}
        .search-action-btn {{ background: none; border: none; font-size: 20px; color: #e67300; cursor: pointer; padding: 4px; border-radius: 50%; display: flex; align-items: center; justify-content: center; }}
        .search-action-btn:hover {{ background-color: rgba(255, 153, 51, 0.15); }}
        
        /* 🔍 REAL-TIME AUTO-SUGGESTIONS BOX */
        .suggestions-box {{ 
            position: absolute; 
            top: 58px; 
            left: 0; 
            right: 0; 
            background: #fff; 
            border-radius: 16px; 
            box-shadow: 0 8px 24px rgba(0,0,0,0.15); 
            border: 1px solid #ffe0b2; 
            z-index: 9999; 
            display: none; 
            text-align: left; 
            overflow: hidden; 
        }}
        .suggestion-item {{ 
            padding: 12px 20px; 
            cursor: pointer; 
            font-size: 14px; 
            border-bottom: 1px solid #fff3e0; 
            display: flex; 
            align-items: center; 
            gap: 10px; 
            color: #333; 
        }}
        .suggestion-item:hover {{ background-color: #fff3e0; color: #d96b00; }}

        /* 📱 PROFESSIONAL BOTTOM NAVIGATION BAR */
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
        .nav-link-item {{ 
            text-decoration: none; 
            color: #5f6368; 
            font-size: 11px; 
            text-align: center; 
            flex: 1; 
            transition: all 0.2s ease;
        }}
        .nav-link-item.active {{ 
            color: #ff7700 !important; 
            font-weight: 700; 
            transform: translateY(-2px);
        }}
        .no-scrollbar::-webkit-scrollbar {{ display: none; }}

        .chrome-menu {{ width: 280px; border-radius: 20px; padding: 8px 0; border: none; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }}
        .chrome-menu-header {{ display: flex; justify-content: space-between; padding: 8px 16px; border-bottom: 1px solid #f0f0f0; margin-bottom: 6px; }}
        .chrome-top-icon {{ width: 36px; height: 36px; border-radius: 50%; background: #f1f3f4; display: flex; align-items: center; justify-content: center; color: #3c4043; text-decoration: none; font-size: 16px; }}
        .chrome-top-icon:hover {{ background: #e8eaed; }}
        .chrome-menu-item {{ padding: 10px 20px; font-size: 14px; color: #3c4043; display: flex; align-items: center; gap: 14px; text-decoration: none; font-weight: 500; }}
        .chrome-menu-item:hover {{ background-color: #f8f9fa; color: #000; }}
        .chrome-menu-divider {{ height: 1px; background: #e8eaed; margin: 6px 0; }}

        .pro-result-card {{
            transition: all 0.2s ease-in-out;
            border: 1px solid #ffe4cc !important;
        }}
        .pro-result-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(255, 153, 51, 0.15) !important;
        }}
    </style>
</head>
<body>

<!-- STICKY TOP HEADER -->
<div class="sticky-top-header">
    {tabs_bar}

    <div class="top-bar-chrome">
        <div class="creator-badge">🚀 <b>Bharat OS</b> <span class="badge {badge_class} rounded-pill ms-1">{badge_label}</span></div>
        <div class="top-actions">
            <a href="/app_store" class="icon-btn text-success" title="App Store"><i class="bi bi-bag-check-fill"></i></a>
            <a href="/chats" class="icon-btn" title="Bharat Chat"><i class="bi bi-chat-dots-fill text-primary"></i></a>
            <a href="/vip_tiers" class="icon-btn" title="VIP Tiers"><i class="bi bi-gem-fill text-warning"></i></a>
            
            <div class="dropdown">
                <button class="icon-btn" type="button" data-bs-toggle="dropdown"><i class="bi bi-three-dots-vertical"></i></button>
                <div class="dropdown-menu dropdown-menu-end chrome-menu shadow-lg">
                    <div class="chrome-menu-header">
                        <a href="javascript:history.forward()" class="chrome-top-icon" title="Forward"><i class="bi bi-arrow-right"></i></a>
                        <a href="/add_bookmark" class="chrome-top-icon" title="Bookmark"><i class="bi bi-star"></i></a>
                        <a href="/converters" class="chrome-top-icon" title="Downloads"><i class="bi bi-download"></i></a>
                        <a href="/privacy_center" class="chrome-top-icon" title="Info"><i class="bi bi-info-circle"></i></a>
                        <a href="javascript:location.reload()" class="chrome-top-icon" title="Reload"><i class="bi bi-arrow-clockwise"></i></a>
                    </div>

                    <a class="chrome-menu-item" href="/app_store"><i class="bi bi-bag-check-fill fs-5 text-success"></i> Bharat App Store</a>
                    <a class="chrome-menu-item" href="/api/tab/new"><i class="bi bi-plus-square fs-5"></i> New tab</a>
                    <a class="chrome-menu-item" href="/api/tab/new?incognito=true"><i class="bi bi-incognito fs-5"></i> New Incognito tab</a>
                    
                    <div class="chrome-menu-divider"></div>
                    
                    <a class="chrome-menu-item" href="/my_history"><i class="bi bi-clock-history fs-5"></i> History</a>
                    <a class="chrome-menu-item" href="/clear_browsing_data"><i class="bi bi-trash fs-5 text-danger"></i> Delete browsing data</a>
                    
                    <div class="chrome-menu-divider"></div>
                    
                    <a class="chrome-menu-item" href="/converters"><i class="bi bi-download fs-5"></i> Downloads</a>
                    <a class="chrome-menu-item" href="/bookmarks"><i class="bi bi-star-fill fs-5 text-warning"></i> Bookmarks</a>
                    
                    <div class="chrome-menu-divider"></div>
                    
                    <a class="chrome-menu-item fw-bold text-primary" href="/"><i class="bi bi-stars fs-5"></i> Open Gemini AI</a>
                    <a class="chrome-menu-item" href="/privacy_center"><i class="bi bi-gear fs-5"></i> Settings</a>
                    <a class="chrome-menu-item" href="/chats"><i class="bi bi-question-circle fs-5"></i> Help & Feedback</a>
                </div>
            </div>

            <div class="dropdown">
                <button class="icon-btn" type="button" data-bs-toggle="dropdown"><i class="bi bi-person-circle fs-3 text-warning"></i></button>
                <div class="dropdown-menu dropdown-menu-end p-3 shadow-lg" style="width: 280px; border-radius: 20px;">
                    <div class="text-center pb-2 border-bottom mb-2">
                        <h6 class="fw-bold mb-0">{username}</h6>
                        <span class="badge {badge_class} rounded-pill mt-1" style="font-size:10px;">{badge_label}</span>
                    </div>
                    <div class="list-group list-group-flush small">
                        <a href="/vip_tiers" class="list-group-item list-group-item-action border-0 py-2 text-warning fw-bold"><i class="bi bi-crown me-2"></i> Subscription Tiers</a>
                        <a href="/privacy_center" class="list-group-item list-group-item-action border-0 py-2"><i class="bi bi-shield-check me-2"></i> Privacy Dashboard</a>
                        {f'<a href="/owner_dashboard" class="list-group-item list-group-item-action border-0 py-2 text-danger fw-bold"><i class="bi bi-speedometer2 me-2"></i> Owner Control Center</a>' if is_owner else ''}
                        <hr class="my-2">
                        {f'<a href="/logout" class="list-group-item list-group-item-action border-0 py-2 text-danger"><i class="bi bi-box-arrow-right me-2"></i> Sign Out</a>' if (session.get('user_logged') or is_owner) else '<a href="/user_login" class="list-group-item list-group-item-action border-0 py-2 text-success fw-bold"><i class="bi bi-box-arrow-in-right me-2"></i> Sign In / Register</a>'}
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
"""

# -------------------------------------------------------------
# 📱 BOTTOM NAVIGATION FOOTER ENGINE
# -------------------------------------------------------------
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
    <a href="/converters" class="nav-link-item {'active' if active_tab == 'converters' else ''}">
        <i class="bi bi-gear-wide-connected fs-5 d-block text-warning"></i>
        <span>Tools</span>
    </a>
    <a href="/chats" class="nav-link-item {'active' if active_tab == 'chats' else ''}">
        <i class="bi bi-chat-dots-fill fs-5 d-block text-primary"></i>
        <span>Chats</span>
    </a>
    <a href="/vip_tiers" class="nav-link-item {'active' if active_tab == 'vip' else ''}">
        <i class="bi bi-gem-fill fs-5 d-block text-danger"></i>
        <span>VIP</span>
    </a>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
    function addNewTab() {{ window.location.href = "/api/tab/new"; }}
    function switchTab(tabId) {{ window.location.href = "/api/tab/switch/" + tabId; }}
    function closeTab(tabId) {{ window.location.href = "/api/tab/close/" + tabId; }}

    function toggleDarkMode() {{
        document.body.classList.toggle('dark-mode');
        localStorage.setItem('bharat_dark_mode', document.body.classList.contains('dark-mode') ? 'enabled' : 'disabled');
    }}
    if (localStorage.getItem('bharat_dark_mode') === 'enabled') {{ document.body.classList.add('dark-mode'); }}

    // Keyboard Auto-Hide for Navigation Bar
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

    // Real-Time Auto-Suggestions Handler
    const searchInput = document.getElementById("searchInput");
    const suggestionsBox = document.getElementById("suggestionsBox");
    const searchForm = document.getElementById("searchForm");

    if (searchInput) {{
        searchInput.addEventListener("input", async function() {{
            const query = this.value.trim();
            if (query.length < 2) {{ 
                if(suggestionsBox) suggestionsBox.style.display = "none"; 
                return; 
            }}
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
            }} catch(e) {{
                if(suggestionsBox) suggestionsBox.style.display = "none";
            }}
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

    // Voice Search Engine
    function startVoiceSearch() {{
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {{ alert("आपका ब्राउज़र वॉइस सर्च का समर्थन नहीं करता।"); return; }}
        const recognition = new SpeechRecognition();
        recognition.lang = 'hi-IN';
        const micBtn = document.getElementById("micIcon");
        if(micBtn) micBtn.style.color = "red";
        
        recognition.onstart = function() {{ 
            if(searchInput) searchInput.placeholder = "बोलिए, सुन रहा हूँ..."; 
        }};
        recognition.onresult = function(event) {{
            if(searchInput) {{
                searchInput.value = event.results[0][0].transcript;
                if(searchForm) searchForm.submit();
            }}
        }};
        recognition.start();
    }}

    // Camera/Lens Upload Handler
    function triggerCameraUpload() {{ 
        const camInput = document.getElementById("cameraFileInput");
        if(camInput) camInput.click(); 
    }}
    function handleCameraSearch(input) {{
        if (input.files && input.files[0]) {{
            if(searchInput) {{
                searchInput.value = "इमेज एनालिसिस: " + input.files[0].name;
                if(searchForm) searchForm.submit();
            }}
        }}
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
    cat = request.args.get("category", "top")
    news_list = fetch_unlimited_news(cat)
    
    news_html = "".join([f"""
    <div class="col-12 col-md-6 mb-3">
        <a href="{n['link']}" target="_blank" class="text-decoration-none text-dark">
            <div class="card news-card p-3 h-100 shadow-sm border-0 rounded-4 d-flex flex-row align-items-center gap-3">
                <img src="{n['image']}" width="65" height="65" class="rounded-3" style="object-fit: cover;" alt="News">
                <div class="flex-grow-1">
                    <h6 class="fw-bold mb-1 text-dark" style="font-size: 13px; line-height: 1.4;">{n['title']}</h6>
                    <small class="text-muted" style="font-size: 10px;">{n['source']} • {n['date']}</small>
                </div>
            </div>
        </a>
    </div>
    """ for n in news_list])

    return get_html_header() + f"""
    <div class="ram-mandir-bg">
        <div class="container text-center pt-2">
            <div class="bharat-logo mb-1">
                <span style="color:#FF9933">B</span><span style="color:#000080">h</span><span style="color:#138808">arat</span> 🛕
            </div>
            <p class="fw-medium small mb-2" style="color: #d95100;">Universal AI Search Engine 🇮🇳</p>

            <form action="/search" method="GET" id="searchForm" class="google-search-container">
                <i class="bi bi-search search-left-icon"></i>
                <input type="text" id="searchInput" name="q" class="form-control google-input" placeholder="सर्च करें, फाइल्स ढूंढें या AI से पूछें..." autocomplete="off" required>
                <input type="file" id="cameraFileInput" accept="image/*" capture="environment" style="display:none;" onchange="handleCameraSearch(this)">

                <div class="search-right-actions">
                    <button type="button" class="search-action-btn" id="micIcon" onclick="startVoiceSearch()" title="Voice Search"><i class="bi bi-mic-fill"></i></button>
                    <button type="button" class="search-action-btn" onclick="triggerCameraUpload()" title="Google Lens Camera"><i class="bi bi-camera-fill"></i></button>
                </div>

                <div id="suggestionsBox" class="suggestions-box"></div>

                <div class="d-flex gap-2 overflow-auto py-2 px-1 no-scrollbar mt-2" style="white-space: nowrap;">
                    <select name="file_type" class="form-select form-select-sm rounded-pill border-warning" style="width: 110px;">
                        <option value="all">📁 All Files</option>
                        <option value="pdf">📄 PDF</option>
                        <option value="docx">📝 DOCX</option>
                        <option value="pptx">📊 PPTX</option>
                    </select>

                    <select name="country" class="form-select form-select-sm rounded-pill border-warning" style="width: 110px;">
                        <option value="all">🌍 Global</option>
                        <option value="IN">🇮🇳 India</option>
                        <option value="US">🇺🇸 USA</option>
                    </select>

                    <select name="mode" class="form-select form-select-sm rounded-pill border-warning" style="width: 130px;">
                        <option value="fast">⚡ Fast AI</option>
                        <option value="deep">🔬 Deep Research</option>
                        <option value="eli5">👶 ELI5 Mode</option>
                    </select>
                </div>
            </form>

            <div class="container my-3" style="max-width: 680px;">
                <div class="row g-2 text-start">
                    <div class="col-6 col-md-3"><a href="/app_store" class="card p-2 text-decoration-none text-dark shadow-sm text-center rounded-3 bg-white"><div class="fs-4 text-success">🛍️</div><div class="fw-bold small" style="font-size:12px;">App Store</div></a></div>
                    <div class="col-6 col-md-3"><a href="/search?q=Khan+Academy" class="card p-2 text-decoration-none text-dark shadow-sm text-center rounded-3 bg-white"><div class="fs-4 text-primary">🎓</div><div class="fw-bold small" style="font-size:12px;">All Boards Study</div></a></div>
                    <div class="col-6 col-md-3"><a href="/search?q=ChatGPT" class="card p-2 text-decoration-none text-dark shadow-sm text-center rounded-3 bg-white"><div class="fs-4 text-info">🤖</div><div class="fw-bold small" style="font-size:12px;">AI Tools</div></a></div>
                    <div class="col-6 col-md-3"><a href="/games" class="card p-2 text-decoration-none text-dark shadow-sm text-center rounded-3 bg-white"><div class="fs-4 text-danger">🎮</div><div class="fw-bold small" style="font-size:12px;">Games Arcade</div></a></div>
                </div>
            </div>

            <div class="container text-start mt-2 mb-5" style="max-width: 720px;">
                <h6 class="fw-bold text-muted mb-2"><i class="bi bi-newspaper text-warning me-2"></i>Discover Feed</h6>
                <div class="row">{news_html}</div>
            </div>
        </div>
    </div>
    """ + get_footer("home")

# -------------------------------------------------------------
# 💎 IN-APP BHARAT SEARCH RESULT ROUTE (NO EXTERNAL REDIRECTS)
# -------------------------------------------------------------
@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    file_type = request.args.get("file_type", "all")
    country = request.args.get("country", "all")
    mode = request.args.get("mode", "fast")

    if not query or not is_safe_query(query): 
        return redirect("/")

    if "tabs" in session:
        for t in session["tabs"]:
            if t["id"] == session.get("active_tab", 1):
                t["title"] = query
                t["query"] = query
        session.modified = True

    username = session.get("username", "Guest")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO search_history (username, query, timestamp) VALUES (?, ?, ?)", (username, query, now_str))
        conn.commit()
        conn.close()
    except Exception:
        pass

    engine_data = bharat_engine.process_super_search(query)
    intent_data = engine_data.get("intent", {})
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
            <a href="{kg_card['official_website']}" class="btn btn-warning btn-sm rounded-pill fw-bold">आधिकारिक पोर्टल पर जाएँ</a>
        </div>
        """

    local_html = ""
    for item in vector_results:
        title, url, snippet, category = item["title"], item["url"], item["snippet"], item["category"]
        domain = urlparse(url).netloc if url else 'bharat.app'
        favicon = f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
        local_html += f"""
        <div class="card pro-result-card p-3 mb-3 border-0 shadow-sm rounded-4 bg-white">
            <div class="d-flex align-items-center gap-2 mb-2">
                <img src="{favicon}" width="22" height="22" class="rounded-circle border p-1" alt="icon">
                <div>
                    <div class="fw-bold text-dark" style="font-size: 12px; line-height: 1;">{domain.replace('www.', '')}</div>
                    <small class="text-muted" style="font-size: 10px;">{url[:45]}...</small>
                </div>
            </div>
            <h5 class="mb-1"><a href="{url}" class="text-primary text-decoration-none fw-bold" style="font-size:16px;">{title}</a></h5>
            <p class="text-secondary small mb-2" style="font-size: 13px; line-height: 1.5;">{snippet}</p>
            <div class="d-flex gap-2">
                <span class="badge bg-light text-dark border">{category}</span>
                <span class="badge bg-success bg-opacity-10 text-success">Verified In-App Match</span>
            </div>
        </div>
        """

    prompt_prefix = "Explain like I'm 5 years old:" if mode == "eli5" else ("Provide a detailed academic research report with citation facts for:" if mode == "deep" else "Provide a concise summary for:")
    ai_answer = ""

    if genai_client:
        models_to_try = ["gemini-3.6-flash", "gemini-2.5-flash", "gemini-1.5-flash"]
        for model_name in models_to_try:
            try:
                response = genai_client.models.generate_content(
                    model=model_name,
                    contents=f"{prompt_prefix} {query}. उत्तर सरल हिंदी में दें।"
                )
                if response and response.text:
                    ai_answer = format_markdown_to_html(response.text)
                    break
            except Exception:
                continue

    if not ai_answer:
        ai_answer = f"<b>'{query}'</b> के लिए खोज पूर्ण हुई।"

    if not local_html:
        local_html = f"""
        <div class="card p-4 text-center border-0 shadow-sm rounded-4 bg-white">
            <h6 class="fw-bold text-dark mb-1">🔍 Bharat AI Search Result</h6>
            <p class="text-muted small mb-0">'{query}' से संबंधित AI समरी ऊपर दी गई है। नए लिंक्स जोड़ने के लिए Owner Control में इंडेक्स करें।</p>
        </div>
        """

    return get_html_header() + f"""
    <div class="container mt-4 mb-5" style="max-width: 720px;">
        <div class="d-flex gap-2 mb-3">
            <span class="badge bg-warning text-dark">Category: {intent_data.get('category', 'General').upper()}</span>
            <span class="badge bg-secondary">Filter: {file_type.upper()}</span>
            <span class="badge bg-info text-dark">Region: {country.upper()}</span>
        </div>

        {kg_html}

        <div class="card p-4 rounded-4 shadow-sm border-0 bg-white mb-4" style="border-left: 4px solid #ff7700 !important;">
            <div class="d-flex align-items-center justify-content-between mb-2">
                <div class="d-flex align-items-center gap-2">
                    <span class="fs-4">🤖</span>
                    <h6 class="fw-bold text-primary mb-0">Bharat AI Summary Engine</h6>
                </div>
                <span class="badge bg-primary bg-opacity-10 text-primary">In-App Search</span>
            </div>
            <hr class="my-2 text-muted">
            <div style="line-height: 1.6; font-size: 14px; color: #202124;">
                {ai_answer}
            </div>
        </div>

        <h6 class="fw-bold text-muted mb-3"><i class="bi bi-cpu me-2"></i>Bharat In-App Results</h6>
        {local_html}
    </div>
    """ + get_footer("home")

# -------------------------------------------------------------
# 🛍️ BHARAT APP STORE ROUTE (DIRECT INSTALLATION)
# -------------------------------------------------------------
@app.route("/app_store")
def app_store():
    apps = [
        {"id": "chat", "name": "Bharat Chat AI", "desc": "Instant AI Messenger for Teams & Friends", "icon": "💬", "rating": "4.9 ★", "url": "/chats"},
        {"id": "pdf", "name": "Image PDF Converter Pro", "desc": "Fast offline JPG to PDF Converter Tool", "icon": "📄", "rating": "4.8 ★", "url": "/converters"},
        {"id": "snake", "name": "Snake Game Arcade", "desc": "Classic Playable Retro Browser Game", "icon": "🐍", "rating": "4.7 ★", "url": "/games"},
        {"id": "research", "name": "Research Workspace OS", "desc": "Academic Research & PDF Summarizer", "icon": "📚", "rating": "5.0 ★", "url": "/research"}
    ]

    apps_html = ""
    for a in apps:
        apps_html += f"""
        <div class="card p-3 mb-3 border-0 shadow-sm rounded-4 bg-white">
            <div class="d-flex align-items-center gap-3">
                <div class="fs-1 p-2 bg-light rounded-4">{a['icon']}</div>
                <div class="flex-grow-1">
                    <h6 class="fw-bold mb-0 text-dark">{a['name']}</h6>
                    <small class="text-muted d-block">{a['desc']}</small>
                    <small class="text-warning fw-bold">{a['rating']} • Instant Direct Install</small>
                </div>
                <button class="btn btn-success btn-sm rounded-pill px-3 fw-bold" id="installBtn_{a['id']}" onclick="directInstallApp('{a['name']}', '{a['url']}', 'installBtn_{a['id']}')">
                    <i class="bi bi-download me-1"></i> Install
                </button>
            </div>
        </div>
        """

    return get_html_header() + f"""
    <div class="container mt-4 mb-5" style="max-width: 650px;">
        <div class="text-center mb-4">
            <span class="badge bg-success px-3 py-1 rounded-pill fw-bold">🛍️ DIRECT WEB-APK STORE</span>
            <h3 class="fw-bold mt-2">Bharat Play Store</h3>
            <p class="text-muted small">बिना APK डाउनलोड किए सीधे 1-Click में फ़ोन पर इंस्टॉल करें</p>
        </div>
        {apps_html}
    </div>

    <script>
        let deferredPrompt;
        window.addEventListener('beforeinstallprompt', (e) => {{
            e.preventDefault();
            deferredPrompt = e;
        }});

        function directInstallApp(appName, appUrl, btnId) {{
            const btn = document.getElementById(btnId);
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Installing...';
            btn.disabled = true;

            setTimeout(() => {{
                if (deferredPrompt) {{
                    deferredPrompt.prompt();
                    deferredPrompt.userChoice.then((choiceResult) => {{
                        if (choiceResult.outcome === 'accepted') {{
                            btn.className = "btn btn-secondary btn-sm rounded-pill px-3 fw-bold";
                            btn.innerText = "Installed ✓";
                        }} else {{
                            btn.className = "btn btn-success btn-sm rounded-pill px-3 fw-bold";
                            btn.innerHTML = '<i class="bi bi-download me-1"></i> Install';
                            btn.disabled = false;
                        }}
                        deferredPrompt = null;
                    }});
                }} else {{
                    btn.className = "btn btn-secondary btn-sm rounded-pill px-3 fw-bold";
                    btn.innerText = "Installed ✓";
                    alert("📲 " + appName + " आपके फ़ोन पर सफलतापूर्वक इंस्टॉल हो गया है!");
                    window.location.href = appUrl;
                }}
            }}, 1200);
        }}
    </script>
    """ + get_footer("apps")

# -------------------------------------------------------------
# 👑 OWNER DASHBOARD
# -------------------------------------------------------------
@app.route("/owner_dashboard", methods=["GET", "POST"])
def owner_dashboard():
    if not session.get("owner_logged"): return redirect("/owner_login")

    message = ""
    if request.method == "POST":
        form_type = request.form.get("form_type")

        if form_type == "run_crawler":
            try:
                sync_db_to_vector_engine(DB_PATH)
                message = "🕷️ <b>Web Crawler Resync Complete!</b> सभी नए लिंक्स और डेटाबेस वेक्टर इंजन के साथ सिंक हो गए हैं।"
            except Exception as e:
                message = f"⚠️ क्रॉलर एरर: {str(e)}"

        elif form_type == "add_link":
            title, url, snippet, category = request.form.get("title"), request.form.get("url"), request.form.get("snippet"), request.form.get("category")
            if title and url:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO local_search_index (title, url, snippet, category) VALUES (?, ?, ?, ?)", (title, url, snippet, category))
                conn.commit()
                conn.close()
                bharat_engine.index_item(title, url, snippet, category)
                message = f"✅ नई लिंक क्रॉल और इंडेक्स हो गई: {title}"

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users_count = cursor.fetchone()[0]
    cursor.execute("SELECT id, username, tier, is_premium, vip_expires_at FROM users ORDER BY id DESC")
    all_users_list = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) FROM local_search_index")
    total_indexed_count = cursor.fetchone()[0]
    conn.close()

    users_table_rows = "".join([f"<tr><td>#{u[0]}</td><td><b>{u[1]}</b></td><td><span class='badge bg-secondary'>{u[2] or 'Free'}</span></td></tr>" for u in all_users_list])

    return get_html_header() + f"""
    <div class="container mt-4 mb-5" style="max-width: 850px;">
        <div class="bg-white p-4 rounded-4 shadow-sm border mb-4">
            <h4 class="fw-bold text-danger mb-3"><i class="bi bi-speedometer2 me-2"></i>Owner Control Center</h4>
            
            {f'<div class="alert alert-success py-2 small mb-3">{message}</div>' if message else ''}

            <div class="card p-3 border-warning bg-warning bg-opacity-10 mb-4 rounded-4">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <h6 class="fw-bold text-dark mb-0"><i class="bi bi-bug-fill text-warning me-2"></i>Bharat Web Crawler Engine</h6>
                        <small class="text-muted">डेटाबेस और नए लिंक्स को स्मार्ट वेक्टर सर्च इंडेक्स में तुरंत सिंक करें</small>
                    </div>
                    <form method="POST" class="mb-0">
                        <input type="hidden" name="form_type" value="run_crawler">
                        <button type="submit" class="btn btn-warning btn-sm rounded-pill fw-bold px-3"><i class="bi bi-arrow-repeat me-1"></i> Run Crawler Now</button>
                    </form>
                </div>
            </div>

            <div class="card p-3 border-secondary bg-white mb-4 rounded-4">
                <h6 class="fw-bold text-dark mb-2"><i class="bi bi-plus-circle-fill text-primary me-2"></i>Crawl & Add New Web Link</h6>
                <form method="POST">
                    <input type="hidden" name="form_type" value="add_link">
                    <div class="row g-2 mb-2">
                        <div class="col-12 col-md-6"><input type="text" name="title" class="form-control form-control-sm" placeholder="Site Title" required></div>
                        <div class="col-12 col-md-6"><input type="url" name="url" class="form-control form-control-sm" placeholder="Full URL (https://...)" required></div>
                    </div>
                    <div class="row g-2 mb-3">
                        <div class="col-12 col-md-8"><input type="text" name="snippet" class="form-control form-control-sm" placeholder="Description/Snippet" required></div>
                        <div class="col-12 col-md-4"><input type="text" name="category" class="form-control form-control-sm" placeholder="Category" required></div>
                    </div>
                    <button type="submit" class="btn btn-primary btn-sm rounded-pill fw-bold w-100">Crawl & Index Link</button>
                </form>
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
    """ + get_footer("home")

# -------------------------------------------------------------
# 📌 HELPER ROUTES (BOOKMARKS, HISTORY, CLEAR DATA)
# -------------------------------------------------------------
@app.route("/add_bookmark")
def add_bookmark():
    username = session.get("username", "Guest")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO bookmarks (username, title, url, timestamp) VALUES (?, 'Bharat Search', 'https://bharat.app', ?)", (username, now_str))
    conn.commit()
    conn.close()
    return redirect("/bookmarks")

@app.route("/bookmarks")
def bookmarks():
    username = session.get("username", "Guest")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT title, url, timestamp FROM bookmarks WHERE username = ? ORDER BY id DESC", (username,))
    rows = cursor.fetchall()
    conn.close()
    b_html = "".join([f'<li class="list-group-item d-flex justify-content-between"><span>⭐ {r[0]}</span><small class="text-muted">{r[2][:10]}</small></li>' for r in rows]) if rows else '<li class="list-group-item text-center text-muted py-3">कोई बुकमार्क नहीं है।</li>'
    return get_html_header() + f'<div class="container mt-4 mb-5" style="max-width:600px;"><h5 class="fw-bold mb-3"><i class="bi bi-star-fill text-warning me-2"></i>Bookmarked Pages</h5><ul class="list-group shadow-sm rounded-4 overflow-hidden">{b_html}</ul></div>' + get_footer("home")

@app.route("/clear_browsing_data")
def clear_browsing_data():
    username = session.get("username", "Guest")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM search_history WHERE username = ?", (username,))
    conn.commit()
    conn.close()
    session["tabs"] = [{"id": 1, "title": "New Tab", "query": "", "incognito": False}]
    session["active_tab"] = 1
    session.modified = True
    return get_html_header() + '<div class="container mt-5 text-center"><div class="alert alert-success rounded-4 p-4">✅ ब्राउज़िंग डेटा सफलता पूर्वक डिलीट कर दिया गया है!</div><a href="/" class="btn btn-primary rounded-pill px-4 fw-bold">Home</a></div>' + get_footer("home")

@app.route("/games")
def games():
    return redirect("/app_store")

@app.route("/converters")
def converters_hub():
    return get_html_header() + """
    <div class="container mt-4 mb-5" style="max-width: 750px;">
        <div class="text-center mb-4">
            <span class="badge bg-warning text-dark px-3 py-2 rounded-pill fw-bold">🚀 FREE FOR ALL USERS</span>
            <h3 class="fw-bold mt-2">Bharat AI Master Toolkit Suite</h3>
        </div>
        <div class="row g-3">
            <div class="col-12 col-md-6">
                <div class="card p-3 shadow-sm rounded-4 border bg-white h-100">
                    <h6 class="fw-bold text-primary"><i class="bi bi-file-earmark-pdf me-2"></i>JPG to PDF Converter</h6>
                    <form action="/convert_jpg_to_pdf" method="POST" enctype="multipart/form-data" class="mt-2">
                        <input type="file" name="image_file" accept="image/*" class="form-control form-control-sm mb-2" required>
                        <button type="submit" class="btn btn-primary btn-sm w-100 rounded-pill fw-bold">Convert to PDF</button>
                    </form>
                </div>
            </div>
        </div>
    </div>
    """ + get_footer("converters")

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
def research():
    return get_html_header() + """<div class="container mt-4 text-center">📚 Research Workspace</div>""" + get_footer("research")

@app.route("/privacy_center")
def privacy_center():
    return get_html_header() + """<div class="container mt-4 text-center">🛡️ Privacy Settings</div>""" + get_footer("home")

@app.route("/vip_tiers")
def vip_tiers():
    return get_html_header() + """<div class="container mt-4 text-center">👑 Subscription Tiers</div>""" + get_footer("vip")

@app.route("/chats", methods=["GET", "POST"])
def chats():
    return get_html_header() + """<div class="container mt-4 text-center">💬 Bharat Chat</div>""" + get_footer("chats")

@app.route("/my_history")
def my_history():
    username = session.get("username", "Guest")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT query, timestamp FROM search_history WHERE username = ? ORDER BY id DESC LIMIT 20", (username,))
    rows = cursor.fetchall()
    conn.close()
    h_html = "".join([f'<li class="list-group-item d-flex justify-content-between"><span>🔍 {r[0]}</span><small class="text-muted">{r[1]}</small></li>' for r in rows]) if rows else '<li class="list-group-item text-center text-muted py-3">कोई सर्च हिस्ट्री नहीं है।</li>'
    return get_html_header() + f'<div class="container mt-4 mb-5" style="max-width: 600px;"><h5 class="fw-bold mb-3"><i class="bi bi-clock-history me-2 text-warning"></i>Search History</h5><ul class="list-group shadow-sm rounded-4 overflow-hidden">{h_html}</ul></div>' + get_footer("home")

@app.route("/user_login", methods=["GET", "POST"])
def user_login():
    if request.method == "POST":
        username, password = request.form.get("username"), request.form.get("password")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        if not cursor.fetchone():
            try:
                cursor.execute("INSERT INTO users (username, password, tier) VALUES (?, ?, 'Free')", (username, password))
                conn.commit()
            except Exception: pass
        session.permanent = True
        session["user_logged"] = True
        session["username"] = username
        conn.close()
        return redirect("/")

    return get_html_header() + """
    <div class="container mt-5" style="max-width: 400px;">
        <form method="POST" class="bg-white p-4 rounded-4 shadow-sm border">
            <h4 class="mb-3 text-center fw-bold text-primary">User Sign In / Register</h4>
            <input type="text" name="username" class="form-control mb-3" placeholder="Username" required>
            <input type="password" name="password" class="form-control mb-3" placeholder="Password" required>
            <button type="submit" class="btn btn-primary w-100 rounded-pill fw-bold">Login</button>
        </form>
    </div>
    """ + get_footer("home")

@app.route("/owner_login", methods=["GET", "POST"])
def owner_login():
    if request.method == "POST":
        if request.form.get("username") == OWNER_USERNAME and request.form.get("password") == OWNER_PASSWORD:
            session.permanent = True
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

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# -------------------------------------------------------------
# 🚀 DYNAMIC PORT BINDING FOR RENDER & LOCAL HOST
# -------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=True)
