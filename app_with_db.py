import io
import os
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

# 🤖 NEW VECTOR SEARCH ENGINE IMPORT
from engine import bharat_engine, sync_db_to_vector_engine

# -------------------------------------------------------------
# 🔑 CONFIGURATION & CONSTANTS
# -------------------------------------------------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")
YOUR_UPI_ID = os.environ.get("YOUR_UPI_ID", "giriji5626@okaxis")
YOUR_UPI_NAME = os.environ.get("YOUR_UPI_NAME", "Sandesh Giri")
VIP_PRICE = 49
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

def is_safe_query(query):
    query_lower = query.lower()
    for word in BLOCKED_KEYWORDS:
        if word in query_lower:
            return False
    return True

# -------------------------------------------------------------
# 🗄️ DATABASE INITIALIZATION & MASTER SEEDER
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
            is_premium INTEGER DEFAULT 0,
            vip_expires_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payment_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            utr_number TEXT UNIQUE,
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
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT,
            receiver TEXT,
            message TEXT,
            timestamp TEXT,
            is_read INTEGER DEFAULT 0
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
    # Synchronize Database to Vector Search Brain
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

def is_user_premium():
    if session.get("owner_logged"):
        return True
    username = session.get("username")
    if not username:
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT is_premium, vip_expires_at FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()

    if not row or not row[0]:
        return False

    expires_at_str = row[1]
    if expires_at_str:
        try:
            expires_at = datetime.strptime(expires_at_str, "%Y-%m-%d %H:%M:%S")
            if datetime.now() > expires_at:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET is_premium = 0 WHERE username = ?", (username,))
                conn.commit()
                conn.close()
                return False
        except ValueError:
            pass

    return True

# -------------------------------------------------------------
# 🔍 SEARCH SUGGESTIONS API
# -------------------------------------------------------------
@app.route("/api/suggestions")
def suggestions():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    results = []
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        search_kw = f"%{q}%"
        cursor.execute("SELECT DISTINCT title FROM local_search_index WHERE title LIKE ? OR category LIKE ? LIMIT 6", (search_kw, search_kw))
        rows = cursor.fetchall()
        results = [r[0] for r in rows]
        conn.close()
    except Exception:
        pass

    return jsonify(results)

# -------------------------------------------------------------
# 📰 UNLIMITED NEWS FEED
# -------------------------------------------------------------
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
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        resp = requests.get(rss_url, headers=headers, timeout=6)
        if resp.status_code == 200:
            root = ET.fromstring(resp.content)
            for item in root.findall(".//item"):
                title = item.find("title").text if item.find("title") is not None else "Bharat Live News"
                link = item.find("link").text if item.find("link") is not None else "#"
                pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
                description = item.find("description").text if item.find("description") is not None else ""
                
                img_url = ""
                if description:
                    soup = BeautifulSoup(description, "html.parser")
                    img_tag = soup.find("img")
                    if img_tag and img_tag.get("src"):
                        img_url = img_tag["src"]

                parsed = urlparse(link)
                favicon_url = f"https://www.google.com/s2/favicons?domain={parsed.netloc}&sz=128"

                news_items.append({
                    "title": title,
                    "link": link,
                    "date": pub_date[:16] if pub_date else "Live",
                    "image": img_url if img_url else favicon_url,
                    "source": parsed.netloc.replace("www.", "")
                })
    except Exception:
        pass
        
    return news_items

