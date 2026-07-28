from flask import Flask, request, jsonify, redirect, url_for
import sqlite3
import requests

app = Flask(__name__)
DB_PATH = 'users.db'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Modern Google UI Header
HTML_HEADER = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nexus Search Engine</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css">
    <style>
        body { background: #ffffff; font-family: 'Segoe UI', Arial, sans-serif; }
        .google-logo { font-size: 65px; font-weight: 700; letter-spacing: -2px; }
        .search-box-container { max-width: 584px; margin: 0 auto; position: relative; }
        .search-input { height: 46px; border-radius: 24px; padding-left: 45px; padding-right: 45px; border: 1px solid #dfe1e5; box-shadow: none; }
        .search-input:focus { border-color: transparent; box-shadow: 0 1px 6px rgba(32,33,36,0.28); }
        .search-icon { position: absolute; left: 16px; top: 12px; color: #9aa0a6; font-size: 18px; }
        .mic-icon { position: absolute; right: 16px; top: 11px; color: #4285f4; font-size: 20px; cursor: pointer; }
        .result-card { max-width: 650px; margin-bottom: 24px; }
        .result-title { color: #1a0dab; text-decoration: none; font-size: 20px; font-weight: 400; }
        .result-title:hover { text-decoration: underline; }
        .result-url { color: #202124; font-size: 14px; margin-bottom: 4px; }
        .result-snippet { color: #4d5156; font-size: 14px; line-height: 1.58; }
        .nav-link.active { border-bottom: 3px solid #1a73e8 !important; color: #1a73e8 !important; font-weight: bold; }
    </style>
</head>
<body>
"""

HTML_FOOTER = """
<script>
function startVoiceSearch() {
    if ('webkitSpeechRecognition' in window) {
        var recognition = new webkitSpeechRecognition();
        recognition.lang = 'en-US';
        recognition.start();
        recognition.onresult = function(event) {
            document.getElementById('searchInput').value = event.results[0][0].transcript;
            document.getElementById('searchForm').submit();
        };
    } else {
        alert("Voice search is not supported in this browser.");
    }
}
</script>
</body>
</html>
"""

# ----------------- HOME PAGE -----------------
@app.route("/")
def home():
    return HTML_HEADER + """
    <div class="container text-center mt-5 pt-4">
        <div class="google-logo mb-3">
            <span style="color:#4285F4">N</span><span style="color:#EA4335">e</span><span style="color:#FBBC05">x</span><span style="color:#4285F4">u</span><span style="color:#34A853">s</span>
        </div>
        
        <form action="/search" method="GET" id="searchForm" class="search-box-container mb-4">
            <i class="bi bi-search search-icon"></i>
            <input type="text" name="q" id="searchInput" class="form-control search-input" placeholder="Search Nexus or type a URL" autocomplete="off" required>
            <i class="bi bi-mic-fill mic-icon" onclick="startVoiceSearch()" title="Search by voice"></i>
            
            <div class="mt-4">
                <button type="submit" class="btn btn-light border px-3 py-2 me-2 text-secondary">Nexus Search</button>
                <a href="/login_page" class="btn btn-light border px-3 py-2 text-secondary">User Portal</a>
            </div>
        </form>
    </div>
    """ + HTML_FOOTER

# ----------------- SEARCH RESULTS PAGE -----------------
@app.route("/search")
def search():
    query = request.args.get('q', '')
    if not query:
        return redirect("/")

    results = []
    try:
        # Fetching Live Internet Search Results via Wikipedia API
        url = f"https://en.wikipedia.org/w/api.php?action=opensearch&search={query}&limit=8&format=json"
        response = requests.get(url).json()
        
        titles = response[1]
        descriptions = response[2]
        urls = response[3]

        for i in range(len(titles)):
            results.append({
                'title': titles[i],
                'snippet': descriptions[i] if descriptions[i] else 'Click to view complete details on this topic.',
                'link': urls[i]
            })
    except Exception as e:
        results = []

    # Results Header & Tab Navigation
    header_nav = f"""
    <div class="border-bottom pt-3 px-4">
        <div class="d-flex align-items-center mb-3">
            <a href="/" class="google-logo text-decoration-none me-4" style="font-size: 30px;">
                <span style="color:#4285F4">N</span><span style="color:#EA4335">e</span><span style="color:#FBBC05">x</span><span style="color:#4285F4">u</span><span style="color:#34A853">s</span>
            </a>
            <form action="/search" method="GET" id="searchForm" class="search-box-container ms-0 flex-grow-1" style="max-width: 600px;">
                <i class="bi bi-search search-icon"></i>
                <input type="text" name="q" id="searchInput" value="{query}" class="form-control search-input" required>
                <i class="bi bi-mic-fill mic-icon" onclick="startVoiceSearch()"></i>
            </form>
        </div>
        
        <ul class="nav nav-tabs border-0 mt-2" style="margin-left: 130px;">
            <li class="nav-item"><a class="nav-link active border-0 text-secondary" href="#"><i class="bi bi-search me-1"></i> All</a></li>
            <li class="nav-item"><a class="nav-link border-0 text-secondary" href="#"><i class="bi bi-image me-1"></i> Images</a></li>
            <li class="nav-item"><a class="nav-link border-0 text-secondary" href="#"><i class="bi bi-newspaper me-1"></i> News</a></li>
        </ul>
    </div>
    
    <div class="container-fluid px-5 pt-3" style="margin-left: 110px;">
        <p class="text-muted small">About {len(results)} results for <b>{query}</b></p>
    """

    body_results = ""
    if results:
        for item in results:
            body_results += f"""
            <div class="result-card">
                <div class="result-url">{item['link']}</div>
                <a href="{item['link']}" target="_blank" class="result-title">{item['title']}</a>
                <div class="result-snippet mt-1">{item['snippet']}</div>
            </div>
            """
    else:
        body_results = "<div class='alert alert-light border'>No relevant search results found.</div>"

    body_results += "</div>"

    return HTML_HEADER + header_nav + body_results + HTML_FOOTER

# ----------------- LOGIN / PORTAL ROUTES -----------------
@app.route("/login_page")
def login_page():
    return HTML_HEADER + """
    <div class="container mt-5">
        <div class="row justify-content-center">
            <div class="col-md-4">
                <div class="card p-4 shadow-sm border-0">
                    <h4 class="text-center mb-3">Sign in</h4>
                    <form action="/login" method="POST">
                        <div class="mb-3">
                            <input type="text" name="username" class="form-control" placeholder="Username" required>
                        </div>
                        <div class="mb-3">
                            <input type="password" name="password" class="form-control" placeholder="Password" required>
                        </div>
                        <button type="submit" class="btn btn-primary w-100">Next</button>
                    </form>
                    <div class="text-center mt-3"><a href="/" class="text-decoration-none">← Back to Search</a></div>
                </div>
            </div>
        </div>
    </div>
    """ + HTML_FOOTER

if __name__ == "__main__":
    app.run(debug=True)
