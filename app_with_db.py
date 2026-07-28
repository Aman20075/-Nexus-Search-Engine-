ffrom flask import Flask, request, redirect, url_for
import requests

app = Flask(__name__)

# 🔑 Apni Google Keys Yahan Daalein:
GOOGLE_API_KEY = "YOUR_GOOGLE_API_KEY_HERE"
SEARCH_ENGINE_ID = "YOUR_SEARCH_ENGINE_ID_HERE"

HTML_HEADER = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bharat Search Engine</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css">
    <style>
        body { background: #ffffff; font-family: 'Segoe UI', Arial, sans-serif; }
        .bharat-logo { font-size: 65px; font-weight: 700; letter-spacing: -1px; }
        .search-box-container { max-width: 584px; margin: 0 auto; position: relative; }
        .search-input { height: 46px; border-radius: 24px; padding-left: 45px; padding-right: 45px; border: 1px solid #dfe1e5; }
        .search-input:focus { border-color: transparent; box-shadow: 0 1px 6px rgba(32,33,36,0.28); }
        .search-icon { position: absolute; left: 16px; top: 12px; color: #9aa0a6; font-size: 18px; }
        .result-card { max-width: 650px; margin-bottom: 24px; }
        .result-title { color: #1a0dab; text-decoration: none; font-size: 18px; font-weight: 400; }
        .result-title:hover { text-decoration: underline; }
        .result-url { color: #202124; font-size: 13px; margin-bottom: 2px; }
        .result-snippet { color: #4d5156; font-size: 14px; line-height: 1.58; }
    </style>
</head>
<body>
"""

HTML_FOOTER = "</body></html>"

# ----------------- HOME PAGE -----------------
@app.route("/")
def home():
    return HTML_HEADER + """
    <div class="container text-center mt-5 pt-4">
        <div class="bharat-logo mb-2">
            <span style="color:#FF9933">B</span><span style="color:#FF9933">h</span><span style="color:#000080">a</span><span style="color:#138808">r</span><span style="color:#138808">a</span><span style="color:#138808">t</span>
        </div>
        <p class="text-muted mb-4">India's Own Web Search Engine 🇮🇳</p>

        <form action="/search" method="GET" class="search-box-container mb-4">
            <i class="bi bi-search search-icon"></i>
            <input type="text" name="q" class="form-control search-input" placeholder="Search the web with Bharat..." required>
            <div class="mt-4">
                <button type="submit" class="btn btn-light border px-4 py-2 me-2">Bharat Search</button>
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
        url = f"https://www.googleapis.com/customsearch/v1?q={query}&key={GOOGLE_API_KEY}&cx={SEARCH_ENGINE_ID}"
        response = requests.get(url).json()
        
        if "items" in response:
            for item in response["items"]:
                results.append({
                    'title': item.get('title'),
                    'snippet': item.get('snippet'),
                    'link': item.get('link')
                })
    except Exception as e:
        results = []

    header_nav = f"""
    <div class="border-bottom pt-3 px-4">
        <div class="d-flex align-items-center mb-3">
            <a href="/" class="bharat-logo text-decoration-none me-4" style="font-size: 30px;">
                <span style="color:#FF9933">B</span><span style="color:#FF9933">h</span><span style="color:#000080">a</span><span style="color:#138808">r</span><span style="color:#138808">a</span><span style="color:#138808">t</span>
            </a>
            <form action="/search" method="GET" class="search-box-container ms-0 flex-grow-1" style="max-width: 600px;">
                <i class="bi bi-search search-icon"></i>
                <input type="text" name="q" value="{query}" class="form-control search-input" required>
            </form>
        </div>
    </div>
    <div class="container-fluid px-5 pt-3" style="margin-left: 110px;">
        <p class="text-muted small">Search results for <b>{query}</b></p>
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
        body_results = "<div class='alert alert-warning'>Results loading... API Key setup verify karein.</div>"

    body_results += "</div>"
    return HTML_HEADER + header_nav + body_results + HTML_FOOTER

if __name__ == "__main__":
    app.run(debug=True)
