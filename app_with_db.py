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

# 🤖 ADVANCED SEARCH ENGINE IMPORT
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
    # Convert bold **text** to <b>text</b>
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    # Convert italic *text* to <i>text</i>
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    # Convert newlines to <br>
    return text.replace('\n', '<br>')

# -------------------------------------------------------------
# 🗄️ DATABASE INITIALIZATION
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

    # Safety Column Checks
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
# 🔍 SUGGESTIONS & NEWS
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
# 🎨 HEADER & FOOTER ENGINE
# -------------------------------------------------------------
def get_html_header():
    tier_name, tier_info = get_user_tier_info()
    is_owner = session.get("owner_logged", False)
    username = session.get("username", "Owner" if is_owner else "Guest User")
    
    badge_label = "👑 OWNER" if is_owner else tier_info["badge"]
    badge_class = "bg-danger" if is_owner else tier_info["cls"]

    adsense_script = """<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-6514818403683886" crossorigin="anonymous"></script>""" if tier_name == "Free" else "<!-- VIP Member: Ads Disabled -->"

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
        html, body {{ height: 100%; margin: 0; background-color: var(--bg-color); color: var(--text-color); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; transition: background 0.3s, color 0.3s; }}
        body {{ padding-bottom: 75px; }}
        .ram-mandir-bg {{ background-image: linear-gradient(to bottom, rgba(255, 243, 230, 0.88), rgba(255, 230, 204, 0.95)), url('https://upload.wikimedia.org/wikipedia/commons/e/e0/Ram_Mandir_Ayodhya.jpg'); background-size: cover; background-position: center; min-height: 100vh; }}
        body.dark-mode .ram-mandir-bg {{ background-image: linear-gradient(to bottom, rgba(18, 18, 18, 0.90), rgba(20, 20, 20, 0.96)), url('https://upload.wikimedia.org/wikipedia/commons/e/e0/Ram_Mandir_Ayodhya.jpg'); }}
        .top-bar-chrome {{ display: flex; justify-content: space-between; align-items: center; padding: 12px 18px; }}
        .creator-badge {{ font-size: 13px; font-weight: 600; color: #d96b00; display: flex; align-items: center; gap: 4px; }}
        .top-actions {{ display: flex; align-items: center; gap: 10px; }}
        .icon-btn {{ background: none; border: none; font-size: 22px; color: #d96b00; cursor: pointer; text-decoration: none; padding: 4px; }}
        .bharat-logo {{ font-size: 52px; font-weight: 700; letter-spacing: -1.5px; margin-top: 10px; }}
        .google-search-container {{ max-width: 620px; width: 92%; margin: 15px auto; position: relative; }}
        .google-input {{ height: 52px; border-radius: 26px; padding-left: 48px; border: 2px solid #ffaa44; background: var(--card-bg); color: var(--text-color); box-shadow: 0 4px 12px rgba(255, 153, 51, 0.2); font-size: 15px; }}
        .search-left-icon {{ position: absolute; left: 18px; top: 16px; color: #e67300; font-size: 18px; z-index: 10; }}
        .suggestions-box {{ position: absolute; top: 58px; left: 0; right: 0; background: #fff; border-radius: 16px; box-shadow: 0 8px 24px rgba(0,0,0,0.15); border: 1px solid #ffe0b2; z-index: 9999; display: none; text-align: left; overflow: hidden; }}
        .suggestion-item {{ padding: 12px 20px; cursor: pointer; font-size: 14px; border-bottom: 1px solid #fff3e0; display: flex; align-items: center; gap: 10px; color: #333; }}
        .bottom-nav-bar {{ position: fixed; bottom: 0; left: 0; right: 0; background: var(--bg-color); border-top: 1px solid var(--border-color); display: flex; justify-content: space-around; padding: 8px 0; z-index: 9998; transition: transform 0.2s ease-in-out; }}
        .nav-link-item {{ text-decoration: none; color: #5f6368; font-size: 11px; text-align: center; flex: 1; }}
        .nav-link-item.active {{ color: #ff7700; font-weight: 600; }}
        
        @media (max-height: 550px) {{
            .bottom-nav-bar {{ display: none !important; }}
            body {{ padding-bottom: 0px !important; }}
        }}
        .bottom-nav-bar.keyboard-open {{ display: none !important; }}
        .no-scrollbar::-webkit-scrollbar {{ display: none; }}
    </style>
</head>
<body>

<div class="top-bar-chrome">
    <div class="creator-badge">🚀 <b>Bharat OS</b> <span class="badge {badge_class} rounded-pill ms-1">{badge_label}</span></div>
    <div class="top-actions">
        <a href="/chats" class="icon-btn" title="Bharat Chat"><i class="bi bi-chat-dots-fill text-primary"></i></a>
        <a href="/vip_tiers" class="icon-btn" title="VIP Tiers"><i class="bi bi-gem-fill text-warning"></i></a>
        <div class="dropdown">
            <button class="icon-btn" type="button" data-bs-toggle="dropdown"><i class="bi bi-three-dots-vertical"></i></button>
            <ul class="dropdown-menu dropdown-menu-end p-2 shadow-lg" style="width: 230px; border-radius: 16px;">
                <li><a class="dropdown-item rounded-3 py-2" href="/"><i class="bi bi-plus-lg me-2 text-primary"></i> New Search</a></li>
                <li><a class="dropdown-item rounded-3 py-2" href="/research"><i class="bi bi-journal-check me-2 text-info"></i> Research Workspace</a></li>
                <li><a class="dropdown-item rounded-3 py-2" href="/privacy_center"><i class="bi bi-shield-lock me-2 text-success"></i> Privacy Center</a></li>
                <li><a class="dropdown-item rounded-3 py-2" href="/my_history"><i class="bi bi-clock-history me-2 text-secondary"></i> History</a></li>
                <li><a class="dropdown-item rounded-3 py-2" href="/games"><i class="bi bi-controller me-2 text-danger"></i> Games Arcade</a></li>
                <li><a class="dropdown-item rounded-3 py-2" href="/converters"><i class="bi bi-gear-wide-connected me-2 text-warning"></i> VIP Tools</a></li>
                <li><hr class="dropdown-divider"></li>
                <li><button class="dropdown-item rounded-3 py-2" onclick="toggleDarkMode()"><i class="bi bi-moon-stars me-2 text-info"></i> Toggle Theme</button></li>
                <li><a class="dropdown-item rounded-3 py-2 fw-bold text-danger" href="/vip_tiers"><i class="bi bi-crown me-2"></i> Subscription Tiers</a></li>
            </ul>
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
"""

def get_footer(active_tab="home"):
    return f"""
<div class="bottom-nav-bar" id="bottomNavBar">
    <a href="/" class="nav-link-item {'active' if active_tab == 'home' else ''}"><i class="bi bi-house-door-fill fs-5 d-block"></i>Home</a>
    <a href="/research" class="nav-link-item {'active' if active_tab == 'research' else ''}"><i class="bi bi-journal-bookmark fs-5 d-block text-info"></i>Research</a>
    <a href="/converters" class="nav-link-item {'active' if active_tab == 'converters' else ''}"><i class="bi bi-gear-wide-connected fs-5 d-block text-warning"></i>VIP Tools</a>
    <a href="/chats" class="nav-link-item {'active' if active_tab == 'chats' else ''}"><i class="bi bi-chat-dots-fill fs-5 d-block text-primary"></i>Chats</a>
    <a href="/vip_tiers" class="nav-link-item {'active' if active_tab == 'vip' else ''}"><i class="bi bi-gem fs-5 d-block text-danger"></i>VIP Club</a>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
    function toggleDarkMode() {{
        document.body.classList.toggle('dark-mode');
        localStorage.setItem('bharat_dark_mode', document.body.classList.contains('dark-mode') ? 'enabled' : 'disabled');
    }}
    if (localStorage.getItem('bharat_dark_mode') === 'enabled') {{ document.body.classList.add('dark-mode'); }}

    const navBar = document.getElementById("bottomNavBar");
    
    if (window.visualViewport) {{
        window.visualViewport.addEventListener('resize', () => {{
            if (window.visualViewport.height < window.innerHeight - 150) {{
                if (navBar) navBar.classList.add("keyboard-open");
            }} else {{
                if (navBar) navBar.classList.remove("keyboard-open");
            }}
        }});
    }}

    const searchInput = document.getElementById("searchInput");
    const suggestionsBox = document.getElementById("suggestionsBox");

    if (searchInput) {{
        searchInput.addEventListener("input", async function() {{
            const query = this.value.trim();
            if (query.length < 2) {{ suggestionsBox.style.display = "none"; return; }}
            try {{
                const res = await fetch('/api/suggestions?q=' + encodeURIComponent(query));
                const data = await res.json();
                if (data.length > 0) {{
                    suggestionsBox.innerHTML = data.map(item => `<div class="suggestion-item" onclick="selectSuggestion('${{item}}')"><i class="bi bi-search text-muted"></i> ${{item}}</div>`).join('');
                    suggestionsBox.style.display = "block";
                }} else {{ suggestionsBox.style.display = "none"; }}
            }} catch(e) {{}}
        }});
    }}

    function selectSuggestion(text) {{
        if (searchInput) searchInput.value = text;
        if (suggestionsBox) suggestionsBox.style.display = "none";
        if (searchInput && searchInput.form) searchInput.form.submit();
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

            <form action="/search" method="GET" class="google-search-container">
                <i class="bi bi-search search-left-icon"></i>
                <input type="text" id="searchInput" name="q" class="form-control google-input" placeholder="सर्च करें, फाइल्स ढूंढें या AI से पूछें..." autocomplete="off" required>
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
                    <div class="col-6 col-md-3"><a href="/search?q=Piramal+Finance" class="card p-2 text-decoration-none text-dark shadow-sm text-center rounded-3 bg-white"><div class="fs-4 text-success">🏦</div><div class="fw-bold small" style="font-size:12px;">Loans & Finance</div></a></div>
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
# 🔍 SEARCH ROUTE (PRODUCTION-READY & ERROR-FREE)
# -------------------------------------------------------------
@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    file_type = request.args.get("file_type", "all")
    country = request.args.get("country", "all")
    mode = request.args.get("mode", "fast")

    if not query or not is_safe_query(query): 
        return redirect("/")

    # 1. 💾 Save Search Query to User History
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

    # 2. Execute Super Engine Pipeline
    engine_data = bharat_engine.process_super_search(query)
    intent_data = engine_data.get("intent", {})
    kg_card = engine_data.get("knowledge_card")
    vector_results = engine_data.get("results", [])

    # Knowledge Panel HTML
    kg_html = ""
    if kg_card:
        kg_html = f"""
        <div class="card p-3 mb-4 rounded-4 shadow-sm border-warning bg-warning bg-opacity-10">
            <span class="badge bg-warning text-dark align-self-start mb-2">🇮🇳 {kg_card['category']}</span>
            <h5 class="fw-bold text-dark">{kg_card['title']}</h5>
            <p class="small mb-1"><b>विभाग:</b> {kg_card['department']}</p>
            <p class="small mb-2"><b>लाभ:</b> {kg_card['benefits']}</p>
            <a href="{kg_card['official_website']}" target="_blank" class="btn btn-warning btn-sm rounded-pill fw-bold">आधिकारिक पोर्टल पर जाएँ</a>
        </div>
        """

    # 3. Process Smart Local Vector Results
    local_html = ""
    for item in vector_results:
        title, url, snippet, category = item["title"], item["url"], item["snippet"], item["category"]
        favicon = f"https://www.google.com/s2/favicons?domain={urlparse(url).netloc if url else 'google.com'}&sz=64"
        local_html += f"""
        <div class="card p-3 mb-2 border-0 shadow-sm rounded-4 bg-white">
            <div class="d-flex align-items-center gap-2 mb-1">
                <img src="{favicon}" width="18" height="18" class="rounded" alt="icon">
                <span class="text-muted small" style="font-size: 11px;">{url}</span>
            </div>
            <h6 class="mb-1"><a href="{url}" target="_blank" class="text-primary text-decoration-none fw-bold">{title}</a></h6>
            <p class="text-muted small mb-0" style="font-size: 13px;">{snippet}</p>
        </div>
        """

    # 4. Generate Robust AI Answer (With Fallback)
    prompt_prefix = "Explain like I'm 5 years old:" if mode == "eli5" else ("Provide a detailed academic analysis for:" if mode == "deep" else "Provide a concise summary for:")
    ai_answer = ""

    if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_GEMINI_API_KEY_HERE":
        try:
            # Note: Endpoint updated for standard REST generation
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
            payload = {
                "contents": [{"parts": [{"text": f"{prompt_prefix} {query}. Reply in clear Hindi or simple English."}]}]
            }
            res = requests.post(url, json=payload, timeout=7)
            if res.status_code == 200:
                json_data = res.json()
                raw_answer = json_data["candidates"][0]["content"]["parts"][0]["text"]
                ai_answer = format_markdown_to_html(raw_answer)
            else:
                ai_answer = f"⚠️ AI सेवा प्रतिक्रिया देने में असमर्थ रही (Status: {res.status_code})। कृपया अपनी API Key की जाँच करें।"
        except Exception as e:
            ai_answer = f"⚠️ लाइव खोज नेटवर्क कनेक्शन में त्रुटि: {str(e)}"
    
    if not ai_answer:
        ai_answer = f"<b>'{query}'</b> के लिए खोज पूर्ण हुई। विस्तृत जानकारी के लिए नीचे दिए गए लिंक्स देखें।"

    # Fallback for empty search matches
    fallback_web_link = f"https://www.google.com/search?q={quote_plus(query)}"
    if not local_html:
        local_html = f"""
        <div class="card p-3 text-center border-0 shadow-sm rounded-4 bg-white">
            <p class="text-muted small mb-2">स्थानीय डेटाबेस में सीधा परिणाम नहीं मिला।</p>
            <a href="{fallback_web_link}" target="_blank" class="btn btn-outline-primary btn-sm rounded-pill fw-bold mx-auto" style="max-width: 250px;">
                <i class="bi bi-globe me-1"></i> Google पर '{query}' खोजें
            </a>
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

        <div class="card p-4 rounded-4 shadow-sm border bg-white mb-4">
            <div class="d-flex align-items-center gap-2 mb-2">
                <span class="fs-4">🤖</span>
                <h6 class="fw-bold text-primary mb-0">Bharat AI Summary</h6>
            </div>
            <div style="line-height: 1.6; font-size: 14px; color: #333;">
                {ai_answer}
            </div>
        </div>

        <h6 class="fw-bold text-success mb-3"><i class="bi bi-cpu me-2"></i>Bharat Smart Web Results</h6>
        {local_html}
    </div>
    """ + get_footer("home")

# -------------------------------------------------------------
# 🛠️ UNLOCKED VIP TOOLKIT SUITE (100% FREE FOR ALL USERS)
# -------------------------------------------------------------
@app.route("/converters")
def converters_hub():
    return get_html_header() + """
    <div class="container mt-4 mb-5" style="max-width: 750px;">
        <div class="text-center mb-4">
            <span class="badge bg-warning text-dark px-3 py-2 rounded-pill fw-bold">🚀 FREE FOR ALL USERS</span>
            <h3 class="fw-bold mt-2">Bharat AI Master Toolkit Suite</h3>
            <p class="text-muted small">सभी यूज़र्स के लिए 100% मुफ़्त और अति-उन्नत टूल्स</p>
        </div>

        <div class="row g-3">
            <div class="col-12 col-md-6">
                <div class="card p-3 shadow-sm rounded-4 border bg-white h-100">
                    <h6 class="fw-bold text-primary"><i class="bi bi-file-earmark-pdf me-2"></i>JPG to PDF Converter</h6>
                    <p class="small text-muted mb-2">अपनी किसी भी फोटो या डॉक्यूमेंट इमेज को PDF में बदलें।</p>
                    <form action="/convert_jpg_to_pdf" method="POST" enctype="multipart/form-data" class="mt-auto">
                        <input type="file" name="image_file" accept="image/*" class="form-control form-control-sm mb-2" required>
                        <button type="submit" class="btn btn-primary btn-sm w-100 rounded-pill fw-bold">Convert to PDF</button>
                    </form>
                </div>
            </div>

            <div class="col-12 col-md-6">
                <div class="card p-3 shadow-sm rounded-4 border bg-white h-100">
                    <h6 class="fw-bold text-success"><i class="bi bi-file-earmark-image me-2"></i>PNG / WEBP to JPG</h6>
                    <p class="small text-muted mb-2">इमेज के फॉर्मेट को तुरंत बदलें और डाउनलोड करें।</p>
                    <form action="/convert_image_format" method="POST" enctype="multipart/form-data" class="mt-auto">
                        <input type="file" name="image_file" accept="image/*" class="form-control form-control-sm mb-2" required>
                        <button type="submit" class="btn btn-success btn-sm w-100 rounded-pill fw-bold">Convert Format</button>
                    </form>
                </div>
            </div>

            <div class="col-12 col-md-6">
                <div class="card p-3 shadow-sm rounded-4 border bg-white h-100">
                    <h6 class="fw-bold text-info"><i class="bi bi-journal-text me-2"></i>AI Text Summarizer</h6>
                    <p class="small text-muted mb-2">किसी भी लंबे लेख या पैराग्राफ का 1 सेकंड में सार प्राप्त करें।</p>
                    <form action="/search" method="GET" class="mt-auto">
                        <input type="hidden" name="mode" value="fast">
                        <input type="text" name="q" class="form-control form-control-sm mb-2" placeholder="समरी के लिए विषय दर्ज करें..." required>
                        <button type="submit" class="btn btn-info text-white btn-sm w-100 rounded-pill fw-bold">Summarize Now</button>
                    </form>
                </div>
            </div>

            <div class="col-12 col-md-6">
                <div class="card p-3 shadow-sm rounded-4 border bg-white h-100">
                    <h6 class="fw-bold text-dark"><i class="bi bi-code-slash me-2"></i>AI Code Debugger</h6>
                    <p class="small text-muted mb-2">Python, JS, या HTML कोड में गलतियाँ ढूँढें या कोड लिखें।</p>
                    <form action="/search" method="GET" class="mt-auto">
                        <input type="hidden" name="mode" value="deep">
                        <input type="text" name="q" class="form-control form-control-sm mb-2" placeholder="e.g. Python loop code or bug fix" required>
                        <button type="submit" class="btn btn-dark btn-sm w-100 rounded-pill fw-bold">Debug / Write Code</button>
                    </form>
                </div>
            </div>

            <div class="col-12 text-center mt-2">
                <div class="card p-3 shadow-sm rounded-4 border bg-warning bg-opacity-10">
                    <h6 class="fw-bold text-dark"><i class="bi bi-calculator me-2"></i>Bharat Financial Calculators</h6>
                    <p class="small text-muted mb-2">EMI, SIP, Loan Interest और Tax गणना के लिए सीधे खोजें:</p>
                    <div class="d-flex gap-2 justify-content-center flex-wrap">
                        <a href="/search?q=EMI+Calculator" class="btn btn-sm btn-outline-dark rounded-pill">EMI Calc</a>
                        <a href="/search?q=SIP+Calculator" class="btn btn-sm btn-outline-dark rounded-pill">SIP Calc</a>
                        <a href="/search?q=Income+Tax+Calculator" class="btn btn-sm btn-outline-dark rounded-pill">Tax Calc</a>
                    </div>
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

@app.route("/convert_image_format", methods=["POST"])
def convert_image_format():
    if not Image: return "Image library missing."
    file = request.files.get('image_file')
    if not file: return redirect("/converters")
    try:
        image = Image.open(file.stream)
        if image.mode != 'RGB': image = image.convert('RGB')
        img_bytes = io.BytesIO()
        image.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        return send_file(img_bytes, mimetype='image/jpeg', as_attachment=True, download_name='converted.jpg')
    except Exception as e: return str(e)

# -------------------------------------------------------------
# 🎮 GAMES ARCADE (UNLOCKED)
# -------------------------------------------------------------
@app.route("/games")
def games():
    return get_html_header() + """
    <div class="container mt-4 mb-5" style="max-width: 600px;">
        <h4 class="fw-bold mb-3"><i class="bi bi-controller text-success me-2"></i>Games Arcade</h4>
        <div class="row g-3">
            <div class="col-6"><div class="card p-4 text-center shadow-sm rounded-4 border">🚀 Space Runner</div></div>
            <div class="col-6"><div class="card p-4 text-center shadow-sm rounded-4 border">💡 Brain Quiz</div></div>
        </div>
    </div>
    """ + get_footer("games")

# -------------------------------------------------------------
# 📚 RESEARCH WORKSPACE (UNLOCKED)
# -------------------------------------------------------------
@app.route("/research")
def research():
    return get_html_header() + """
    <div class="container mt-4 mb-5" style="max-width: 650px;">
        <div class="card p-4 rounded-4 shadow-sm border bg-white">
            <h4 class="fw-bold text-primary mb-2"><i class="bi bi-journal-bookmark-fill me-2"></i>Research Workspace</h4>
            <p class="small text-muted mb-3">Save research projects, organizing sources, and PDF summaries.</p>
            <button class="btn btn-primary btn-sm rounded-pill fw-bold align-self-start">+ Create New Research Project</button>
        </div>
    </div>
    """ + get_footer("research")

# -------------------------------------------------------------
# 🛡️ PRIVACY CENTER (UNLOCKED)
# -------------------------------------------------------------
@app.route("/privacy_center")
def privacy_center():
    return get_html_header() + """
    <div class="container mt-4 mb-5" style="max-width: 650px;">
        <div class="card p-4 rounded-4 shadow-sm border bg-white">
            <h4 class="fw-bold text-success mb-3"><i class="bi bi-shield-check me-2"></i>Privacy Controls & History Management</h4>
            <div class="form-check form-switch mb-3">
                <input class="form-check-input" type="checkbox" id="privateMode">
                <label class="form-check-label small fw-bold" for="privateMode">Enhanced Private Search Mode</label>
            </div>
            <button class="btn btn-danger btn-sm rounded-pill fw-bold">Auto-Delete History (30 Days)</button>
        </div>
    </div>
    """ + get_footer("home")

# -------------------------------------------------------------
# 👑 MEMBERSHIP SHOWCASE
# -------------------------------------------------------------
@app.route("/vip_tiers")
def vip_tiers():
    return get_html_header() + f"""
    <div class="container mt-4 mb-5" style="max-width: 850px;">
        <div class="text-center mb-4">
            <h3 class="fw-bold">Bharat OS Power Subscriptions</h3>
            <p class="text-muted small">अपनी आवश्यकताओं के लिए सबसे एडवांस्ड प्लान चुनें</p>
        </div>

        <div class="row g-3 d-flex align-items-stretch">
            <div class="col-12 col-md-6">
                <div class="card p-3 border rounded-4 shadow-sm h-100 bg-white d-flex flex-column justify-content-between">
                    <div>
                        <span class="badge bg-secondary align-self-start mb-2">🟢 FREE PLAN</span>
                        <h4 class="fw-bold mb-1">₹0 <small class="fs-6 text-muted">/ forever</small></h4>
                        <hr class="my-2">
                        <ul class="small text-muted ps-3 mb-0" style="line-height: 1.8;">
                            <li>Basic Web & Keyword Search</li>
                            <li>10 AI Overview Queries / day</li>
                            <li>Live News Feed & Discover</li>
                            <li>Standard Speed & Ads Supported</li>
                        </ul>
                    </div>
                </div>
            </div>

            <div class="col-12 col-md-6">
                <div class="card p-3 border-warning rounded-4 shadow-sm h-100 bg-light d-flex flex-column justify-content-between">
                    <div>
                        <span class="badge bg-warning text-dark align-self-start mb-2">🔵 VIP MEMBER</span>
                        <h4 class="fw-bold mb-1">₹49 <small class="fs-6 text-muted">/ 90 Days</small></h4>
                        <hr class="my-2">
                        <ul class="small text-dark ps-3 mb-3" style="line-height: 1.8;">
                            <li><b>🚫 100% Zero Ads Clean UI</b></li>
                            <li>100 Fast AI Answers / day</li>
                            <li>📄 PDF, DOCX, PPTX Filters</li>
                            <li>🛠️ Unlimited VIP Toolkit Converter Access</li>
                            <li>👑 Blue VIP Status Badge</li>
                        </ul>
                    </div>
                    <a href="/remove_ads?plan=VIP" class="btn btn-warning btn-sm rounded-pill fw-bold w-100 mt-3 py-2">Choose VIP (₹49)</a>
                </div>
            </div>

            <div class="col-12 col-md-6">
                <div class="card p-3 border-primary rounded-4 shadow-sm h-100 bg-white d-flex flex-column justify-content-between">
                    <div>
                        <span class="badge bg-primary align-self-start mb-2">🟣 VIP PRO</span>
                        <h4 class="fw-bold mb-1">₹149 <small class="fs-6 text-muted">/ 90 Days</small></h4>
                        <hr class="my-2">
                        <ul class="small text-dark ps-3 mb-3" style="line-height: 1.8;">
                            <li>VIP के सभी फ़ायदे +</li>
                            <li><b>🔬 Deep Research Engine v2.0</b></li>
                            <li><b>⚡ Code & Algorithm Engine</b></li>
                            <li><b>👶 ELI5 Mode ("Explain Like I'm 5")</b></li>
                            <li>📁 Smart Document OCR & PDF Chat Engine</li>
                            <li>⚡ 500 AI Queries / day (Priority Speed)</li>
                        </ul>
                    </div>
                    <a href="/remove_ads?plan=VIP_PRO" class="btn btn-primary btn-sm rounded-pill fw-bold w-100 mt-3 py-2">Choose VIP Pro (₹149)</a>
                </div>
            </div>

            <div class="col-12 col-md-6">
                <div class="card p-3 border-danger rounded-4 shadow-sm h-100 bg-danger bg-opacity-10 d-flex flex-column justify-content-between">
                    <div>
                        <span class="badge bg-danger align-self-start mb-2">👑 VIP ULTRA</span>
                        <h4 class="fw-bold mb-1">₹299 <small class="fs-6 text-muted">/ 90 Days</small></h4>
                        <hr class="my-2">
                        <ul class="small text-dark ps-3 mb-3" style="line-height: 1.8;">
                            <li>VIP Pro के सभी फ़ायदे +</li>
                            <li><b>♾️ Unlimited Reasonable AI Queries</b></li>
                            <li><b>🤖 Autonomous Web AI Agent</b></li>
                            <li><b>🛡️ Private Vault & Auto-Delete History</b></li>
                            <li>🔮 Live Data & Market Price AI Tracker</li>
                            <li>⚡ Quantum Queue Allocation (0.001s Speed)</li>
                            <li>💬 Direct Owner Hotline & Early Beta Access</li>
                        </ul>
                    </div>
                    <a href="/remove_ads?plan=VIP_ULTRA" class="btn btn-danger btn-sm rounded-pill fw-bold w-100 mt-3 py-2">Choose VIP Ultra (₹299)</a>
                </div>
            </div>
        </div>
    </div>
    """ + get_footer("vip")

# -------------------------------------------------------------
# 💳 PAYMENT ROUTE
# -------------------------------------------------------------
@app.route("/remove_ads", methods=["GET", "POST"])
def remove_ads():
    plan_key = request.args.get("plan", "VIP").upper()
    plan_info = TIER_DETAILS.get(plan_key, TIER_DETAILS["VIP"])
    price = plan_info["price"]

    msg = ""
    is_owner = session.get("owner_logged", False)
    username = session.get("username", "Owner" if is_owner else "")

    if request.method == "POST":
        utr_no = request.form.get("utr_number", "").strip()
        if utr_no and len(utr_no) >= 10:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            try:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("INSERT OR REPLACE INTO payment_requests (username, utr_number, plan_type, status, timestamp) VALUES (?, ?, ?, 'pending', ?)", (username, utr_no, plan_key, now))
                conn.commit()
                msg = "✅ UTR सफलतापूर्वक सबमिट हो गई है! ऑनर वेरिफिकेशन के बाद एक्टिवेट होगा।"
            except Exception as e:
                msg = f"⚠️ त्रुटि: {str(e)}"
            conn.close()

    upi_intent = f"upi://pay?pa={YOUR_UPI_ID}&pn={quote_plus(YOUR_UPI_NAME)}&am={price}&cu=INR"
    upi_qr_url = f"https://quickchart.io/qr?text={quote_plus(upi_intent)}&size=250&margin=1"

    return get_html_header() + f"""
    <div class="container mt-3 mb-5" style="max-width: 500px;">
        <div class="bg-white p-4 rounded-4 shadow-sm border text-center">
            <span class="badge bg-warning text-dark rounded-pill px-3 py-1 mb-2">⚡ UNIFORM PAYMENTS</span>
            <h4 class="fw-bold mb-1">Upgrade to {plan_key.replace('_', ' ')} Plan</h4>
            <p class="text-muted small mb-3">स्कैन करें या UPI ID पर भुगतान करें</p>

            {f'<div class="alert alert-info py-2 small mb-3">{msg}</div>' if msg else ''}

            <div class="card p-3 my-2 bg-light border-warning rounded-4 shadow-sm">
                <div class="fw-bold text-danger fs-3 mb-1">₹{price} <small class="fs-6 text-muted">/ 90 दिन</small></div>
                
                <div class="my-2 p-2 bg-white d-inline-block rounded-3 border mx-auto">
                    <img src="{upi_qr_url}" alt="Bharat UPI QR Code" style="width: 200px; height: 200px; display: block;">
                </div>

                <div class="mt-2 bg-white p-2 rounded-3 border d-flex justify-content-between align-items-center">
                    <div class="text-start">
                        <small class="text-muted d-block" style="font-size:10px;">UPI ID</small>
                        <strong class="text-dark" id="upiIdText" style="font-size:14px;">{YOUR_UPI_ID}</strong>
                    </div>
                    <button type="button" class="btn btn-sm btn-outline-primary rounded-pill px-3" onclick="copyUPI()"><i class="bi bi-clipboard me-1"></i>Copy</button>
                </div>

                <a href="{upi_intent}" class="btn btn-success btn-sm w-100 rounded-pill fw-bold mt-3"><i class="bi bi-wallet2 me-1"></i> Open GPay / PhonePe / Paytm</a>
            </div>

            <form method="POST" class="mt-3">
                <div class="text-start mb-1">
                    <label class="form-label small fw-bold text-muted mb-1">भुगतान के बाद 12-अंकों का UTR / Ref No. दर्ज करें:</label>
                </div>
                <input type="text" name="utr_number" class="form-control text-center rounded-pill mb-2" placeholder="e.g. 4238XXXX1234" required pattern="[0-9]{{10,16}}">
                <button type="submit" class="btn btn-warning w-100 rounded-pill fw-bold py-2"><i class="bi bi-check-circle-fill me-1"></i> Submit Payment UTR</button>
            </form>
        </div>
    </div>

    <script>
    function copyUPI() {{
        const upiText = document.getElementById("upiIdText").innerText;
        navigator.clipboard.writeText(upiText);
        alert("UPI ID कॉपी हो गई है: " + upiText);
    }}
    </script>
    """ + get_footer("vip")

# -------------------------------------------------------------
# 👑 OWNER DASHBOARD
# -------------------------------------------------------------
@app.route("/owner_dashboard", methods=["GET", "POST"])
def owner_dashboard():
    if not session.get("owner_logged"): return redirect("/owner_login")

    message = ""
    if request.method == "POST":
        form_type = request.form.get("form_type")

        # 1. DIRECT MANUAL USER UPGRADE
        if form_type == "direct_upgrade":
            target_user = request.form.get("username", "").strip()
            selected_tier = request.form.get("tier", "VIP")
            
            if target_user:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                expiry_date = (datetime.now() + timedelta(days=VIP_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
                
                cursor.execute("SELECT id FROM users WHERE username = ?", (target_user,))
                user_exists = cursor.fetchone()
                
                if user_exists:
                    cursor.execute("UPDATE users SET is_premium = 1, tier = ?, vip_expires_at = ? WHERE username = ?", (selected_tier, expiry_date, target_user))
                    message = f"✅ <b>{target_user}</b> को सफलता से <b>{selected_tier}</b> में अपग्रेड कर दिया गया है!"
                else:
                    cursor.execute("INSERT INTO users (username, password, tier, is_premium, vip_expires_at) VALUES (?, '123456', ?, 1, ?)", (target_user, selected_tier, expiry_date))
                    message = f"✅ नया यूज़र <b>{target_user}</b> बनाकर उसे <b>{selected_tier}</b> एक्टिवेट कर दिया गया!"
                
                conn.commit()
                conn.close()

        # 2. APPROVE / REJECT FROM PENDING TABLE
        elif form_type == "payment_action":
            action = request.form.get("action")
            target_user = request.form.get("username")
            req_id = request.form.get("req_id")
            plan_type = request.form.get("plan_type", "VIP")

            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            if action == "approve":
                expiry_date = (datetime.now() + timedelta(days=VIP_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("UPDATE users SET is_premium = 1, tier = ?, vip_expires_at = ? WHERE username = ?", (plan_type, expiry_date, target_user))
                cursor.execute("UPDATE payment_requests SET status = 'approved' WHERE id = ?", (req_id,))
                message = f"✅ {target_user} का भुगतान स्वीकृत! ({plan_type} सक्रीय)"
            elif action == "reject":
                cursor.execute("UPDATE payment_requests SET status = 'rejected' WHERE id = ?", (req_id,))
                message = f"❌ भुगतान अनुरोध अस्वीकृत।"
            conn.commit()
            conn.close()

        # 3. ADD NEW LINK TO SEARCH INDEX
        elif form_type == "add_link":
            title, url, snippet, category = request.form.get("title"), request.form.get("url"), request.form.get("snippet"), request.form.get("category")
            if title and url:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO local_search_index (title, url, snippet, category) VALUES (?, ?, ?, ?)", (title, url, snippet, category))
                conn.commit()
                conn.close()
                bharat_engine.index_item(title, url, snippet, category)
                message = f"✅ नई लिंक इंडेक्स हो गई: {title}"

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id, username, utr_number, plan_type, status, timestamp FROM payment_requests ORDER BY id DESC")
        requests_list = cursor.fetchall()
    except Exception:
        requests_list = []

    cursor.execute("SELECT COUNT(*) FROM local_search_index")
    total_indexed_count = cursor.fetchone()[0]
    conn.close()

    req_rows = ""
    for r in requests_list:
        req_id, u_name, utr, p_type, p_status, p_time = r[0], r[1], r[2], r[3] or "VIP", r[4], r[5]
        if p_status == "pending":
            req_rows += f"""
            <tr>
                <td><b>{u_name}</b></td>
                <td><code>{utr}</code></td>
                <td><span class="badge bg-primary">{p_type}</span></td>
                <td><small class="text-muted">{p_time[:16] if p_time else ''}</small></td>
                <td>
                    <form method="POST" class="d-inline">
                        <input type="hidden" name="form_type" value="payment_action">
                        <input type="hidden" name="req_id" value="{req_id}">
                        <input type="hidden" name="username" value="{u_name}">
                        <input type="hidden" name="plan_type" value="{p_type}">
                        <button name="action" value="approve" class="btn btn-sm btn-success fw-bold px-2 py-1 me-1"><i class="bi bi-check-circle"></i> Approve</button>
                        <button name="action" value="reject" class="btn btn-sm btn-danger fw-bold px-2 py-1"><i class="bi bi-x-circle"></i> Reject</button>
                    </form>
                </td>
            </tr>
            """

    return get_html_header() + f"""
    <div class="container mt-4 mb-5" style="max-width: 800px;">
        <div class="bg-white p-4 rounded-4 shadow-sm border mb-4">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h4 class="fw-bold text-danger mb-0"><i class="bi bi-speedometer2 me-2"></i>Owner Control Center</h4>
                <span class="badge bg-primary rounded-pill px-3 py-2">Total Links: {total_indexed_count}</span>
            </div>
            
            {f'<div class="alert alert-success py-2 small mb-3">{message}</div>' if message else ''}

            <!-- 🚀 1. DIRECT MANUAL USER UPGRADE -->
            <div class="card p-3 border-danger bg-danger bg-opacity-10 mb-4 rounded-4">
                <h6 class="fw-bold text-danger mb-1"><i class="bi bi-lightning-charge-fill me-1"></i>Direct VIP Upgrade (1-Click Approval)</h6>
                <p class="text-muted small mb-2">अगर पेंडिंग टेबल में यूजर का नाम नहीं दिख रहा है, तो यहाँ उसका Username दर्ज करके सीधे एक्टिवेट करें:</p>
                
                <form method="POST">
                    <input type="hidden" name="form_type" value="direct_upgrade">
                    <div class="row g-2">
                        <div class="col-12 col-md-5">
                            <input type="text" name="username" class="form-control form-control-sm" placeholder="Enter Username (e.g. Rahul123)" required>
                        </div>
                        <div class="col-12 col-md-4">
                            <select name="tier" class="form-select form-select-sm">
                                <option value="VIP">🔵 VIP (₹49)</option>
                                <option value="VIP_PRO">🟣 VIP Pro (₹149)</option>
                                <option value="VIP_ULTRA">👑 VIP Ultra (₹299)</option>
                            </select>
                        </div>
                        <div class="col-12 col-md-3">
                            <button type="submit" class="btn btn-danger btn-sm w-100 fw-bold rounded-pill"><i class="bi bi-check2-circle"></i> Activate VIP</button>
                        </div>
                    </div>
                </form>
            </div>

            <!-- 2. PENDING UTR REQUESTS TABLE -->
            <div class="card p-3 border-warning bg-light mb-4 rounded-4">
                <h6 class="fw-bold text-dark mb-2"><i class="bi bi-credit-card-2-front text-warning me-2"></i>Pending UTR Requests</h6>
                <div class="table-responsive">
                    <table class="table table-hover align-middle small mb-0 bg-white rounded-3 overflow-hidden">
                        <thead class="table-dark">
                            <tr>
                                <th>User</th>
                                <th>UTR Number</th>
                                <th>Plan</th>
                                <th>Time</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {req_rows if req_rows else '<tr><td colspan="5" class="text-center text-muted py-3">कोई नया पेंडिंग अनुरोध नहीं है। ऊपर दिए गए "Direct VIP Upgrade" फ़ॉर्म का उपयोग करें!</td></tr>'}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- 3. ADD LINK FORM -->
            <div class="card p-3 border-secondary bg-white rounded-4">
                <h6 class="fw-bold text-dark mb-2"><i class="bi bi-plus-circle-fill text-primary me-2"></i>Add Web Link to Index</h6>
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
                    <button type="submit" class="btn btn-warning btn-sm rounded-pill fw-bold w-100">Add Link to Index</button>
                </form>
            </div>
        </div>
    </div>
    """ + get_footer("home")

# -------------------------------------------------------------
# 💬 CHATS, HISTORY & AUTH
# -------------------------------------------------------------
@app.route("/chats", methods=["GET", "POST"])
def chats():
    username = session.get("username", "")
    if not username: return redirect("/user_login")
    if request.method == "POST":
        receiver, msg_text = request.form.get("receiver", "").strip(), request.form.get("message", "").strip()
        if receiver and msg_text:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO messages (sender, receiver, message, timestamp) VALUES (?, ?, ?, ?)", (username, receiver, msg_text, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            conn.close()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT sender, receiver, message, timestamp FROM messages WHERE sender = ? OR receiver = ? ORDER BY id DESC LIMIT 20", (username, username))
    chat_list = cursor.fetchall()
    conn.close()

    # Unicode arrow fix
    chat_rows = "".join([f'<li class="list-group-item d-flex justify-content-between"><div><b>{c[0]} → {c[1]}:</b> {c[2]}</div><small class="text-muted">{c[3][11:16]}</small></li>' for c in chat_list])

    return get_html_header() + f"""
    <div class="container mt-4 mb-5" style="max-width: 600px;">
        <div class="card p-4 rounded-4 shadow-sm border bg-white">
            <h4 class="fw-bold text-primary mb-3"><i class="bi bi-chat-dots-fill me-2"></i>Bharat Chat Hub</h4>
            <form method="POST" class="mb-4">
                <input type="text" name="receiver" class="form-control mb-2" placeholder="To Username" required>
                <div class="input-group">
                    <input type="text" name="message" class="form-control" placeholder="Type a message..." required>
                    <button class="btn btn-primary" type="submit">Send</button>
                </div>
            </form>
            <ul class="list-group list-group-flush small">{chat_rows}</ul>
        </div>
    </div>
    """ + get_footer("chats")

@app.route("/my_history")
def my_history():
    username = session.get("username", "")
    if not username: return redirect("/user_login")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT query, timestamp FROM search_history WHERE username = ? ORDER BY id DESC LIMIT 20", (username,))
    rows = cursor.fetchall()
    conn.close()
    history_html = "".join([f'<li class="list-group-item d-flex justify-content-between"><span>{r[0]}</span><small class="text-muted">{r[1]}</small></li>' for r in rows]) if rows else '<li class="list-group-item text-muted text-center py-3">कोई खोज इतिहास नहीं मिला।</li>'
    return get_html_header() + f'<div class="container mt-4 mb-5" style="max-width: 600px;"><h5 class="fw-bold mb-3"><i class="bi bi-clock-history me-2 text-warning"></i>आपकी खोज इतिहास</h5><ul class="list-group shadow-sm rounded-4 overflow-hidden">{history_html}</ul></div>' + get_footer("home")

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

if __name__ == "__main__":
    app.run(debug=True, port=5000)
