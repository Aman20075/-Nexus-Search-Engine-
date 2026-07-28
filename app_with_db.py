from flask import Flask, request
import sqlite3

app = Flask(__name__)

# Database setup function
def init_db():
    conn = sqlite3.connect('users.db')
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

# Home Page / Register Form
@app.route("/")
def home():
    return """
    <div style='text-align: center; font-family: Arial; margin-top: 50px;'>
        <h1 style='color: #2c3e50;'>🔐 User Registration (Database)</h1>
        <form action='/register' method='POST' style='display: inline-block; text-align: left; background: #ecf0f1; padding: 20px; border-radius: 8px;'>
            <label>Username:</label><br>
            <input type='text' name='username' required style='padding: 8px; width: 200px; margin-bottom: 10px;'><br>
            <label>Password:</label><br>
            <input type='password' name='password' required style='padding: 8px; width: 200px; margin-bottom: 15px;'><br>
            <button type='submit' style='padding: 8px 15px; background: #27ae60; color: white; border: none; border-radius: 4px; cursor: pointer;'>Register</button>
        </form>
    </div>
    """

# Register Endpoint
@app.route("/register", methods=['POST'])
def register():
    username = request.form['username']
    password = request.form['password']
    
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        conn.close()
        return f"""
        <div style='text-align: center; font-family: Arial; margin-top: 50px;'>
            <h2 style='color: #27ae60;'>✅ Success! User '{username}' Database me Save ho gaya!</h2>
            <a href='/'>← Back to Form</a>
        </div>
        """
    except sqlite3.IntegrityError:
        return f"""
        <div style='text-align: center; font-family: Arial; margin-top: 50px;'>
            <h2 style='color: #e74c3c;'>❌ Error: Username '{username}' pehle se maujood hai!</h2>
            <a href='/'>← Back to Form</a>
        </div>
        """

if __name__ == "__main__":
    app.run(debug=True)