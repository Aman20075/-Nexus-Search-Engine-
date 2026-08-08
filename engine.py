import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import sqlite3

class BharatVectorEngine:
    def __init__(self):
        # 1. AI Embedding Model जो टेक्स्ट का 'अर्थ' समझता है
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.dimension = 384
        self.index = faiss.IndexFlatL2(self.dimension)
        self.documents = []

    def index_item(self, title, url, snippet, category):
        """नए कंटेंट को Vector Database में जोड़ना"""
        text_to_encode = f"{title} {snippet} {category}"
        vector = self.model.encode([text_to_encode])[0].astype('float32')
        self.index.add(np.array([vector]))
        self.documents.append({
            "title": title,
            "url": url,
            "snippet": snippet,
            "category": category
        })

    def search(self, query, top_k=5):
        """गूगल से भी तेज़ 'Semantic' AI सर्च"""
        if self.index.ntotal == 0:
            return []
        
        query_vector = self.model.encode([query])[0].astype('float32')
        distances, indices = self.index.search(np.array([query_vector]), top_k)
        
        results = []
        for idx in indices[0]:
            if idx < len(self.documents) and idx >= 0:
                results.append(self.documents[idx])
        return results

# ग्लोबल इंजन इनीशियलाइजेशन
bharat_engine = BharatVectorEngine()

def sync_db_to_vector_engine(db_path="search_engine.db"):
    """SQLite डेटाबेस से सारे मास्टर लिंक्स को Vector Engine में लोड करना"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT title, url, snippet, category FROM local_search_index")
        rows = cursor.fetchall()
        conn.close()

        for r in rows:
            bharat_engine.index_item(r[0], r[1], r[2], r[3])
    except Exception as e:
        print(f"Vector Sync Warning: {e}")
