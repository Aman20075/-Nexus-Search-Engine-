# engine.py
import sqlite3
import difflib

class BharatQueryRouter:
    def __init__(self):
        self.gov_keywords = ["yojana", "scheme", "sarkari", "pan card", "aadhaar", "passport", "digilocker", "epfo", "pm kisan", "ration card"]
        self.code_keywords = ["code", "python", "javascript", "function", "bug", "error", "api", "html", "css", "sql"]
        self.finance_keywords = ["stock", "share price", "mutual fund", "ipo", "loan", "emi", "sip calculator", "gold price"]
        self.news_keywords = ["news", "khabar", "samachar", "breaking", "latest update", "today news"]

    def detect_intent(self, query: str) -> dict:
        q_lower = query.lower()
        if any(kw in q_lower for kw in self.gov_keywords): return {"category": "government", "mode": "trusted_facts"}
        if any(kw in q_lower for kw in self.code_keywords): return {"category": "developer", "mode": "technical"}
        if any(kw in q_lower for kw in self.finance_keywords): return {"category": "finance", "mode": "data_table"}
        if any(kw in q_lower for kw in self.news_keywords): return {"category": "news", "mode": "realtime"}
        return {"category": "general", "mode": "standard"}

class BharatKnowledgeGraph:
    def __init__(self):
        self.db = {
            "pm kisan": {"title": "PM-KISAN", "category": "Government Scheme", "department": "Ministry of Agriculture", "benefits": "₹6,000 प्रति वर्ष", "official_website": "https://pmkisan.gov.in/"},
            "pan card": {"title": "PAN Card", "category": "Identity", "department": "Income Tax", "benefits": "Financial ID", "official_website": "https://eportal.incometax.gov.in/"}
        }
    def search_knowledge_base(self, query: str):
        q_lower = query.lower()
        for key, data in self.db.items():
            if key in q_lower: return data
        return None

class BharatVectorEngine:
    def __init__(self):
        self.documents = []
        self.router = BharatQueryRouter()
        self.kg = BharatKnowledgeGraph()

    def index_item(self, title, url, snippet, category):
        for doc in self.documents:
            if doc["url"] == url: return
        self.documents.append({"title": title, "url": url, "snippet": snippet, "category": category, "search_text": f"{title} {snippet} {category}".lower()})

    def search(self, query, top_k=5):
        if not self.documents: return []
        query_lower = query.lower()
        scored_results = []
        for doc in self.documents:
            score = difflib.SequenceMatcher(None, query_lower, doc["search_text"]).ratio()
            if query_lower in doc["search_text"]: score += 0.5
            if score > 0.05: scored_results.append((score, doc))
        scored_results.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored_results[:top_k]]

    def process_super_search(self, query):
        return {"intent": self.router.detect_intent(query), "knowledge_card": self.kg.search_knowledge_base(query), "results": self.search(query)}

bharat_engine = BharatVectorEngine()

def sync_db_to_vector_engine(db_path="search_engine.db"):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT title, url, snippet, category FROM local_search_index")
        rows = cursor.fetchall()
        conn.close()
        for r in rows: bharat_engine.index_item(r[0], r[1], r[2], r[3])
    except Exception as e: print(f"Engine Sync Error: {e}")
