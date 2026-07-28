from flask import Flask, request, redirect, url_for
import requests

app = Flask(__name__)

HTML_HEADER = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bharat Search Engine</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background: #ffffff; font-family: Arial, sans-serif; }
        .bharat-logo { font-size: 60px; font-weight: 700; }
        .search-box { max-width: 580px; margin: 0 auto; }
        .search-input { height: 46px; border-radius: 24px; padding: 0 20px; border: 1px solid #dfe1e5; }
    </style>
</head>
<body>
"""

HTML_FOOTER = "</body></html>"

@app.route("/")
def home():
    return HTML_HEADER + """
    <div class="container text-center mt-5 pt-4">
        <div class="bharat-logo mb-2">
            <span style="color:#FF9933">B</span><span style="color:#FF9933">h</span><span style="color:#000080">a</span><span style="color:#138808">r</span><span style="color:#138808">a</span><span style="color:#138808">t</span>
        </div>
        <p class="text-muted mb-4">India's Own Web Search Engine 🇮🇳</p>

        <form action="/search" method="GET" class="search-box">
            <input type="text" name="q" class="form-control search-input mb-3" placeholder="Search the web with Bharat..." required>
            <button type="submit" class="btn btn-light border px-4 py-2">Bharat Search</button>
        </form>
    </div>
    """ + HTML_FOOTER

@app.route("/search")
def search():
    query = request.args.get('q', '')
    if not query:
        return redirect("/")

    results = []
    try:
        url = f"https://en.wikipedia.org/w/api.php?action=opensearch&search={query}&limit=6&format=json"
        response = requests.get(url).json()
        titles = response[1]
        descriptions = response[2]
        urls = response[3]

        for i in range(len(titles)):
            snippet_text = descriptions[i] if descriptions[i] else "Click to view complete details."
            results.append({
                'title': titles[i],
                'snippet': snippet_text,
                'link': urls[i]
            })
    except Exception as e:
        results = []

    results_html = f"""
    <div class="container mt-4">
        <div class="d-flex align-items-center mb-4">
            <a href="/" class="bharat-logo text-decoration-none me-4" style="font-size: 28px;">
                <span style="color:#FF9933">B</span><span style="color:#FF9933">h</span><span style="color:#000080">a</span><span style="color:#138808">r</span><span style="color:#138808">a</span><span style="color:#138808">t</span>
            </a>
            <form action="/search" method="GET" class="flex-grow-1" style="max-width: 500px;">
                <input type="text" name="q" value="{query}" class="form-control search-input" required>
            </form>
        </div>
        <p class="text-muted small">Search results for: <b>{query}</b></p>
    """

    if results:
        for item in results:
            results_html += f"""
            <div class="mb-4" style="max-width: 600px;">
                <div style="color: #202124; font-size: 13px;">{item['link']}</div>
                <a href="{item['link']}" target="_blank" style="color: #1a0dab; font-size: 18px; text-decoration: none;">{item['title']}</a>
                <div style="color: #4d5156; font-size: 14px;">{item['snippet']}</div>
            </div>
            """
    else:
        results_html += "<div class='alert alert-warning'>No results found.</div>"

    results_html += "</div>"
    return HTML_HEADER + results_html + HTML_FOOTER

if __name__ == "__main__":
    app.run(debug=True)
