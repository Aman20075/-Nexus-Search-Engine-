# engine.py - Render-Safe Lightweight Search Engine
import sqlite3
import difflib

class BharatVectorEngine:
    def __init__(self):
        self.documents = []

    def index_item(self, title, url, snippet, category):
        self.documents.append({
            "title": title,
            "url": url,
            "snippet": snippet,
            "category": category,
            "search_text": f"{title} {snippet} {category}".lower()
        })

    def search(self, query, top_k=5):
        if not self.documents:
            return []
        
        query = query.lower()
        scored_results = []
        
        for doc in self.documents:
            score = difflib.SequenceMatcher(None, query, doc["search_text"]).ratio()
            if query in doc["search_text"]:
                score += 0.5 
                
            if score > 0.05:
                scored_results.append((score, doc))
        
        scored_results.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored_results[:top_k]]

bharat_engine = BharatVectorEngine()

def sync_db_to_vector_engine(db_path="search_engine.db"):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT title, url, snippet, category FROM local_search_index")
        rows = cursor.fetchall()
        conn.close()

        for r in rows:
            bharat_engine.index_item(r[0], r[1], r[2], r[3])
    except Exception as e:
        print(f"Engine Sync Warning: {e}")
