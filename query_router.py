# query_router.py
import re

class BharatQueryRouter:
    def __init__(self):
        self.gov_keywords = ["yojana", "scheme", "sarkari", "pan card", "aadhaar", "passport", "digilocker", "epfo", "pm kisan", "ration card"]
        self.code_keywords = ["code", "python", "javascript", "function", "bug", "error", "api", "html", "css", "sql"]
        self.finance_keywords = ["stock", "share price", "mutual fund", "ipo", "loan", "emi", "sip calculator", "gold price"]
        self.news_keywords = ["news", "khabar", "samachar", "breaking", "latest update", "today news"]

    def detect_intent(self, query: str) -> dict:
        q_lower = query.lower()
        
        # 1. Government / Bharat Knowledge Intent
        if any(kw in q_lower for kw in self.gov_keywords):
            return {"category": "government", "priority_engine": "knowledge_graph", "mode": "trusted_facts"}
        
        # 2. Developer / Coding Intent
        if any(kw in q_lower for kw in self.code_keywords):
            return {"category": "developer", "priority_engine": "code_agent", "mode": "technical"}
            
        # 3. Finance / Market Intent
        if any(kw in q_lower for kw in self.finance_keywords):
            return {"category": "finance", "priority_engine": "finance_tracker", "mode": "data_table"}
            
        # 4. News / Realtime Intent
        if any(kw in q_lower for kw in self.news_keywords):
            return {"category": "news", "priority_engine": "live_news_rss", "mode": "realtime"}
            
        return {"category": "general", "priority_engine": "hybrid_search", "mode": "standard"}
