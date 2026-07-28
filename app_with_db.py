ffrom flask import Flask, request, redirect, url_for
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

HTML_HEADER = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nexus Search Engine</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background: #f8f9fa; font-family: Arial, sans-serif; }
        .google-logo { font-size: 50px; font-weight: bold; color: #4285F4; }
        .search-box { max-width: 600px; margin: 0 auto; }
        .result-card { background: white; padding: 15px; border-radius: 8px; margin-bottom: 12px; border: 1px solid #e0e0e0; }
        .result-title { color: #1a0dab; text-decoration: none; font-size: 18px; font-weight: bold; }
        .result-title:hover { text-decoration: underline; }
        .result-url { color: #006621; font-size: 14px; }
    </style>
</head>
<body>
<div class="container mt-5">
"""

HTML_FOOTER = """
</div>
</body>
</html>
"""

# Home Page (Google Jaisa Search Bar)
@app.route("/")
def home():
    return HTML_HEADER + """
    <div class="text-center mt-5">
        <div class="google-logo mb-3">
            <span style="color:#4285F4">N</span><span style="color:#EA4335">e</span><span style="color:#FBBC05">x</span><span style="color:#4285F4">u</span><span style="color:#34A853">s</span>
        </div>
        <p class="text-muted mb-4">Python Powered Search Engine</p>
        
        <form action="/search" method="GET" class="search-box">
            <div class="input-group mb-3">
                <input type="text" name="q" class="form-control form-control-lg rounded-pill px-4" placeholder="Search the web..." required>
            </div>
            <button type="submit" class="btn btn-primary px-4 py-2 me-2">Google Search</button>
            <a href="/login_page" class="btn btn-outline-secondary px-4 py-2">User Portal</a>
        </form>
    </div>
    """ + HTML_FOOTER

# Live Search Endpoint
@app.route("/search")
def search():
    query = request.args.get('q', '')
    if not query:
        return redirect("/")

    results = []
    try:
        # Wikipedia API se Live Web Data Search Karna
        url = f"https://en.wikipedia.org/w/api.php?action=opensearch&search={query}&limit=5&format=json"
        response = requests.get(url).json()
        
        titles = response[1]
        descriptions = response[2]
        urls = response[3]

        for i in range(len(titles)):
            results.append({
                'title': titles[i],
                'snippet': descriptions[i] if descriptions[i] else 'Click to read more details.',
                'link': urls[i]
            })
    except Exception as e:
        results = []

    # Display Search Results
    results_html = f"""
    <div class="search-box text-start">
        <div class="d-flex align-items-center mb-4">
            <a href="/" class="google-logo text-decoration-none me-3" style="font-size: 28px;">
                <span style="color:#4285F4">N</span><span style="color:#EA4335">e</span><span style="color:#FBBC05">x</span><span style="color:#4285F4">u</span><span style="color:#34A853">s</span>
            </a>
            <form action="/search" method="GET" class="w-100">
                <input type="text" name="q" value="{query}" class="form-control rounded-pill px-3">
            </form>
        </div>
        <p class="text-muted">Showing results for: <b>{query}</b></p>
    """

    if results:
        for item in results:
            results_html += f"""
            <div class="result-card">
                <a href="{item['link']}" target="_blank" class="result-title">{item['title']}</a>
                <div class="result-url">{item['link']}</div>
                <p class="mt-1 mb-0 text-secondary">{item['snippet']}</p>
            </div>
            """
    else:
        results_html += "<div class="alert alert-warning">No results found for your query.</div>"

    results_html += "<br><a href='/' class='btn btn-light'>← Home Page</a></div>"

    return HTML_HEADER + results_html + HTML_FOOTER

# Registered / Login Routes
@app.route("/login_page")
def login_page():
    return HTML_HEADER + """
    <div class="row justify-content-center">
        <div class="col-md-5">
            <div class="card p-4 mt-5">
                <h3 class="mb-3 text-center">🔐 Portal Login</h3>
                <form action="/login" method="POST">
                    <div class="mb-3">
                        <label class="form-label">Username</label>
                        <input type="text" name="username" class="form-control" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Password</label>
                        <input type="password" name="password" class="form-control" required>
                    </div>
                    <button type="submit" class="btn btn-primary w-100">Login</button>
                </form>
                <div class="text-center mt-3"><a href="/">← Back to Search</a></div>
            </div>
        </div>
    </div>
    """ + HTML_FOOTER

if __name__ == "__main__":
    app.run(debug=True)
