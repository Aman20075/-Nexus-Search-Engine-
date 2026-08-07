import os
import sqlite3
from datetime import datetime
from urllib.parse import quote_plus, urlparse

from bs4 import BeautifulSoup
from flask import Flask, jsonify, redirect, request, session, url_for
import requests

# -------------------------------------------------------------
# 🔑 CONFIGURATION & API KEYS
# -------------------------------------------------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")

# 💳 आपकी UPI ID और नाम (Direct Bank Transfer)
YOUR_UPI_ID = os.environ.get("YOUR_UPI_ID", "giriji5626@okaxis")
YOUR_UPI_NAME = os.environ.get("YOUR_UPI_NAME", "Sandesh Giri")

try:
    from google import genai
    ai_client = (
        genai.Client(api_key=GEMINI_API_KEY)
        if GEMINI_API_KEY != "YOUR_GEMINI_API_KEY_HERE"
        else None
    )
except ImportError:
    ai_client = None

app = Flask(__name__)
app.permanent_session_lifetime = 365 * 24 * 60 * 60
app.secret_key = os.environ.get(
    "SECRET_KEY", "bharat_search_permanent_session_key_2026"
)

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

def crawl_website_metadata(url):
    try:
        parsed_url = urlparse(url)
        domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
        favicon_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(url, headers=headers, timeout=5)
        title, snippet = "", ""
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            if soup.title and soup.title.string:
                title = soup.title.string.strip()
            meta_desc = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
            if meta_desc and meta_desc.get("content"):
                snippet = meta_desc["content"].strip()
        if not title: title = parsed_url.netloc
        if not snippet: snippet = f"Explore {parsed_url.netloc} for official links and updates."
        return title, snippet, favicon_url
    except Exception:
        parsed_url = urlparse(url)
        domain = f"{parsed_url.scheme}://{parsed_url.netloc}" if parsed_url.netloc else url
        favicon_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
        return parsed_url.netloc or url, "Instant web result from Bharat Search Engine.", favicon_url

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT DEFAULT 'user',
            is_premium INTEGER DEFAULT 0
        )
    """)

    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    if "is_premium" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN is_premium INTEGER DEFAULT 0")

    # UTR Requests Table for Direct UPI Verification
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

    conn.commit()
    conn.close()

init_db()

def is_user_premium():
    if session.get("owner_logged"):
        return True
    username = session.get("username")
    if not username:
        return False
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT is_premium FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    return bool(row[0]) if row else False

def get_html_header():
    premium = is_user_premium()
    adsense_script = """
    <!-- Google AdSense Integration -->
    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-6514818403683886" crossorigin="anonymous"></script>
    """ if not premium else "<!-- Premium Member: Ads Disabled -->"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Bharat AI Search Engine</title>
    {adsense_script}
    <link rel="manifest" href="/manifest.json">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css">
    <meta name="theme-color" content="#FF9933">
    <style>
        :root {{ --bg-color: #fff9f2; --text-color: #202124; --card-bg: rgba(255, 255, 255, 0.95); --border-color: #f1d3b3; }}
        body.dark-mode {{ --bg-color: #121212; --text-color: #e8eaed; --card-bg: rgba(30, 30, 30, 0.95); --border-color: #3c4043; }}
        html, body {{ height: 100%; margin: 0; background-color: var(--bg-color); color: var(--text-color); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; touch-action: manipulation; transition: background 0.3s, color 0.3s; }}
        body {{ padding-bottom: 75px; }}
        .ram-mandir-bg {{ background-image: linear-gradient(to bottom, rgba(255, 243, 230, 0.88), rgba(255, 230, 204, 0.95)), url('https://upload.wikimedia.org/wikipedia/commons/e/e0/Ram_Mandir_Ayodhya.jpg'); background-size: cover; background-position: center; min-height: 100vh; }}
        body.dark-mode .ram-mandir-bg {{ background-image: linear-gradient(to bottom, rgba(18, 18, 18, 0.90), rgba(20, 20, 20, 0.96)), url('https://upload.wikimedia.org/wikipedia/commons/e/e0/Ram_Mandir_Ayodhya.jpg'); }}
        .top-bar-chrome {{ display: flex; justify-content: space-between; align-items: center; padding: 12px 18px; }}
        .creator-badge {{ font-size: 13px; font-weight: 600; color: #d96b00; }}
        .top-right-actions {{ display: flex; align-items: center; gap: 8px; }}
        .dots-btn, .account-btn, .theme-btn {{ background: none; border: none; font-size: 20px; color: #444746; cursor: pointer; padding: 4px 8px; border-radius: 50%; text-decoration: none; }}
        .bharat-logo {{ font-size: 52px; font-weight: 700; letter-spacing: -1.5px; margin-top: 15px; }}
        .google-search-container {{ max-width: 580px; width: 92%; margin: 24px auto 16px auto; position: relative; }}
        .google-input {{ height: 54px; border-radius: 27px; padding-left: 52px; padding-right: 90px; border: 2px solid #ffaa44; background: var(--card-bg); color: var(--text-color); box-shadow: 0 4px 12px rgba(255, 153, 51, 0.2); font-size: 16px; }}
        .search-left-icon {{ position: absolute; left: 18px; top: 17px; color: #e67300; font-size: 18px; }}
        .bottom-nav-bar {{ position: fixed; bottom: 0; left: 0; right: 0; background: var(--bg-color); border-top: 1px solid var(--border-color); display: flex; justify-content: space-around; padding: 8px 0; z-index: 9998; }}
        .nav-link-item {{ text-decoration: none; color: #5f6368; font-size: 11px; text-align: center; display: flex; flex-direction: column; align-items: center; flex: 1; }}
        .nav-link-item.active {{ color: #ff7700; font-weight: 600; }}
    </style>
</head>
<body>
"""

