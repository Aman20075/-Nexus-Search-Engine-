# engine.py - Self-Reliant Instant Bharat Search Engine
import sqlite3
import difflib
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, quote_plus
import concurrent.futures

class BharatDirectWebCrawler:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def fetch_live_site(self, target_url):
        try:
            resp = requests.get(target_url, headers=self.headers, timeout=2.0)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                title = soup.title.string.strip() if soup.title and soup.title.string else target_url
                meta_desc = soup.find('meta', attrs={'name': 'description'})
                snippet = meta_desc['content'].strip() if meta_desc and 'content' in meta_desc.attrs else ""
                
                if not snippet:
                    paragraphs = [p.get_text().strip() for p in soup.find_all('p') if len(p.get_text().strip()) > 30]
                    snippet = paragraphs[0] if paragraphs else "आधिकारिक पोर्टल से सीधी जानकारी उपलब्ध है।"

                return {
                    "title": title[:80],
                    "url": target_url,
                    "snippet": snippet[:200],
                    "category": "Live Web"
                }
        except Exception:
            pass
        return None

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
            "pm kisan": {"title": "PM-KISAN (प्रधानमंत्री किसान सम्मान निधि)", "category": "Government Scheme", "department": "Ministry of Agriculture & Farmers Welfare", "benefits": "₹6,000 प्रति वर्ष (₹2,000 की 3 समान किस्तों में)।", "official_website": "https://pmkisan.gov.in/"},
            "pan card": {"title": "Permanent Account Number (PAN)", "category": "Official Identity Document", "department": "Income Tax Department, Govt of India", "benefits": "वित्तीय लेनदेन और टैक्स रिटर्न हेतु आवश्यक।", "official_website": "https://eportal.incometax.gov.in/"}
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
        self.crawler = BharatDirectWebCrawler()

    def index_item(self, title, url, snippet, category):
        for doc in self.documents:
            if doc["url"] == url: return
        self.documents.append({
            "title": title,
            "url": url,
            "snippet": snippet,
            "category": category,
            "search_text": f"{title} {snippet} {category}".lower()
        })

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
        intent = self.router.detect_intent(query)
        kg_card = self.kg.search_knowledge_base(query)
        results = self.search(query)
        
        return {
            "intent": intent,
            "knowledge_card": kg_card,
            "results": results
        }

bharat_engine = BharatVectorEngine()

def sync_db_to_vector_engine(db_path="search_engine.db"):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT title, url, snippet, category FROM local_search_index")
        rows = cursor.fetchall()
        conn.close()
        for r in rows: bharat_engine.index_item(r[0], r[1], r[2], r[3])
    except Exception as e: print(f"Engine Sync Warning: {e}")
