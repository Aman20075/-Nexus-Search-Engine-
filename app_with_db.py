from flask import Flask, request, render_template_string
import sqlite3
import os

app = Flask(__name__)

# Database path handle karne ke liye (Cloud-Friendly)
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

# App start hone par DB initialize karein
init_db()

@app.route("/")
def home():
    return """
    <div style='text-align: center; font-family: Arial; margin-top: 50px;'>
        <h1 style='color: #2c3e50;'>🔐 User Registration System</h1>
        <p style='color: #27ae60;'>Status: Server Online & Running Live! 🚀</p>
        <form action='/register' method='POST' style='display: inline-block; text-align: left; background: #ecf0f1; padding: 25px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
            <label><b>Username:</b></label><br>
            <input type='text' name='username' required style='padding: 8px; width: 220px; margin-top: 5px; margin-bottom: 15px;'><br>
            <label><b>Password:</b></label><br>
            <input type='password' name='password' required style='padding: 8px; width: 220px; margin-top: 5px; margin-bottom: 20px;'><br>
            <button type='submit' style='padding: 10px 20px; background: #27ae60; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; width: 100%;'>Register User</button>
        </form>
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
            <h2 style='color: #27ae60;'>✅ Success! User '{username}' Saved to Database!</h2>
            <br>
            <a href='/' style='text-decoration: none; color: #3498db; font-size: 18px;'>← Back to Form</a>
        </div>
        """
    except sqlite3.IntegrityError:
        return f"""
        <div style='text-align: center; font-family: Arial; margin-top: 50px;'>
            <h2 style='color: #e74c3c;'>❌ Error: Username '{username}' pehle se maujood hai!</h2>
            <br>
            <a href='/' style='text-decoration: none; color: #3498db; font-size: 18px;'>← Back to Form</a>
        </div>
        """
    except Exception as e:
        return f"""
        <div style='text-align: center; font-family: Arial; margin-top: 50px;'>
            <h2 style='color: #e74c3c;'>❌ Something went wrong: {str(e)}</h2>
            <br>
            <a href='/'>← Back to Form</a>
        </div>
        """

if __name__ == "__main__":
    app.run(debug=True)