# -------------------------------------------------------------
# 🎨 HEADER & NAVIGATION MENUS
# -------------------------------------------------------------
def get_html_header():
    premium = is_user_premium()
    is_owner = session.get("owner_logged", False)
    username = session.get("username", "Owner" if is_owner else "Guest User")
    
    adsense_script = """
    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-6514818403683886" crossorigin="anonymous"></script>
    """ if not premium else "<!-- VIP Member: Ads Disabled -->"

    badge_label = "👑 OWNER" if is_owner else ("👑 VIP MEMBER" if premium else "FREE USER")
    badge_class = "bg-danger" if is_owner else ("bg-warning text-dark" if premium else "bg-secondary")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Bharat AI Universal SuperApp Engine</title>
    {adsense_script}
    <link rel="manifest" href="/manifest.json">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css">
    <meta name="theme-color" content="#FF9933">
    <style>
        :root {{ --bg-color: #fff9f2; --text-color: #202124; --card-bg: rgba(255, 255, 255, 0.95); --border-color: #f1d3b3; }}
        body.dark-mode {{ --bg-color: #121212; --text-color: #e8eaed; --card-bg: rgba(30, 30, 30, 0.95); --border-color: #3c4043; }}
        html, body {{ height: 100%; margin: 0; background-color: var(--bg-color); color: var(--text-color); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; transition: background 0.3s, color 0.3s; }}
        body {{ padding-bottom: 75px; }}
        .ram-mandir-bg {{ background-image: linear-gradient(to bottom, rgba(255, 243, 230, 0.88), rgba(255, 230, 204, 0.95)), url('https://upload.wikimedia.org/wikipedia/commons/e/e0/Ram_Mandir_Ayodhya.jpg'); background-size: cover; background-position: center; min-height: 100vh; }}
        body.dark-mode .ram-mandir-bg {{ background-image: linear-gradient(to bottom, rgba(18, 18, 18, 0.90), rgba(20, 20, 20, 0.96)), url('https://upload.wikimedia.org/wikipedia/commons/e/e0/Ram_Mandir_Ayodhya.jpg'); }}
        .top-bar-chrome {{ display: flex; justify-content: space-between; align-items: center; padding: 12px 18px; }}
        .creator-badge {{ font-size: 13px; font-weight: 600; color: #d96b00; display: flex; align-items: center; gap: 4px; }}
        .top-actions {{ display: flex; align-items: center; gap: 10px; }}
        .icon-btn {{ background: none; border: none; font-size: 22px; color: #d96b00; cursor: pointer; text-decoration: none; padding: 4px; }}
        .bharat-logo {{ font-size: 52px; font-weight: 700; letter-spacing: -1.5px; margin-top: 10px; }}
        
        .google-search-container {{ max-width: 580px; width: 92%; margin: 20px auto 16px auto; position: relative; }}
        .google-input {{ height: 54px; border-radius: 27px; padding-left: 52px; padding-right: 20px; border: 2px solid #ffaa44; background: var(--card-bg); color: var(--text-color); box-shadow: 0 4px 12px rgba(255, 153, 51, 0.2); font-size: 16px; }}
        .search-left-icon {{ position: absolute; left: 18px; top: 17px; color: #e67300; font-size: 18px; z-index: 10; }}
        .suggestions-box {{ position: absolute; top: 58px; left: 0; right: 0; background: #fff; border-radius: 16px; box-shadow: 0 8px 24px rgba(0,0,0,0.15); border: 1px solid #ffe0b2; z-index: 9999; display: none; text-align: left; overflow: hidden; }}
        .suggestion-item {{ padding: 12px 20px; cursor: pointer; font-size: 14px; border-bottom: 1px solid #fff3e0; display: flex; align-items: center; gap: 10px; color: #333; }}
        .suggestion-item:hover {{ background: #fff8e1; }}

        .bottom-nav-bar {{ position: fixed; bottom: 0; left: 0; right: 0; background: var(--bg-color); border-top: 1px solid var(--border-color); display: flex; justify-content: space-around; padding: 8px 0; z-index: 9998; transition: transform 0.2s ease-in-out; }}
        
        @media (max-height: 500px) {{
            .bottom-nav-bar {{ display: none !important; }}
            body {{ padding-bottom: 0px !important; }}
        }}
        .hide-nav {{ transform: translateY(100%); }}
        .news-card {{ background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 16px; }}
        .nav-link-item {{ text-decoration: none; color: #5f6368; font-size: 11px; text-align: center; display: flex; flex-direction: column; align-items: center; flex: 1; }}
        .nav-link-item.active {{ color: #ff7700; font-weight: 600; }}
        .ai-link-btn {{ display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; background: #f0f7ff; color: #0d6efd; border: 1px solid #b6d4fe; border-radius: 20px; font-size: 12px; font-weight: 600; text-decoration: none; margin: 4px 4px 4px 0; transition: all 0.2s; }}
        .ai-link-btn:hover {{ background: #0d6efd; color: #fff; }}
    </style>
</head>
<body>

<div class="top-bar-chrome">
    <div class="creator-badge">🚀 <b>Bharat AI OS</b> <span class="badge {badge_class} rounded-pill ms-1">{badge_label}</span></div>
    
    <div class="top-actions">
        <a href="/chats" class="icon-btn position-relative" title="Bharat Chat">
            <i class="bi bi-chat-dots-fill text-primary"></i>
        </a>

        <div class="dropdown">
            <button class="icon-btn" type="button" data-bs-toggle="dropdown"><i class="bi bi-three-dots-vertical"></i></button>
            <ul class="dropdown-menu dropdown-menu-end p-2 shadow-lg" style="width: 230px; border-radius: 16px;">
                <li><a class="dropdown-item rounded-3 py-2" href="/"><i class="bi bi-plus-lg me-2 text-primary"></i> New Tab</a></li>
                <li><a class="dropdown-item rounded-3 py-2" href="/my_history"><i class="bi bi-clock-history me-2 text-success"></i> History</a></li>
                <li><a class="dropdown-item rounded-3 py-2" href="/games"><i class="bi bi-controller me-2 text-danger"></i> Games Arcade</a></li>
                <li><a class="dropdown-item rounded-3 py-2" href="/converters"><i class="bi bi-gear-wide-connected me-2 text-warning"></i> VIP Tools</a></li>
                <li><hr class="dropdown-divider"></li>
                <li><button class="dropdown-item rounded-3 py-2" onclick="toggleDarkMode()"><i class="bi bi-moon-stars me-2 text-info"></i> Dark Mode Toggle</button></li>
                <li><a class="dropdown-item rounded-3 py-2" href="/remove_ads"><i class="bi bi-gem me-2 text-warning"></i> VIP Club (₹49)</a></li>
            </ul>
        </div>

        <div class="dropdown">
            <button class="icon-btn" type="button" data-bs-toggle="dropdown"><i class="bi bi-person-circle fs-3 text-warning"></i></button>
            <div class="dropdown-menu dropdown-menu-end p-3 shadow-lg" style="width: 280px; border-radius: 20px;">
                <div class="text-center pb-2 border-bottom mb-2">
                    <div class="fs-1 text-primary"><i class="bi bi-person-bounding-box"></i></div>
                    <h6 class="fw-bold mb-0">{username}</h6>
                    <span class="badge {badge_class} rounded-pill mt-1" style="font-size:10px;">{badge_label}</span>
                </div>
                <div class="list-group list-group-flush small">
                    <a href="/remove_ads" class="list-group-item list-group-item-action border-0 py-2 rounded-3 text-warning fw-bold"><i class="bi bi-crown me-2"></i> VIP Membership Status</a>
                    <a href="/my_history" class="list-group-item list-group-item-action border-0 py-2 rounded-3"><i class="bi bi-search me-2 text-secondary"></i> My Search Activity</a>
                    {f'<a href="/owner_dashboard" class="list-group-item list-group-item-action border-0 py-2 rounded-3 text-danger fw-bold"><i class="bi bi-speedometer2 me-2"></i> Owner Control Center</a>' if is_owner else ''}
                    <hr class="my-2">
                    {f'<a href="/logout" class="list-group-item list-group-item-action border-0 py-2 rounded-3 text-danger"><i class="bi bi-box-arrow-right me-2"></i> Sign Out</a>' if (session.get('user_logged') or is_owner) else '<a href="/user_login" class="list-group-item list-group-item-action border-0 py-2 rounded-3 text-success fw-bold"><i class="bi bi-box-arrow-in-right me-2"></i> Sign In / Register</a>'}
                </div>
            </div>
        </div>
    </div>
</div>
"""

def get_footer(active_tab="home"):
    return f"""
<div class="bottom-nav-bar" id="bottomNavBar">
    <a href="/" class="nav-link-item {'active' if active_tab == 'home' else ''}"><i class="bi bi-house-door-fill fs-5 d-block"></i>Home</a>
    <a href="/converters" class="nav-link-item {'active' if active_tab == 'converters' else ''}"><i class="bi bi-gear-wide-connected fs-5 d-block text-warning"></i>VIP Tools</a>
    <a href="/chats" class="nav-link-item {'active' if active_tab == 'chats' else ''}"><i class="bi bi-chat-dots-fill fs-5 d-block text-primary"></i>Chats</a>
    <a href="/games" class="nav-link-item {'active' if active_tab == 'games' else ''}"><i class="bi bi-controller fs-5 d-block text-success"></i>Games</a>
    <a href="/remove_ads" class="nav-link-item {'active' if active_tab == 'noads' else ''}"><i class="bi bi-gem fs-5 d-block text-danger"></i>VIP Club</a>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
    function toggleDarkMode() {{
        document.body.classList.toggle('dark-mode');
        localStorage.setItem('bharat_dark_mode', document.body.classList.contains('dark-mode') ? 'enabled' : 'disabled');
    }}
    if (localStorage.getItem('bharat_dark_mode') === 'enabled') {{
        document.body.classList.add('dark-mode');
    }}

    const searchInput = document.getElementById("searchInput");
    const suggestionsBox = document.getElementById("suggestionsBox");

    if (searchInput) {{
        searchInput.addEventListener("input", async function() {{
            const query = this.value.trim();
            if (query.length < 2) {{
                suggestionsBox.style.display = "none";
                return;
            }}
            try {{
                const res = await fetch('/api/suggestions?q=' + encodeURIComponent(query));
                const data = await res.json();
                if (data.length > 0) {{
                    suggestionsBox.innerHTML = data.map(item => 
                        `<div class="suggestion-item" onclick="selectSuggestion('${{item}}')"><i class="bi bi-search text-muted"></i> ${{item}}</div>`
                    ).join('');
                    suggestionsBox.style.display = "block";
                }} else {{
                    suggestionsBox.style.display = "none";
                }}
            }} catch(e) {{}}
        }});

        searchInput.addEventListener("focus", function() {{
            document.getElementById("bottomNavBar").classList.add("hide-nav");
        }});
        searchInput.addEventListener("blur", function() {{
            setTimeout(() => {{
                document.getElementById("bottomNavBar").classList.remove("hide-nav");
                suggestionsBox.style.display = "none";
            }}, 200);
        }});
    }}

    function selectSuggestion(text) {{
        searchInput.value = text;
        suggestionsBox.style.display = "none";
        searchInput.form.submit();
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
    
    news_html = ""
    for n in news_list:
        news_html += f"""
        <div class="col-12 col-md-6 mb-3">
            <a href="{n['link']}" target="_blank" class="text-decoration-none text-dark">
                <div class="card news-card p-3 h-100 shadow-sm border-0 rounded-4 d-flex flex-row align-items-center gap-3" style="background: rgba(255,255,255,0.95);">
                    <img src="{n['image']}" width="70" height="70" class="rounded-3" style="object-fit: cover;" alt="News Image" onerror="this.src='https://www.google.com/s2/favicons?domain=google.com&sz=128'">
                    <div class="flex-grow-1">
                        <h6 class="fw-bold mb-1 text-dark" style="font-size: 13px; line-height: 1.4;">{n['title']}</h6>
                        <div class="d-flex align-items-center gap-2">
                            <span class="badge bg-light text-secondary border fw-normal" style="font-size: 9px;">{n['source']}</span>
                            <small class="text-muted" style="font-size: 10px;">{n['date']}</small>
                        </div>
                    </div>
                </div>
            </a>
        </div>
        """

    cat_tabs = f"""
    <div class="d-flex gap-2 overflow-auto py-2 mb-3 no-scrollbar" style="white-space: nowrap;">
        <a href="/?category=top" class="btn btn-sm rounded-pill px-3 {'btn-warning fw-bold' if cat=='top' else 'btn-light border'}">🔥 मुख्य समाचार</a>
        <a href="/?category=national" class="btn btn-sm rounded-pill px-3 {'btn-warning fw-bold' if cat=='national' else 'btn-light border'}">🇮🇳 देश</a>
        <a href="/?category=tech" class="btn btn-sm rounded-pill px-3 {'btn-warning fw-bold' if cat=='tech' else 'btn-light border'}">💻 टेक्नोलॉजी</a>
        <a href="/?category=sports" class="btn btn-sm rounded-pill px-3 {'btn-warning fw-bold' if cat=='sports' else 'btn-light border'}">🏏 खेल</a>
        <a href="/?category=entertainment" class="btn btn-sm rounded-pill px-3 {'btn-warning fw-bold' if cat=='entertainment' else 'btn-light border'}">🎬 बॉलीवुड</a>
        <a href="/?category=business" class="btn btn-sm rounded-pill px-3 {'btn-warning fw-bold' if cat=='business' else 'btn-light border'}">💼 बिज़नेस</a>
    </div>
    """

    return get_html_header() + f"""
    <div class="ram-mandir-bg">
        <div class="container text-center pt-2">
            <div class="bharat-logo mb-1">
                <span style="color:#FF9933">B</span><span style="color:#000080">h</span><span style="color:#138808">arat</span> 🛕
            </div>
            <p class="fw-medium small mb-3" style="color: #d95100;">Universal Search Engine 🇮🇳</p>

            <form action="/search" method="GET" class="google-search-container">
                <i class="bi bi-search search-left-icon"></i>
                <input type="text" id="searchInput" name="q" class="form-control google-input" placeholder="Search apps, loans, finance or AI..." autocomplete="off" required autofocus>
                <div id="suggestionsBox" class="suggestions-box"></div>
            </form>

            <div class="container my-3" style="max-width: 680px;">
                <div class="row g-2 text-start">
                    <div class="col-6 col-md-3">
                        <a href="/search?q=Piramal+Finance" class="card p-2 text-decoration-none text-dark shadow-sm border text-center rounded-3 bg-white">
                            <div class="fs-4 text-success">🏦</div>
                            <div class="fw-bold small" style="font-size:12px;">Loans & Finance</div>
                        </a>
                    </div>
                    <div class="col-6 col-md-3">
                        <a href="/search?q=Khan+Academy" class="card p-2 text-decoration-none text-dark shadow-sm border text-center rounded-3 bg-white">
                            <div class="fs-4 text-primary">🎓</div>
                            <div class="fw-bold small" style="font-size:12px;">All Boards Study</div>
                        </a>
                    </div>
                    <div class="col-6 col-md-3">
                        <a href="/search?q=ChatGPT" class="card p-2 text-decoration-none text-dark shadow-sm border text-center rounded-3 bg-white">
                            <div class="fs-4 text-info">🤖</div>
                            <div class="fw-bold small" style="font-size:12px;">AI Tools</div>
                        </a>
                    </div>
                    <div class="col-6 col-md-3">
                        <a href="/search?q=Steam" class="card p-2 text-decoration-none text-dark shadow-sm border text-center rounded-3 bg-white">
                            <div class="fs-4 text-danger">🎮</div>
                            <div class="fw-bold small" style="font-size:12px;">Games Arcade</div>
                        </a>
                    </div>
                </div>
            </div>

            <div class="container text-start mt-2 mb-5" style="max-width: 720px;">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <h6 class="fw-bold text-muted mb-0"><i class="bi bi-newspaper text-warning me-2"></i>Discover Feed</h6>
                    <span class="badge bg-danger rounded-pill">LIVE</span>
                </div>
                
                {cat_tabs}

                <div class="row">
                    {news_html if news_html else '<div class="text-center text-muted py-4">खबरें लोड हो रही हैं...</div>'}
                </div>
            </div>
        </div>
    </div>
    """ + get_footer("home")

# -------------------------------------------------------------
# 🔍 UNIVERSAL SEARCH ROUTE (INTEGRATED WITH VECTOR AI ENGINE)
# -------------------------------------------------------------
@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    if not query or not is_safe_query(query):
        return redirect("/")

    if session.get("username"):
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("INSERT INTO search_history (username, query, timestamp) VALUES (?, ?, ?)", (session["username"], query, now))
            conn.commit()
            conn.close()
        except Exception:
            pass

    # 1. 🤖 VECTOR AI SEARCH ENGINE CALL (गूगल-बीटिंग स्मार्ट सर्च)
    vector_results = bharat_engine.search(query, top_k=5)
    
    local_html = ""
    knowledge_panel_html = ""
    
    if vector_results:
        first_item = vector_results[0]
        kp_title, kp_url, kp_snippet, kp_cat = first_item["title"], first_item["url"], first_item["snippet"], first_item["category"]
        kp_fav = f"https://www.google.com/s2/favicons?domain={urlparse(kp_url).netloc if kp_url else 'google.com'}&sz=128"
        
        knowledge_panel_html = f"""
        <div class="card p-3 mb-4 rounded-4 shadow-sm border-primary bg-primary bg-opacity-10 border-2">
            <div class="d-flex align-items-center gap-3 mb-2">
                <img src="{kp_fav}" width="40" height="40" class="rounded-3 shadow-sm" onerror="this.src='https://www.google.com/s2/favicons?domain=google.com'">
                <div>
                    <h5 class="fw-bold mb-0 text-primary">{kp_title}</h5>
                    <span class="badge bg-primary rounded-pill small" style="font-size:10px;">{kp_cat if kp_cat else 'AI Vector Match'}</span>
                </div>
            </div>
            <p class="small text-dark mb-2" style="line-height: 1.5;">{kp_snippet}</p>
            <a href="{kp_url}" target="_blank" class="btn btn-primary btn-sm rounded-pill fw-bold align-self-start"><i class="bi bi-box-arrow-up-right me-1"></i> Visit Official Site</a>
        </div>
        """

        local_html += f'<h6 class="fw-bold text-success mb-3"><i class="bi bg-cpu me-2"></i>Bharat Vector Smart Index ({len(vector_results)} Matches)</h6>'
        for item in vector_results:
            title, url, snippet, category = item["title"], item["url"], item["snippet"], item["category"]
            favicon = f"https://www.google.com/s2/favicons?domain={urlparse(url).netloc if url else 'google.com'}&sz=64"
            local_html += f"""
            <div class="card p-3 mb-3 border-0 shadow-sm rounded-4 bg-white">
                <div class="d-flex align-items-center gap-2 mb-1">
                    <img src="{favicon}" width="20" height="20" class="rounded" onerror="this.src='https://www.google.com/s2/favicons?domain=google.com'">
                    <span class="text-muted small" style="font-size: 11px;">{url}</span>
                    {f'<span class="badge bg-light text-dark border ms-auto">{category}</span>' if category else ''}
                </div>
                <h6 class="mb-1"><a href="{url}" target="_blank" class="text-primary text-decoration-none fw-bold">{title}</a></h6>
                <p class="text-muted small mb-0" style="font-size: 13px;">{snippet}</p>
            </div>
            """

    # 2. 🌐 लाइव वेब क्रॉल लिंक्स
    crawl_html = ""
    ai_links_from_web = []
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        crawl_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        resp = requests.get(crawl_url, headers=headers, timeout=5)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            snippets = soup.find_all("a", class_="result__snippet", limit=5)
            titles = soup.find_all("a", class_="result__a", limit=5)
            
            if titles:
                crawl_html += f'<h6 class="fw-bold text-primary my-3"><i class="bi bi-globe me-2"></i>Live Web Results</h6>'
                for i in range(len(titles)):
                    t = titles[i].get_text()
                    u = titles[i].get("href", "#")
                    s = snippets[i].get_text() if i < len(snippets) else "वेब से लाइव परिणाम..."
                    parsed_domain = urlparse(u).netloc
                    fav = f"https://www.google.com/s2/favicons?domain={parsed_domain}&sz=64" if parsed_domain else "https://www.google.com/s2/favicons?domain=google.com"

                    ai_links_from_web.append((t, u))

                    crawl_html += f"""
                    <div class="card p-3 mb-2 border-0 shadow-sm rounded-4 bg-white">
                        <div class="d-flex align-items-center gap-2 mb-1">
                            <img src="{fav}" width="18" height="18" class="rounded">
                            <span class="text-muted small" style="font-size: 11px;">{u[:40]}...</span>
                        </div>
                        <h6 class="mb-1"><a href="{u}" target="_blank" class="text-primary text-decoration-none fw-bold">{t}</a></h6>
                        <p class="text-muted small mb-0" style="font-size: 13px;">{s}</p>
                    </div>
                    """
    except Exception:
        crawl_html = ""

    # 3. 🤖 AI Overview Search
    ai_answer = ""
    ai_sources_html = ""
    if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_GEMINI_API_KEY_HERE":
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
            payload = {
                "contents": [{
                    "parts": [{"text": f"You are Bharat AI. Provide a clear, detailed summary with key facts for: {query}."}]
                }]
            }
            res = requests.post(url, json=payload, timeout=8)
            if res.status_code == 200:
                data = res.json()
                ai_answer = data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            ai_answer = ""

    if ai_answer:
        combined_links = []
        if vector_results:
            for item in vector_results[:3]:
                combined_links.append((item["title"], item["url"]))
        if ai_links_from_web:
            for item in ai_links_from_web[:3]:
                combined_links.append((item[0], item[1]))

        if combined_links:
            ai_sources_html = '<div class="mt-3 pt-3 border-top"><div class="fw-bold small text-secondary mb-2"><i class="bi bi-link-45deg"></i> आधिकारिक व उपयोगी लिंक्स (Official Web Links):</div>'
            for title, link_url in combined_links:
                domain_name = urlparse(link_url).netloc.replace("www.", "")
                ai_sources_html += f'<a href="{link_url}" target="_blank" class="ai-link-btn"><i class="bi bi-box-arrow-up-right"></i> {title[:25]}... ({domain_name})</a>'
            ai_sources_html += '</div>'

    # 4. ❓ Google-Style "People Also Ask"
    paa_html = f"""
    <div class="card p-3 my-4 border-0 shadow-sm rounded-4 bg-white">
        <h6 class="fw-bold text-dark mb-3"><i class="bi bi-question-circle-fill text-warning me-2"></i>People Also Ask (लोग यह भी पूछते हैं)</h6>
        <div class="accordion accordion-flush" id="paaAccordion">
            <div class="accordion-item border-bottom">
                <h2 class="accordion-header" id="headingOne">
                    <button class="accordion-button collapsed py-2 px-0 bg-transparent fw-medium small" type="button" data-bs-toggle="collapse" data-bs-target="#collapseOne">
                        {query} का उपयोग और मुख्य लाभ क्या हैं?
                    </button>
                </h2>
                <div id="collapseOne" class="accordion-collapse collapse" data-bs-parent="#paaAccordion">
                    <div class="accordion-body small text-muted px-0 py-2">
                        {query} मुख्य रूप से सही जानकारी, आधिकारिक सेवाओं और त्वरित सहायता के लिए उपयोग किया जाता है। ऊपर दिए गए लिंक्स पर क्लिक करके आप इसकी आधिकारिक वेबसाइट पर पहुँच सकते हैं।
                    </div>
                </div>
            </div>
            <div class="accordion-item border-bottom">
                <h2 class="accordion-header" id="headingTwo">
                    <button class="accordion-button collapsed py-2 px-0 bg-transparent fw-medium small" type="button" data-bs-toggle="collapse" data-bs-target="#collapseTwo">
                        {query} की आधिकारिक/Official Website कौन सी है?
                    </button>
                </h2>
                <div id="collapseTwo" class="accordion-collapse collapse" data-bs-parent="#paaAccordion">
                    <div class="accordion-body small text-muted px-0 py-2">
                        {query} की आधिकारिक वेबसाइट का लिंक ऊपर दिए गए <b>Bharat Master Index</b> और <b>Official Web Links</b> सेक्शन में नीले रंग के बटन में दिया गया है।
                    </div>
                </div>
            </div>
        </div>
    </div>
    """

    if not ai_answer:
        ai_answer = f"<b>{query}</b> से संबंधित सभी आधिकारिक लिंक्स ऊपर दिए गए परिणामों में उपलब्ध हैं।"

    return get_html_header() + f"""
    <div class="container mt-4 mb-5" style="max-width: 720px;">
        <form action="/search" method="GET" class="google-search-container mb-4">
            <i class="bi bi-search search-left-icon"></i>
            <input type="text" id="searchInput" name="q" value="{query}" class="form-control google-input" autocomplete="off" required>
            <div id="suggestionsBox" class="suggestions-box"></div>
        </form>

        <!-- 1. Knowledge Panel -->
        {knowledge_panel_html}

        <!-- 2. AI Overview Summary -->
        <div class="card p-4 rounded-4 shadow-sm border bg-white mb-4">
            <div class="d-flex align-items-center gap-2 mb-2">
                <span class="fs-4">🤖</span>
                <h6 class="fw-bold text-primary mb-0">Bharat AI Overview</h6>
            </div>
            <div style="line-height: 1.6; font-size: 14px; color: #333;">
                {ai_answer.replace('\n', '<br>')}
                {ai_sources_html}
            </div>
        </div>

        <!-- 3. People Also Ask -->
        {paa_html}

        <!-- 4. Indexed Vector Results -->
        {local_html}

        <!-- 5. Live Crawl Results -->
        {crawl_html}

        <div class="text-center mt-3">
            <a href="/" class="btn btn-outline-secondary btn-sm rounded-pill">Back to Home</a>
        </div>
    </div>
    """ + get_footer("home")

# -------------------------------------------------------------
# 👑 OWNER DASHBOARD
# -------------------------------------------------------------
@app.route("/owner_dashboard", methods=["GET", "POST"])
def owner_dashboard():
    if not session.get("owner_logged"): 
        return redirect("/owner_login")

    message = ""
    if request.method == "POST":
        form_type = request.form.get("form_type")

        if form_type == "add_link":
            title = request.form.get("title", "").strip()
            url = request.form.get("url", "").strip()
            snippet = request.form.get("snippet", "").strip()
            category = request.form.get("category", "General").strip()

            if title and url:
                try:
                    domain = urlparse(url).netloc
                    logo = f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT OR REPLACE INTO local_search_index (title, url, snippet, category, logo_url)
                        VALUES (?, ?, ?, ?, ?)
                    """, (title, url, snippet, category, logo))
                    conn.commit()
                    conn.close()
                    
                    # Also index in real-time into the AI Vector Engine!
                    bharat_engine.index_item(title, url, snippet, category)
                    
                    message = f"✅ नई लिंक सफलतापूर्वक Vector Engine और DB में इंडेक्स कर दी गई: <b>{title}</b>"
                except Exception as e:
                    message = f"⚠️ त्रुटि: {str(e)}"

        elif form_type == "payment_action":
            action = request.form.get("action")
            target_user = request.form.get("username")
            req_id = request.form.get("req_id")
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            if action == "approve":
                expiry_date = (datetime.now() + timedelta(days=VIP_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("UPDATE users SET is_premium = 1, vip_expires_at = ? WHERE username = ?", (expiry_date, target_user))
                cursor.execute("UPDATE payment_requests SET status = 'approved' WHERE id = ?", (req_id,))
                message = f"✅ Approved {target_user} for 90 Days VIP!"
            elif action == "reject":
                cursor.execute("UPDATE payment_requests SET status = 'rejected' WHERE id = ?", (req_id,))
                message = f"❌ Rejected payment request."
            conn.commit()
            conn.close()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, utr_number, status, timestamp FROM payment_requests ORDER BY id DESC")
    requests_list = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM local_search_index")
    total_indexed_count = cursor.fetchone()[0]
    conn.close()

    req_rows = "".join([f'<tr><td>{r[1]}</td><td><code>{r[2]}</code></td><td><span class="badge bg-warning">{r[3]}</span></td><td><form method="POST" class="d-inline"><input type="hidden" name="form_type" value="payment_action"><input type="hidden" name="req_id" value="{r[0]}"><input type="hidden" name="username" value="{r[1]}"><button name="action" value="approve" class="btn btn-sm btn-success py-0 me-1">Approve</button><button name="action" value="reject" class="btn btn-sm btn-danger py-0">Reject</button></form></td></tr>' for r in requests_list if r[3] == 'pending'])

    return get_html_header() + f"""
    <div class="container mt-4 mb-5" style="max-width: 850px;">
        <div class="bg-white p-4 rounded-4 shadow-sm border mb-4">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h4 class="fw-bold text-danger mb-0"><i class="bi bi-speedometer2 me-2"></i>Owner Control Center</h4>
                <span class="badge bg-primary rounded-pill px-3 py-2">Total Indexed Links: {total_indexed_count}</span>
            </div>
            
            {f'<div class="alert alert-info py-2 small mb-3">{message}</div>' if message else ''}

            <!-- 🌐 ADD CRAWL / CUSTOM WEBSITE LINK FORM -->
            <div class="card p-3 border-warning bg-light mb-4 rounded-4">
                <h6 class="fw-bold text-dark mb-2"><i class="bi bi-plus-circle-fill text-warning me-2"></i>Add New Crawl & Master Index Link</h6>
                <p class="text-muted small mb-3">यहाँ से आप सीधे कोई भी नई वेबसाइट, ऐप या फाइनेंस पोर्टल सर्च इंजन में जोड़ सकते हैं:</p>

                <form method="POST">
                    <input type="hidden" name="form_type" value="add_link">
                    <div class="row g-2 mb-2">
                        <div class="col-12 col-md-6">
                            <input type="text" name="title" class="form-control form-control-sm" placeholder="Site Title (e.g. Piramal Finance)" required>
                        </div>
                        <div class="col-12 col-md-6">
                            <input type="url" name="url" class="form-control form-control-sm" placeholder="Full URL (https://...)" required>
                        </div>
                    </div>
                    <div class="row g-2 mb-3">
                        <div class="col-12 col-md-8">
                            <input type="text" name="snippet" class="form-control form-control-sm" placeholder="Description/Snippet (Short info)" required>
                        </div>
                        <div class="col-12 col-md-4">
                            <input type="text" name="category" class="form-control form-control-sm" placeholder="Category (e.g. Finance/AI/Education)" required>
                        </div>
                    </div>
                    <button type="submit" class="btn btn-warning btn-sm rounded-pill fw-bold w-100"><i class="bi bi-cloud-upload me-1"></i> Add Link to Bharat Search Index</button>
                </form>
            </div>

            <h6 class="fw-bold text-dark mb-2"><i class="bi bi-credit-card me-2"></i>Pending VIP Payments (₹{VIP_PRICE})</h6>
            <div class="table-responsive">
                <table class="table table-bordered table-hover align-middle small">
                    <thead class="table-light">
                        <tr><th>User</th><th>UTR Number</th><th>Status</th><th>Action</th></tr>
                    </thead>
                    <tbody>
                        {req_rows if req_rows else '<tr><td colspan="4" class="text-center text-muted">No pending payment requests.</td></tr>'}
                    </tbody>
                </table>
            </div>

            <div class="text-center mt-3">
                <a href="/" class="btn btn-outline-secondary btn-sm rounded-pill">Back to Home</a>
            </div>
        </div>
    </div>
    """ + get_footer("home")

# -------------------------------------------------------------
# 💬 CHAT, GAMES, CONVERTERS & AUTH ROUTES
# -------------------------------------------------------------
@app.route("/chats", methods=["GET", "POST"])
def chats():
    username = session.get("username", "")
    if not username: return redirect("/user_login")
    message_sent = ""
    if request.method == "POST":
        receiver = request.form.get("receiver", "").strip()
        msg_text = request.form.get("message", "").strip()
        if receiver and msg_text:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("INSERT INTO messages (sender, receiver, message, timestamp) VALUES (?, ?, ?, ?)", (username, receiver, msg_text, now))
            conn.commit()
            conn.close()
            message_sent = "✅ मैसेज भेज दिया गया!"

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT sender, receiver, message, timestamp FROM messages WHERE sender = ? OR receiver = ? ORDER BY id DESC LIMIT 20", (username, username))
    chat_list = cursor.fetchall()
    conn.close()

    chat_rows = "".join([f'<li class="list-group-item d-flex justify-content-between align-items-start"><div><b>{c[0]} $\\rightarrow$ {c[1]}:</b> {c[2]}</div><small class="text-muted" style="font-size:10px;">{c[3][11:16]}</small></li>' for c in chat_list])

    return get_html_header() + f"""
    <div class="container mt-4 mb-5" style="max-width: 600px;">
        <div class="card p-4 rounded-4 shadow-sm border bg-white">
            <h4 class="fw-bold text-primary mb-3"><i class="bi bi-chat-dots-fill me-2"></i>Bharat Chat Hub</h4>
            {f'<div class="alert alert-success small py-2">{message_sent}</div>' if message_sent else ''}

            <form method="POST" class="mb-4">
                <div class="input-group mb-2">
                    <span class="input-group-text">To:</span>
                    <input type="text" name="receiver" class="form-control" placeholder="Username / Bharat AI" required>
                </div>
                <div class="input-group">
                    <input type="text" name="message" class="form-control" placeholder="Type a message..." required>
                    <button class="btn btn-primary" type="submit"><i class="bi bi-send-fill"></i> Send</button>
                </div>
            </form>

            <h6 class="fw-bold text-muted mb-2">Recent Messages</h6>
            <ul class="list-group list-group-flush rounded-3 small">
                {chat_rows if chat_rows else '<li class="list-group-item text-center text-muted py-3">No recent chats.</li>'}
            </ul>
        </div>
    </div>
    """ + get_footer("chats")

@app.route("/games")
def games():
    return get_html_header() + """
    <div class="container mt-4 mb-5" style="max-width: 600px;">
        <h4 class="fw-bold mb-3"><i class="bi bi-controller text-success me-2"></i>VIP Games Arcade</h4>
        <div class="row g-3">
            <div class="col-6"><div class="card p-4 text-center shadow-sm rounded-4 border">🚀 Space Runner</div></div>
            <div class="col-6"><div class="card p-4 text-center shadow-sm rounded-4 border">💡 Brain Quiz</div></div>
            <div class="col-6"><div class="card p-4 text-center shadow-sm rounded-4 border">🧩 Puzzle Master</div></div>
            <div class="col-6"><div class="card p-4 text-center shadow-sm rounded-4 border">🏹 Archer King</div></div>
        </div>
    </div>
    """ + get_footer("games")

@app.route("/converters")
def converters_hub():
    premium = is_user_premium()
    return get_html_header() + f"""
    <div class="container mt-4 mb-5" style="max-width: 700px;">
        <div class="text-center mb-4">
            <span class="badge bg-warning text-dark px-3 py-2 rounded-pill fw-bold">👑 VIP TOOLKIT SUITE</span>
            <h3 class="fw-bold mt-2">All-In-One File Converter</h3>
        </div>
        <div class="row g-3">
            <div class="col-12 col-md-6">
                <div class="card p-3 shadow-sm rounded-4 border bg-white">
                    <h6>JPG to PDF Converter</h6>
                    <form action="/convert_jpg_to_pdf" method="POST" enctype="multipart/form-data">
                        <input type="file" name="image_file" accept="image/*" class="form-control form-control-sm mb-2" required {'disabled' if not premium else ''}>
                        <button type="submit" class="btn btn-primary btn-sm w-100 rounded-pill" {'disabled' if not premium else ''}>Convert to PDF</button>
                    </form>
                </div>
            </div>
            <div class="col-12 col-md-6">
                <div class="card p-3 shadow-sm rounded-4 border bg-white">
                    <h6>PNG / WEBP to JPG</h6>
                    <form action="/convert_image_format" method="POST" enctype="multipart/form-data">
                        <input type="file" name="image_file" accept="image/*" class="form-control form-control-sm mb-2" required {'disabled' if not premium else ''}>
                        <button type="submit" class="btn btn-primary btn-sm w-100 rounded-pill" {'disabled' if not premium else ''}>Convert Format</button>
                    </form>
                </div>
            </div>
        </div>
    </div>
    """ + get_footer("converters")

@app.route("/convert_jpg_to_pdf", methods=["POST"])
def convert_jpg_to_pdf():
    if not is_user_premium(): return redirect("/remove_ads")
    if not Image: return "Image library missing."
    file = request.files.get('image_file')
    if not file: return redirect("/converters")
    try:
        image = Image.open(file.stream)
        if image.mode != 'RGB': image = image.convert('RGB')
        pdf_bytes = io.BytesIO()
        image.save(pdf_bytes, format='PDF')
        pdf_bytes.seek(0)
        return send_file(pdf_bytes, mimetype='application/pdf', as_attachment=True, download_name='converted_bharat.pdf')
    except Exception as e:
        return f"Error: {str(e)}"

@app.route("/convert_image_format", methods=["POST"])
def convert_image_format():
    if not is_user_premium(): return redirect("/remove_ads")
    if not Image: return "Image library missing."
    file = request.files.get('image_file')
    if not file: return redirect("/converters")
    try:
        image = Image.open(file.stream)
        if image.mode in ("RGBA", "P"): image = image.convert("RGB")
        img_bytes = io.BytesIO()
        image.save(img_bytes, format='JPEG', quality=95)
        img_bytes.seek(0)
        return send_file(img_bytes, mimetype='image/jpeg', as_attachment=True, download_name='converted_bharat.jpg')
    except Exception as e:
        return f"Error: {str(e)}"

@app.route("/remove_ads", methods=["GET", "POST"])
def remove_ads():
    is_owner = session.get("owner_logged", False)
    premium = is_user_premium()
    msg = ""
    username = session.get("username", "Owner" if is_owner else "")

    if request.method == "POST":
        utr_no = request.form.get("utr_number", "").strip()
        if utr_no and len(utr_no) >= 10:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            try:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("INSERT INTO payment_requests (username, utr_number, status, timestamp) VALUES (?, ?, 'pending', ?)", (username, utr_no, now))
                conn.commit()
                msg = "✅ UTR सबमिट हो गई है! Owner वेरिफिकेशन के बाद एक्टिवेट होगा।"
            except sqlite3.IntegrityError:
                msg = "⚠️ यह UTR पहले ही सबमिट किया जा चुका है!"
            conn.close()

    upi_qr_url = f"https://chart.googleapis.com/chart?cht=qr&chs=250x250&chl=upi://pay?pa={YOUR_UPI_ID}&pn={quote_plus(YOUR_UPI_NAME)}&am={VIP_PRICE}&cu=INR"

    return get_html_header() + f"""
    <div class="container mt-4 mb-5" style="max-width: 500px;">
        <div class="bg-white p-4 rounded-4 shadow-sm border text-center">
            <h3 class="fw-bold">Bharat AI VIP Club</h3>
            <div class="card p-3 my-3 bg-light border-warning">
                <div class="display-5 fw-bold text-danger mb-1">₹{VIP_PRICE}</div>
                <small class="text-muted mb-3">वैधता: <b>90 दिन</b></small>
                <img src="{upi_qr_url}" alt="UPI QR" class="mx-auto my-2" style="width:180px;">
                <form method="POST">
                    <input type="text" name="utr_number" class="form-control text-center rounded-pill my-2" placeholder="Enter 12-digit UTR No." required>
                    <button type="submit" class="btn btn-warning w-100 rounded-pill fw-bold">Submit UTR</button>
                </form>
            </div>
        </div>
    </div>
    """ + get_footer("noads")

@app.route("/my_history")
def my_history():
    username = session.get("username", "")
    if not username: return redirect("/user_login")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT query, timestamp FROM search_history WHERE username = ? ORDER BY id DESC LIMIT 20", (username,))
    rows = cursor.fetchall()
    conn.close()
    history_html = "".join([f'<li class="list-group-item d-flex justify-content-between"><span>{r[0]}</span><small class="text-muted">{r[1]}</small></li>' for r in rows])
    return get_html_header() + f'<div class="container mt-4 mb-5" style="max-width: 600px;"><ul class="list-group shadow-sm">{history_html}</ul></div>' + get_footer("history")

@app.route("/user_login", methods=["GET", "POST"])
def user_login():
    if request.method == "POST":
        username, password = request.form.get("username"), request.form.get("password")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = cursor.fetchone()
        if not user:
            try:
                cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
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

@app.route("/about")
def about():
    return get_html_header() + '<div class="container mt-5 text-center mb-5"><div class="bg-white p-4 rounded-4 border shadow-sm"><h4>Bharat AI Engine</h4><p>Created by <b>Aman Giri</b></p></div></div>' + get_footer("home")

if __name__ == "__main__":
    app.run(debug=True, port=5000)
