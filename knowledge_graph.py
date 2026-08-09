# knowledge_graph.py

class BharatKnowledgeGraph:
    def __init__(self):
        self.db = {
            "pm kisan": {
                "title": "PM-KISAN (प्रधानमंत्री किसान सम्मान निधि)",
                "category": "Government Scheme",
                "department": "Ministry of Agriculture & Farmers Welfare",
                "benefits": "₹6,000 प्रति वर्ष (₹2,000 की 3 समान किस्तों में सीधे बैंक खाते में)।",
                "eligibility": "सभी भूमिधारक किसान परिवार।",
                "official_website": "https://pmkisan.gov.in/",
                "key_actions": ["e-KYC प्रक्रिया", "Beneficiary Status चेक करें", "नया किसान पंजीकरण"]
            },
            "pan card": {
                "title": "Permanent Account Number (PAN)",
                "category": "Official Identity Document",
                "department": "Income Tax Department, Govt of India",
                "benefits": "वित्तीय लेनदेन, आयकर रिटर्न दाखिल करने और बैंक खाता खोलने के लिए आवश्यक।",
                "official_website": "https://eportal.incometax.gov.in/",
                "key_actions": ["Instant e-PAN लागू करें", "Aadhaar-PAN लिंक स्थिति", "PAN सुधार"]
            }
        }

    def search_knowledge_base(self, query: str):
        q_lower = query.lower()
        for key, data in self.db.items():
            if key in q_lower:
                return data
        return None
