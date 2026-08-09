import sqlite3
from datetime import datetime, timedelta

DB_PATH = "search_engine.db"

def init_advanced_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. User Tiers & Limits Table (Free, VIP, VIP Pro, VIP Ultra)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_subscriptions (
            username TEXT PRIMARY KEY,
            tier TEXT DEFAULT 'Free',
            ai_daily_limit INTEGER DEFAULT 10,
            ai_used_today INTEGER DEFAULT 0,
            last_usage_date TEXT,
            expires_at TEXT
        )
    """)

    # 2. Research Workspace (Save Papers, PDF Summaries, Notes)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS research_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            title TEXT,
            notes TEXT,
            sources_json TEXT,
            created_at TEXT
        )
    """)

    # 3. Privacy Controls & History Auto-Delete
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS privacy_settings (
            username TEXT PRIMARY KEY,
            private_mode INTEGER DEFAULT 0,
            auto_delete_days INTEGER DEFAULT 30,
            allow_personalization INTEGER DEFAULT 1
        )
    """)

    # 4. Keyword & Topic Alerts
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            keyword TEXT,
            alert_type TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()

def get_user_tier(username):
    if not username: return "Free", 10, 0
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT tier, ai_daily_limit, ai_used_today FROM user_subscriptions WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return "Free", 10, 0
    return row[0], row[1], row[2]

init_advanced_db()
