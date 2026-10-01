import os
from typing import Dict, Any

class FeatureExtractor:
    """
    Extracts numerical and categorical feature vectors from uploaded documents.
    """
    
    @staticmethod
    def extract_features(
        file_path: str, 
        filename: str, 
        file_bytes: bytes, 
        meta_override: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        meta_override = meta_override or {}
        file_size = len(file_bytes) if file_bytes else (os.path.getsize(file_path) if os.path.exists(file_path) else 1024)
        
        file_ext = filename.split('.')[-1].lower() if '.' in filename else 'pdf'
        
        # Default fallback extraction
        page_count = meta_override.get("page_count", 1)
        scanned_pages = meta_override.get("scanned_pages", 0)
        text_pages = meta_override.get("text_pages", page_count - scanned_pages)
        language = meta_override.get("language", "English")
        ocr_required = meta_override.get("ocr_required", False)
        document_type = meta_override.get("document_type", "General")
        
        # Try inspecting real PDF if pypdf is available
        if file_ext == "pdf" and file_bytes and "page_count" not in meta_override:
            try:
                import io
                from pypdf import PdfReader
                reader = PdfReader(io.BytesIO(file_bytes))
                page_count = len(reader.pages)
                scanned_count = 0
                text_count = 0
                for page in reader.pages:
                    text = page.extract_text() or ""
                    if len(text.strip()) < 50:
                        scanned_count += 1
                    else:
                        text_count += 1
                scanned_pages = scanned_count
                text_pages = text_count
                ocr_required = scanned_pages > 0
            except Exception:
                pass

        # Calculate scan ratio & image density
        scan_ratio = scanned_pages / max(page_count, 1)
        if scan_ratio > 0.6:
            image_density = "HIGH"
        elif scan_ratio > 0.2:
            image_density = "MEDIUM"
        else:
            image_density = "LOW"
            
        estimated_tokens = page_count * (500 if scan_ratio < 0.5 else 200)

        return {
            "filename": filename,
            "file_type": file_ext,
            "file_size": file_size,
            "page_count": page_count,
            "scanned_pages": scanned_pages,
            "text_pages": text_pages,
            "scan_ratio": scan_ratio,
            "image_density": image_density,
            "language": language,
            "ocr_required": ocr_required,
            "document_type": document_type,
            "estimated_tokens": estimated_tokens
        }
