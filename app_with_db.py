from flask import Flask, request, redirect, url_for
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

# Home Page (Registration & Login Links)
@app.route("/")
def home():
    return """
    <div style='text-align: center; font-family: Arial; margin-top: 50px;'>
        <h1 style='color: #2c3e50;'>🌐 Welcome to Web Auth Portal</h1>
        <div style='background: #ecf0f1; display: inline-block; padding: 30px; border-radius: 10px;'>
            <h3>Chhooniye Aap Kya Karna Chahte Hain:</h3>
            <br>
            <a href='/register_page' style='padding: 10px 20px; background: #27ae60; color: white; text-decoration: none; border-radius: 5px; font-weight: bold;'>1. New Account Banayein (Register)</a>
            <br><br><br>
            <a href='/login_page' style='padding: 10px 20px; background: #2980b9; color: white; text-decoration: none; border-radius: 5px; font-weight: bold;'>2. Existing User Login Karein</a>
        </div>
    </div>
    """

# ----------------- REGISTRATION -----------------
@app.route("/register_page")
def register_page():
    return """
    <div style='text-align: center; font-family: Arial; margin-top: 50px;'>
        <h2>📝 Create New Account</h2>
        <form action='/register' method='POST' style='display: inline-block; background: #f8f9fa; padding: 25px; border-radius: 8px; border: 1px solid #ddd;'>
            <label><b>Username:</b></label><br>
            <input type='text' name='username' required style='padding: 8px; width: 200px; margin: 10px 0;'><br>
            <label><b>Password:</b></label><br>
            <input type='password' name='password' required style='padding: 8px; width: 200px; margin: 10px 0;'><br><br>
            <button type='submit' style='padding: 8px 20px; background: #27ae60; color: white; border: none; border-radius: 4px; cursor: pointer;'>Register</button>
        </form>
        <br><br><a href='/'>← Home Page</a>
    </div>
    """

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
        return f"""
        <div style='text-align: center; font-family: Arial; margin-top: 50px;'>
            <h2 style='color: #27ae60;'>✅ Account Created Successfully!</h2>
            <p>Ab aap login kar sakte hain.</p>
            <a href='/login_page' style='color: #2980b9;'>Click Here to Login ➔</a>
        </div>
        """
    except sqlite3.IntegrityError:
        return "<div style='text-align: center; font-family: Arial; margin-top: 50px;'><h2 style='color: red;'>❌ Username Pehle Se Maujood Hai!</h2><a href='/register_page'>Try Again</a></div>"

# ----------------- LOGIN -----------------
@app.route("/login_page")
def login_page():
    return """
    <div style='text-align: center; font-family: Arial; margin-top: 50px;'>
        <h2>🔐 User Login</h2>
        <form action='/login' method='POST' style='display: inline-block; background: #f8f9fa; padding: 25px; border-radius: 8px; border: 1px solid #ddd;'>
            <label><b>Username:</b></label><br>
            <input type='text' name='username' required style='padding: 8px; width: 200px; margin: 10px 0;'><br>
            <label><b>Password:</b></label><br>
            <input type='password' name='password' required style='padding: 8px; width: 200px; margin: 10px 0;'><br><br>
            <button type='submit' style='padding: 8px 20px; background: #2980b9; color: white; border: none; border-radius: 4px; cursor: pointer;'>Login</button>
        </form>
        <br><br><a href='/'>← Home Page</a>
    </div>
    """

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
        return f"""
        <div style='text-align: center; font-family: Arial; margin-top: 50px;'>
            <h1 style='color: #27ae60;'>🎉 Welcome to Your Dashboard, {username}!</h1>
            <p style='font-size: 18px;'>Aapne successfully database me authentication verify kar liya hai!</p>
            <br>
            <a href='/' style='color: #e74c3c; font-size: 16px;'>Logout</a>
        </div>
        """
    else:
        return """
        <div style='text-align: center; font-family: Arial; margin-top: 50px;'>
            <h2 style='color: #e74c3c;'>❌ Invalid Username or Password!</h2>
            <a href='/login_page'>Try Again ➔</a>
        </div>
        """

if __name__ == "__main__":
    app.run(debug=True)
