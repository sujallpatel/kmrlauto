import random
from typing import List, Dict, Any

class SyntheticDocumentGenerator:
    """
    Generates realistic test document feature sets simulating KMRL document processing requirements.
    """
    
    @staticmethod
    def generate_document_batch(count: int = 30, seed: int = 42) -> List[Dict[str, Any]]:
        random.seed(seed)
        batch = []
        
        doc_types = ["Safety Circular", "Engineering Manual", "Regulatory Compliance", "Vendor Invoice", "Routine Log"]
        languages = ["English", "Malayalam", "Mixed"]
        
        for i in range(1, count + 1):
            doc_type = random.choice(doc_types)
            lang = random.choice(languages)
            
            if "Safety" in doc_type:
                safety = random.uniform(80.0, 100.0)
                regulatory = random.uniform(70.0, 95.0)
                business = random.uniform(60.0, 90.0)
                deadline = random.uniform(70.0, 100.0)
                page_count = random.randint(2, 40)
            elif "Engineering" in doc_type:
                safety = random.uniform(20.0, 60.0)
                regulatory = random.uniform(30.0, 70.0)
                business = random.uniform(50.0, 80.0)
                deadline = random.uniform(20.0, 50.0)
                page_count = random.randint(100, 300)
            else:
                safety = random.uniform(0.0, 40.0)
                regulatory = random.uniform(10.0, 50.0)
                business = random.uniform(20.0, 60.0)
                deadline = random.uniform(10.0, 40.0)
                page_count = random.randint(1, 30)
                
            is_scanned = random.choice([True, False])
            scanned_pages = int(page_count * random.uniform(0.5, 1.0)) if is_scanned else random.randint(0, 5)
            ocr_req = scanned_pages > 0 or lang == "Malayalam"
            file_size_bytes = int(page_count * random.uniform(50, 200) * 1024)  # ~50KB-200KB per page
            
            batch.append({
                "doc_id": i,
                "filename": f"doc_{i:03d}_{doc_type.replace(' ', '_')}.pdf",
                "file_bytes": b"synthetic_pdf_content_" * (page_count * 10),
                "page_count": page_count,
                "scanned_pages": scanned_pages,
                "text_pages": page_count - scanned_pages,
                "ocr_required": ocr_req,
                "language": lang,
                "document_type": doc_type,
                "safety_criticality": round(safety, 1),
                "regulatory_importance": round(regulatory, 1),
                "business_importance": round(business, 1),
                "deadline_urgency": round(deadline, 1),
                "file_size": file_size_bytes
            })
            
        return batch
