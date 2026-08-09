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

# 🤖 ADVANCED SEARCH ENGINE IMPORT
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

# -------------------------------------------------------------
# 👑 4-TIER MEMBERSHIP MATRIX
# -------------------------------------------------------------
TIER_LIMITS = {
    "Free": {"ai_limit": 10, "deep_search": False, "badge": "🟢 FREE USER", "badge_cls": "bg-secondary"},
    "VIP": {"ai_limit": 100, "deep_search": False, "badge": "🔵 VIP MEMBER", "badge_cls": "bg-warning text-dark"},
    "VIP Pro": {"ai_limit": 500, "deep_search": True, "badge": "🟣 VIP PRO", "badge_cls": "bg-primary"},
    "VIP Ultra": {"ai_limit": 9999, "deep_search": True, "badge": "👑 VIP ULTRA", "badge_cls": "bg-danger"}
}

def is_safe_query(query):
    query_lower = query.lower()
    for word in BLOCKED_KEYWORDS:
        if word in query_lower:
            return False
    return True

# -------------------------------------------------------------
# 🗄️ DATABASE INITIALIZATION & SEEDER
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
            status TEXT DEFAULT 'pending',
            plan_type TEXT DEFAULT 'VIP',
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

def get_user_subscription():
    if session.get("owner_logged"):
        return "VIP Ultra", TIER_LIMITS["VIP Ultra"]
    
    username = session.get("username")
    if not username:
        return "Free", TIER_LIMITS["Free"]

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT tier, is_premium, vip_expires_at FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return "Free", TIER_LIMITS["Free"]

    tier, is_prem, expires_at_str = row[0] or "Free", row[1], row[2]
    if is_prem and expires_at_str:
        try:
            expires_at = datetime.strptime(expires_at_str, "%Y-%m-%d %H:%M:%S")
            if datetime.now() > expires_at:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET is_premium = 0, tier = 'Free' WHERE username = ?", (username,))
                conn.commit()
                conn.close()
                return "Free", TIER_LIMITS["Free"]
        except ValueError:
            pass
        return tier, TIER_LIMITS.get(tier, TIER_LIMITS["VIP"])

    return "Free", TIER_LIMITS["Free"]

def is_user_premium():
    tier, _ = get_user_subscription()
    return tier != "Free"

