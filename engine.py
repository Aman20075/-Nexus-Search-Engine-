import sqlite3
import difflib

class BharatAdvancedEngine:
    def __init__(self):
        self.documents = []

    def index_item(self, title, url, snippet, category, file_type="web", country="IN"):
        self.documents.append({
            "title": title,
            "url": url,
            "snippet": snippet,
            "category": category,
            "file_type": file_type.lower(),
            "country": country.upper(),
            "search_text": f"{title} {snippet} {category} {file_type}".lower()
        })

    def search_advanced(self, query, file_type="all", country="all", top_k=10):
        if not self.documents: return []
        
        query_lower = query.lower()
        results = []

        for doc in self.documents:
            # File Type & Region Filters
            if file_type != "all" and doc["file_type"] != file_type.lower():
                continue
            if country != "all" and doc["country"] != country.upper():
                continue

            score = difflib.SequenceMatcher(None, query_lower, doc["search_text"]).ratio()
            if query_lower in doc["search_text"]:
                score += 0.5

            if score > 0.05:
                results.append((score, doc))

        results.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in results[:top_k]]

bharat_engine = BharatAdvancedEngine()

def sync_db_to_engine():
    try:
        conn = sqlite3.connect("search_engine.db")
        cursor = conn.cursor()
        cursor.execute("SELECT title, url, snippet, category FROM local_search_index")
        rows = cursor.fetchall()
        conn.close()
        for r in rows:
            bharat_engine.index_item(r[0], r[1], r[2], r[3])
    except Exception:
        pass

sync_db_to_engine()
