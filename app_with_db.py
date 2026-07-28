from flask import Flask, request, redirect, url_for
import sqlite3

app = Flask(__name__)

DB_PATH = 'users.db'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)from flask import Flask, request, redirect, url_for
import sqlite3

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

# Universal HTML Header with Bootstrap 5
HTML_HEADER = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nexus Cloud Portal</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background: #f4f6f9; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .card { border-radius: 12px; border: none; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
        .btn-custom { background: #6c5ce7; color: white; border-radius: 8px; }
        .btn-custom:hover { background: #5b4cc4; color: white; }
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

@app.route("/")
def home():
    return HTML_HEADER + """
    <div class="row justify-content-center">
        <div class="col-md-6 text-center">
            <div class="card p-5">
                <h1 class="text-primary fw-bold mb-3">🚀 Nexus Web Portal</h1>
                <p class="text-muted mb-4">User Authentication & Full-Stack Portal</p>
                <div class="d-grid gap-3">
                    <a href="/register_page" class="btn btn-success btn-lg">New Account (Register)</a>
                    <a href="/login_page" class="btn btn-primary btn-lg">Existing User (Login)</a>
                </div>
            </div>
        </div>
    </div>
    """ + HTML_FOOTER

@app.route("/register_page")
def register_page():
    return HTML_HEADER + """
    <div class="row justify-content-center">
        <div class="col-md-5">
            <div class="card p-4">
                <h3 class="mb-3 text-center">📝 Register</h3>
                <form action="/register" method="POST">
                    <div class="mb-3">
                        <label class="form-label">Username</label>
                        <input type="text" name="username" class="form-control" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Password</label>
                        <input type="password" name="password" class="form-control" required>
                    </div>
                    <button type="submit" class="btn btn-success w-100">Create Account</button>
                </form>
                <div class="text-center mt-3"><a href="/">← Back to Home</a></div>
            </div>
        </div>
    </div>
    """ + HTML_FOOTER

@app.route("/register", methods=['POST'])
def register():
    username = request.form['username']
    password = request.form['password']
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        conn.close()
        return HTML_HEADER + f"""
        <div class="text-center mt-5">
            <div class="alert alert-success">
                <h4>✅ Registration Successful!</h4>
                <p>Welcome onboard, {username}!</p>
            </div>
            <a href="/login_page" class="btn btn-primary">Go to Login Page</a>
        </div>
        """ + HTML_FOOTER
    except sqlite3.IntegrityError:
        return HTML_HEADER + """
        <div class="text-center mt-5">
            <div class="alert alert-danger">❌ Username already exists!</div>
            <a href="/register_page" class="btn btn-secondary">Try Again</a>
        </div>
        """ + HTML_FOOTER

@app.route("/login_page")
def login_page():
    return HTML_HEADER + """
    <div class="row justify-content-center">
        <div class="col-md-5">
            <div class="card p-4">
                <h3 class="mb-3 text-center">🔐 Login</h3>
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
                <div class="text-center mt-3"><a href="/">← Back to Home</a></div>
            </div>
        </div>
    </div>
    """ + HTML_FOOTER

@app.route("/login", methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
    user = cursor.fetchone()
    conn.close()

    if user:
        return HTML_HEADER + f"""
        <div class="row justify-content-center">
            <div class="col-md-8 text-center">
                <div class="card p-5">
                    <h2 class="text-success">🎉 Welcome to Dashboard, {username}!</h2>
                    <p class="text-muted mt-2">Authentication, DB persistence, and UI rendering verified.</p>
                    <div class="mt-4">
                        <a href="/" class="btn btn-outline-danger">Logout</a>
                    </div>
                </div>
            </div>
        </div>
        """ + HTML_FOOTER
    else:
        return HTML_HEADER + """
        <div class="text-center mt-5">
            <div class="alert alert-danger">❌ Invalid Credentials!</div>
            <a href="/login_page" class="btn btn-secondary">Try Again</a>
        </div>
        """ + HTML_FOOTER

if __name__ == "__main__":
    app.run(debug=True)