# -------------------------------------------------------------
# 🔍 SUGGESTIONS & NEWS
# -------------------------------------------------------------
@app.route("/api/suggestions")
def suggestions():
    q = request.args.get("q", "").strip()
    if not q: return jsonify([])
    results = []
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        search_kw = f"%{q}%"
        cursor.execute("SELECT DISTINCT title FROM local_search_index WHERE title LIKE ? OR category LIKE ? LIMIT 6", (search_kw, search_kw))
        results = [r[0] for r in cursor.fetchall()]
        conn.close()
    except Exception: pass
    return jsonify(results)

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
# 🎨 UI HEADER & FOOTER ENGINE
# -------------------------------------------------------------
def get_html_header():
    tier, tier_info = get_user_subscription()
    is_owner = session.get("owner_logged", False)
    username = session.get("username", "Owner" if is_owner else "Guest User")
    
    badge_label = "👑 OWNER" if is_owner else tier_info["badge"]
    badge_class = "bg-danger" if is_owner else tier_info["badge_cls"]

    adsense_script = """<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-6514818403683886" crossorigin="anonymous"></script>""" if tier == "Free" else "<!-- VIP Member: Ads Disabled -->"

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
        .bottom-nav-bar {{ position: fixed; bottom: 0; left: 0; right: 0; background: var(--bg-color); border-top: 1px solid var(--border-color); display: flex; justify-content: space-around; padding: 8px 0; z-index: 9998; }}
        .nav-link-item {{ text-decoration: none; color: #5f6368; font-size: 11px; text-align: center; flex: 1; }}
        .nav-link-item.active {{ color: #ff7700; font-weight: 600; }}
        .no-scrollbar::-webkit-scrollbar {{ display: none; }}
    </style>
</head>
<body>

<div class="top-bar-chrome">
    <div class="creator-badge">🚀 <b>Bharat OS</b> <span class="badge {badge_class} rounded-pill ms-1">{badge_label}</span></div>
    <div class="top-actions">
        <a href="/chats" class="icon-btn" title="Bharat Chat"><i class="bi bi-chat-dots-fill text-primary"></i></a>
        <a href="/vip_tiers" class="icon-btn" title="VIP Tiers"><i class="bi bi-crown-fill text-warning"></i></a>
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
                <li><a class="dropdown-item rounded-3 py-2 fw-bold text-danger" href="/vip_tiers"><i class="bi bi-gem me-2"></i> Upgrade Tiers</a></li>
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
        searchInput.value = text;
        suggestionsBox.style.display = "none";
        searchInput.form.submit();
    }}
</script>
</body>
</html>
"""

# -------------------------------------------------------------
# 🏠 HOME ROUTE (ADVANCED 140-FEATURE SEARCH ENGINE)
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

            <!-- 140 ADVANCED SEARCH FILTERS BAR -->
            <form action="/search" method="GET" class="google-search-container">
                <i class="bi bi-search search-left-icon"></i>
                <input type="text" id="searchInput" name="q" class="form-control google-input" placeholder="सर्च करें, फाइल्स ढूंढें या AI से पूछें..." autocomplete="off" required autofocus>
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
# 🔍 SEARCH ROUTE
# -------------------------------------------------------------
@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    file_type = request.args.get("file_type", "all")
    country = request.args.get("country", "all")
    mode = request.args.get("mode", "fast")

    if not query or not is_safe_query(query): return redirect("/")

    tier, _ = get_user_subscription()

    # 1. AI Vector Search Call
    vector_results = bharat_engine.search(query, top_k=5)
    
    local_html = ""
    for item in vector_results:
        title, url, snippet, category = item["title"], item["url"], item["snippet"], item["category"]
        favicon = f"https://www.google.com/s2/favicons?domain={urlparse(url).netloc if url else 'google.com'}&sz=64"
        local_html += f"""
        <div class="card p-3 mb-2 border-0 shadow-sm rounded-4 bg-white">
            <div class="d-flex align-items-center gap-2 mb-1">
                <img src="{favicon}" width="18" height="18" class="rounded">
                <span class="text-muted small" style="font-size: 11px;">{url}</span>
            </div>
            <h6 class="mb-1"><a href="{url}" target="_blank" class="text-primary text-decoration-none fw-bold">{title}</a></h6>
            <p class="text-muted small mb-0" style="font-size: 13px;">{snippet}</p>
        </div>
        """

    # 2. AI Overview Generation (Mode Adaptive)
    prompt_prefix = "Explain like I'm 5 years old:" if mode == "eli5" else ("Provide a deep academic summary for:" if mode == "deep" else "Provide a detailed overview for:")
    ai_answer = f"<b>{query}</b> ({mode.upper()} Mode) से संबंधित सभी आधिकारिक लिंक्स और परिणाम नीचे प्रस्तुत हैं।"
    
    if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_GEMINI_API_KEY_HERE":
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
            payload = {"contents": [{"parts": [{"text": f"{prompt_prefix} {query}"}]}]}
            res = requests.post(url, json=payload, timeout=8)
            if res.status_code == 200:
                ai_answer = res.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception: pass

    return get_html_header() + f"""
    <div class="container mt-4 mb-5" style="max-width: 720px;">
        <div class="d-flex gap-2 mb-3">
            <span class="badge bg-warning text-dark">Mode: {mode.upper()}</span>
            <span class="badge bg-secondary">Filter: {file_type.upper()}</span>
            <span class="badge bg-info text-dark">Region: {country.upper()}</span>
        </div>

        <div class="card p-4 rounded-4 shadow-sm border bg-white mb-4">
            <div class="d-flex align-items-center gap-2 mb-2">
                <span class="fs-4">🤖</span>
                <h6 class="fw-bold text-primary mb-0">Bharat AI Summary</h6>
            </div>
            <div style="line-height: 1.6; font-size: 14px; color: #333;">
                {ai_answer.replace('\n', '<br>')}
            </div>
        </div>

        <h6 class="fw-bold text-success mb-3"><i class="bi bi-cpu me-2"></i>Bharat Vector Smart Matches</h6>
        {local_html if local_html else '<p class="text-muted small">कोई स्थानीय परिणाम नहीं मिला। वेब खोज चालू है...</p>'}
    </div>
    """ + get_footer("home")

# -------------------------------------------------------------
# 👑 4-TIERS MEMBERSHIP CLUB ROUTE
# -------------------------------------------------------------
@app.route("/vip_tiers")
def vip_tiers():
    return get_html_header() + f"""
    <div class="container mt-4 mb-5" style="max-width: 750px;">
        <div class="text-center mb-4">
            <h3 class="fw-bold">Bharat OS Subscription Tiers</h3>
            <p class="text-muted small">अपनी आवश्यकतानुसार बेस्ट प्लान चुनें</p>
        </div>

        <div class="row g-3">
            <div class="col-12 col-md-6">
                <div class="card p-3 border rounded-4 shadow-sm h-100 bg-white">
                    <span class="badge bg-secondary align-self-start mb-2">🟢 FREE</span>
                    <h4 class="fw-bold">₹0 <small class="fs-6 text-muted">/ forever</small></h4>
                    <ul class="small text-muted ps-3 mt-2">
                        <li>Basic Search + Images + News</li>
                        <li>Limited AI Answers (10/day)</li>
                        <li>Standard Speed</li>
                    </ul>
                </div>
            </div>

            <div class="col-12 col-md-6">
                <div class="card p-3 border-warning rounded-4 shadow-sm h-100 bg-light">
                    <span class="badge bg-warning text-dark align-self-start mb-2">🔵 VIP</span>
                    <h4 class="fw-bold">₹49 <small class="fs-6 text-muted">/ 90 Days</small></h4>
                    <ul class="small ps-3 mt-2">
                        <li><b>Ad-Free Experience</b></li>
                        <li>100 AI Answers / day</li>
                        <li>Advanced Search Filters</li>
                    </ul>
                    <a href="/remove_ads?plan=VIP" class="btn btn-warning btn-sm rounded-pill fw-bold mt-auto">Choose VIP</a>
                </div>
            </div>

            <div class="col-12 col-md-6">
                <div class="card p-3 border-primary rounded-4 shadow-sm h-100 bg-white">
                    <span class="badge bg-primary align-self-start mb-2">🟣 VIP PRO</span>
                    <h4 class="fw-bold">₹149 <small class="fs-6 text-muted">/ 90 Days</small></h4>
                    <ul class="small ps-3 mt-2">
                        <li>VIP के सभी फ़ायदे +</li>
                        <li><b>Deep Research Mode</b></li>
                        <li>500 AI Answers / day</li>
                    </ul>
                    <a href="/remove_ads?plan=VIP_PRO" class="btn btn-primary btn-sm rounded-pill fw-bold mt-auto">Choose VIP Pro</a>
                </div>
            </div>

            <div class="col-12 col-md-6">
                <div class="card p-3 border-danger rounded-4 shadow-sm h-100 bg-danger bg-opacity-10">
                    <span class="badge bg-danger align-self-start mb-2">👑 VIP ULTRA</span>
                    <h4 class="fw-bold">₹299 <small class="fs-6 text-muted">/ 90 Days</small></h4>
                    <ul class="small ps-3 mt-2">
                        <li>VIP Pro के सभी फ़ायदे +</li>
                        <li><b>Unlimited Reasonable Usage</b></li>
                        <li>Early Access to Experimental AI</li>
                    </ul>
                    <a href="/remove_ads?plan=VIP_ULTRA" class="btn btn-danger btn-sm rounded-pill fw-bold mt-auto">Choose VIP Ultra</a>
                </div>
            </div>
        </div>
    </div>
    """ + get_footer("vip")

# -------------------------------------------------------------
# 📚 RESEARCH WORKSPACE & 🛡️ PRIVACY CENTER
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
# 💬 CHAT, GAMES, CONVERTERS, OWNER & AUTH ROUTES (UNTOUCHED)
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

    chat_rows = "".join([f'<li class="list-group-item d-flex justify-content-between"><div><b>{c[0]} $\\rightarrow$ {c[1]}:</b> {c[2]}</div><small class="text-muted">{c[3][11:16]}</small></li>' for c in chat_list])

    return get_html_header() + f"""
    <div class="container mt-4 mb-5" style="max-width: 600px;">
        <div class="card p-4 rounded-4 shadow-sm border bg-white">
            <h4 class="fw-bold text-primary mb-3"><i class="bi bi-chat-dots-fill me-2"></i>Bharat Chat Hub</h4>
            <form method="POST" class="mb-4">
                <input type="text" name="receiver" class="form-control mb-2" placeholder="To Username" required>
                <div class="input-group">
                    <input type="text" name="message" class="form-control" placeholder="Message..." required>
                    <button class="btn btn-primary" type="submit">Send</button>
                </div>
            </form>
            <ul class="list-group list-group-flush small">{chat_rows}</ul>
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
        </div>
    </div>
    """ + get_footer("games")

@app.route("/converters")
def converters_hub():
    return get_html_header() + """
    <div class="container mt-4 mb-5" style="max-width: 600px;">
        <h4 class="fw-bold mb-3"><i class="bi bi-gear-wide-connected text-warning me-2"></i>VIP Toolkit Suite</h4>
        <div class="card p-3 shadow-sm rounded-4 border bg-white mb-3">
            <h6>JPG to PDF Converter</h6>
            <form action="/convert_jpg_to_pdf" method="POST" enctype="multipart/form-data">
                <input type="file" name="image_file" accept="image/*" class="form-control form-control-sm mb-2" required>
                <button type="submit" class="btn btn-primary btn-sm rounded-pill w-100">Convert to PDF</button>
            </form>
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

@app.route("/owner_dashboard", methods=["GET", "POST"])
def owner_dashboard():
    if not session.get("owner_logged"): return redirect("/owner_login")
    if request.method == "POST":
        form_type = request.form.get("form_type")
        if form_type == "add_link":
            title, url, snippet, category = request.form.get("title"), request.form.get("url"), request.form.get("snippet"), request.form.get("category")
            if title and url:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO local_search_index (title, url, snippet, category) VALUES (?, ?, ?, ?)", (title, url, snippet, category))
                conn.commit()
                conn.close()
                bharat_engine.index_item(title, url, snippet, category)

    return get_html_header() + """
    <div class="container mt-4 mb-5" style="max-width: 700px;">
        <div class="card p-4 rounded-4 shadow-sm border bg-white">
            <h4 class="fw-bold text-danger mb-3"><i class="bi bi-speedometer2 me-2"></i>Owner Control Center</h4>
            <form method="POST">
                <input type="hidden" name="form_type" value="add_link">
                <input type="text" name="title" class="form-control form-control-sm mb-2" placeholder="Site Title" required>
                <input type="url" name="url" class="form-control form-control-sm mb-2" placeholder="URL" required>
                <input type="text" name="snippet" class="form-control form-control-sm mb-2" placeholder="Description" required>
                <input type="text" name="category" class="form-control form-control-sm mb-3" placeholder="Category" required>
                <button type="submit" class="btn btn-warning btn-sm rounded-pill fw-bold w-100">Add Link to Index</button>
            </form>
        </div>
    </div>
    """ + get_footer("home")

@app.route("/remove_ads", methods=["GET", "POST"])
def remove_ads():
    plan = request.args.get("plan", "VIP")
    upi_qr_url = f"https://chart.googleapis.com/chart?cht=qr&chs=250x250&chl=upi://pay?pa={YOUR_UPI_ID}&pn={quote_plus(YOUR_UPI_NAME)}&am={VIP_PRICE}&cu=INR"
    return get_html_header() + f"""
    <div class="container mt-4 mb-5" style="max-width: 500px;">
        <div class="bg-white p-4 rounded-4 shadow-sm border text-center">
            <h3 class="fw-bold">Upgrade to {plan}</h3>
            <img src="{upi_qr_url}" alt="UPI QR" class="mx-auto my-2" style="width:180px;">
            <form method="POST">
                <input type="text" name="utr_number" class="form-control text-center rounded-pill my-2" placeholder="Enter 12-digit UTR No." required>
                <button type="submit" class="btn btn-warning w-100 rounded-pill fw-bold">Submit Payment UTR</button>
            </form>
        </div>
    </div>
    """ + get_footer("vip")

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
    return get_html_header() + f'<div class="container mt-4 mb-5" style="max-width: 600px;"><ul class="list-group shadow-sm">{history_html}</ul></div>' + get_footer("home")

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