def get_footer(active_tab="home"):
    return f"""
<div class="bottom-nav-bar">
    <a href="/" class="nav-link-item {'active' if active_tab == 'home' else ''}"><i class="bi bi-house-door-fill fs-5"></i>Home</a>
    <a href="/remove_ads" class="nav-link-item {'active' if active_tab == 'noads' else ''}"><i class="bi bi-shield-slash-fill fs-5 text-warning"></i>No Ads</a>
    <a href="/games" class="nav-link-item {'active' if active_tab == 'games' else ''}"><i class="bi bi-controller fs-5"></i>Games</a>
    <a href="/my_history" class="nav-link-item {'active' if active_tab == 'history' else ''}"><i class="bi bi-clock-history fs-5"></i>History</a>
</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

# -------------------------------------------------------------
# 💸 DIRECT UPI PAYMENT ROUTE
# -------------------------------------------------------------
@app.route("/remove_ads", methods=["GET", "POST"])
def remove_ads():
    if not session.get("user_logged") and not session.get("owner_logged"):
        return redirect("/user_login")

    premium = is_user_premium()
    msg = ""
    username = session.get("username", "")

    if request.method == "POST":
        utr_no = request.form.get("utr_number", "").strip()
        if utr_no and len(utr_no) >= 10:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            try:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    "INSERT INTO payment_requests (username, utr_number, status, timestamp) VALUES (?, ?, 'pending', ?)",
                    (username, utr_no, now)
                )
                conn.commit()
                msg = "✅ आपकी UTR सबमिट हो गई है! Owner के वेरिफिकेशन के बाद तुरंत Ads हट जाएंगे।"
            except sqlite3.IntegrityError:
                msg = "⚠️ यह UTR पहले ही सबमिट किया जा चुका है!"
            conn.close()
        else:
            msg = "⚠️ कृपया सही 12-अंकों का UTR / Transaction No. भरें!"

    # Dynamic QR Code Generator URL using Google Chart API
    upi_qr_url = f"https://chart.googleapis.com/chart?cht=qr&chs=250x250&chl=upi://pay?pa={YOUR_UPI_ID}&pn={quote_plus(YOUR_UPI_NAME)}&am=99&cu=INR"

    return get_html_header() + f"""
    <div class="container mt-4 mb-5" style="max-width: 500px;">
        <div class="bg-white p-4 rounded-4 shadow-sm border text-center">
            <div class="display-4 mb-2">🛡️</div>
            <h3 class="fw-bold text-primary">Direct Bank Payment</h3>
            <p class="text-muted small">0% Commission • सीधा आपके बैंक खाते में पेमेंट</p>
            <hr>

            {f'''
            <div class="alert alert-success fw-bold p-3 my-4">
                🎉 बधाई हो! आप Premium Member हैं। आपके लिए सभी एड्स हटा दिए गए हैं।
            </div>
            ''' if premium else f'''
            {f'<div class="alert alert-info small">{msg}</div>' if msg else ''}

            <div class="card p-3 my-3 bg-light border-warning">
                <span class="badge bg-warning text-dark align-self-center mb-2">Lifetime Ad-Free Access</span>
                <div class="display-6 fw-bold text-danger mb-3">₹99</div>

                <!-- UPI QR CODE -->
                <div class="bg-white p-2 rounded border d-inline-block mx-auto mb-3">
                    <img src="{upi_qr_url}" alt="UPI QR Code" style="width: 200px; height: 200px;">
                </div>

                <div class="small fw-bold text-dark mb-1">UPI ID: <span class="text-primary">{YOUR_UPI_ID}</span></div>
                <div class="text-muted small mb-3">GPay, PhonePe, Paytm या BHIM से QR स्कैन करके <b>₹99</b> भेजें।</div>

                <!-- UTR SUBMISSION FORM -->
                <form method="POST" class="mt-2">
                    <div class="mb-3">
                        <input type="text" name="utr_number" class="form-control text-center rounded-pill" placeholder="Enter 12-digit UTR / Ref No." required>
                    </div>
                    <button type="submit" class="btn btn-warning btn-lg fw-bold w-100 rounded-pill shadow-sm">
                        🚀 Submit UTR Number
                    </button>
                </form>
            </div>
            '''}

            <div class="mt-3">
                <a href="/" class="btn btn-outline-secondary btn-sm rounded-pill">Back to Home</a>
            </div>
        </div>
    </div>
    """ + get_footer("noads")

# -------------------------------------------------------------
# 👑 OWNER DASHBOARD (VERIFY UTR AND APPROVE REMOVE ADS)
# -------------------------------------------------------------
@app.route("/owner_dashboard", methods=["GET", "POST"])
def owner_dashboard():
    if not session.get("owner_logged"):
        return redirect("/owner_login")

    message = ""
    if request.method == "POST":
        action = request.form.get("action")
        target_user = request.form.get("username")
        req_id = request.form.get("req_id")

        if action == "approve":
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_premium = 1 WHERE username = ?", (target_user,))
            cursor.execute("UPDATE payment_requests SET status = 'approved' WHERE id = ?", (req_id,))
            conn.commit()
            conn.close()
            message = f"✅ Approved {target_user}! Ads removed successfully."
        elif action == "reject":
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("UPDATE payment_requests SET status = 'rejected' WHERE id = ?", (req_id,))
            conn.commit()
            conn.close()
            message = f"❌ Rejected payment request for {target_user}."

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, utr_number, status, timestamp FROM payment_requests ORDER BY id DESC")
    requests_list = cursor.fetchall()
    conn.close()

    req_rows = ""
    for r in requests_list:
        status_badge = "bg-warning" if r[3] == "pending" else ("bg-success" if r[3] == "approved" else "bg-danger")
        req_rows += f"""
        <tr>
            <td><b>{r[1]}</b></td>
            <td><code>{r[2]}</code></td>
            <td><span class="badge {status_badge}">{r[3]}</span></td>
            <td><small>{r[4]}</small></td>
            <td>
                {f'''
                <form method="POST" class="d-inline">
                    <input type="hidden" name="req_id" value="{r[0]}">
                    <input type="hidden" name="username" value="{r[1]}">
                    <button type="submit" name="action" value="approve" class="btn btn-sm btn-success py-0">Approve</button>
                    <button type="submit" name="action" value="reject" class="btn btn-sm btn-danger py-0">Reject</button>
                </form>
                ''' if r[3] == 'pending' else 'Done'}
            </td>
        </tr>
        """

    return get_html_header() + f"""
    <div class="container mt-4 mb-5" style="max-width: 800px;">
        <div class="bg-white p-4 rounded-4 shadow-sm border">
            <h4 class="mb-3 text-center">👑 Owner Control Center</h4>
            {f'<div class="alert alert-info">{message}</div>' if message else ''}

            <h5 class="text-primary mt-4 mb-3">💸 Pending Payment UTRs</h5>
            <div class="table-responsive">
                <table class="table table-bordered table-hover align-middle small">
                    <thead class="table-light">
                        <tr>
                            <th>User</th>
                            <th>UTR Number</th>
                            <th>Status</th>
                            <th>Time</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {req_rows if req_rows else '<tr><td colspan="5" class="text-center text-muted">No payment requests found.</td></tr>'}
                    </tbody>
                </table>
            </div>

            <div class="text-center mt-4"><a href="/" class="btn btn-outline-secondary btn-sm rounded-pill">Back to Home</a></div>
        </div>
    </div>
    """ + get_footer("home")

@app.route("/")
def home():
    username = session.get("username", "")
    account_url = "/account" if username or session.get("owner_logged") else "/user_login"

    return get_html_header() + f"""
    <div class="ram-mandir-bg">
        <div class="top-bar-chrome">
            <div class="creator-badge">🚀 Created by <b>Aman Giri</b></div>
            <a href="{account_url}" class="account-btn"><i class="bi bi-person-circle"></i></a>
        </div>
        <div class="container text-center pt-2">
            <div class="bharat-logo mb-1">
                <span style="color:#FF9933">B</span><span style="color:#000080">h</span><span style="color:#138808">arat</span> 🛕
            </div>
            <p class="fw-medium small mb-3" style="color: #d95100;">India's AI Search Engine 🇮🇳</p>

            <form action="/search" method="GET" class="google-search-container">
                <i class="bi bi-search search-left-icon"></i>
                <input type="text" name="q" class="form-control google-input" placeholder="Search web or AI..." required>
            </form>
        </div>
    </div>
    """ + get_footer("home")

@app.route("/user_login", methods=["GET", "POST"])
def user_login():
    error = ""
    if request.method == "POST":
        username, password = request.form.get("username"), request.form.get("password")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = cursor.fetchone()
        conn.close()
        if user:
            session.permanent = True
            session["user_logged"] = True
            session["username"] = username
            return redirect("/")
        error = "गलत यूज़रनेम या पासवर्ड!"
    return get_html_header() + f"""
    <div class="container mt-5" style="max-width: 400px;">
        <form method="POST" class="bg-white p-4 rounded-4 shadow-sm border">
            <h4 class="mb-3 text-center">User Login</h4>
            {f'<div class="alert alert-danger small">{error}</div>' if error else ''}
            <input type="text" name="username" class="form-control mb-3" placeholder="Username" required>
            <input type="password" name="password" class="form-control mb-3" placeholder="Password" required>
            <button type="submit" class="btn btn-primary w-100 rounded-pill">Login</button>
        </form>
    </div>
    """ + get_footer("home")

@app.route("/owner_login", methods=["GET", "POST"])
def owner_login():
    error = ""
    if request.method == "POST":
        username, password = request.form.get("username"), request.form.get("password")
        if username == OWNER_USERNAME and password == OWNER_PASSWORD:
            session.permanent = True
            session["owner_logged"] = True
            return redirect("/owner_dashboard")
        error = "गलत Owner क्रेडेंशियल!"
    return get_html_header() + f"""
    <div class="container mt-5" style="max-width: 400px;">
        <form method="POST" class="bg-white p-4 rounded-4 shadow-sm border">
            <h4 class="mb-3 text-center text-danger">👑 Owner Login</h4>
            {f'<div class="alert alert-danger small">{error}</div>' if error else ''}
            <input type="text" name="username" class="form-control mb-3" placeholder="Owner Username" required>
            <input type="password" name="password" class="form-control mb-3" placeholder="Owner Password" required>
            <button type="submit" class="btn btn-danger w-100 rounded-pill">Login to Dashboard</button>
        </form>
    </div>
    """ + get_footer("home")

if __name__ == "__main__":
    app.run(debug=True, port=5000)
