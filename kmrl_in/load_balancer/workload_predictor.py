import numpy as np
from typing import Dict, Any, Tuple, Optional
from sqlmodel import Session, select, func
from app.core.config import settings
from app.models.schema import ProcessingHistory

try:
    from sklearn.ensemble import RandomForestRegressor
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

class WorkloadPredictor:
    """
    Two-stage Workload Predictor:
    1. Heuristic Model (Stage A): Weighted linear combination formula for cold-start scenarios.
    2. Data-Driven ML Model (Stage B): Random Forest Regressor trained on historical processing logs.
    """
    
    def __init__(self):
        self.ml_model: Optional[Any] = None
        self.is_trained: bool = False
        self.min_samples_for_ml: int = 20  # train threshold
        
    def _normalize_features(self, features: Dict[str, Any]) -> Dict[str, float]:
        # Page count (normalize up to 300 pages)
        P = min(features.get("page_count", 1) / 300.0, 1.0)
        
        # File size (normalize up to 20MB = 20 * 1024 * 1024 bytes)
        S = min(features.get("file_size", 1024) / (20.0 * 1024 * 1024), 1.0)
        
        # OCR required (0 or 1)
        O = 1.0 if features.get("ocr_required", False) else 0.0
        
        # Image / Scanned Ratio (0.0 to 1.0)
        I = float(features.get("scan_ratio", 0.0))
        
        # Language complexity
        lang = str(features.get("language", "English")).lower()
        if "malayalam" in lang:
            L = 1.0
        elif "mixed" in lang or "hindi" in lang:
            L = 0.7
        else:
            L = 0.3
            
        return {"P": P, "S": S, "O": O, "I": I, "L": L}

    def predict_heuristic(self, features: Dict[str, Any]) -> Tuple[float, str, float]:
        """
        Stage A: Heuristic Score Formula:
        C = w_p*P + w_s*S + w_o*O + w_i*I + w_l*L
        """
        norm = self._normalize_features(features)
        
        complexity = (
            settings.WEIGHT_PAGE * norm["P"] +
            settings.WEIGHT_FILE_SIZE * norm["S"] +
            settings.WEIGHT_OCR * norm["O"] +
            settings.WEIGHT_IMAGE * norm["I"] +
            settings.WEIGHT_LANGUAGE * norm["L"]
        )
        
        complexity = min(max(complexity, 0.0), 1.0)
        
        if complexity < 0.30:
            category = "LOW"
        elif complexity < 0.60:
            category = "MEDIUM"
        elif complexity < 0.80:
            category = "HIGH"
        else:
            category = "VERY HIGH"
            
        # Estimated processing time baseline: 5s base + up to 150s for max complexity
        predicted_time_sec = round(5.0 + complexity * 150.0, 2)
        return round(complexity, 4), category, predicted_time_sec

    def train_ml_model(self, session: Session) -> bool:
        """
        Stage B: Train Random Forest Regressor on accumulated ProcessingHistory data.
        """
        if not SKLEARN_AVAILABLE:
            return False
            
        statement = select(ProcessingHistory).where(ProcessingHistory.success == True)
        results = session.exec(statement).all()
        
        if len(results) < self.min_samples_for_ml:
            self.is_trained = False
            return False
            
        X = []
        y = []
        for row in results:
            feats = {
                "page_count": row.pages,
                "file_size": row.file_size,
                "ocr_required": row.ocr_required,
                "scan_ratio": row.scanned_ratio,
                "language": row.language
            }
            norm = self._normalize_features(feats)
            X.append([norm["P"], norm["S"], norm["O"], norm["I"], norm["L"]])
            y.append(row.actual_processing_time)
            
        try:
            rf = RandomForestRegressor(n_estimators=50, random_state=42)
            rf.fit(X, y)
            self.ml_model = rf
            self.is_trained = True
            return True
        except Exception:
            self.is_trained = False
            return False

    def predict_adaptive(self, features: Dict[str, Any], session: Optional[Session] = None) -> Tuple[float, str, float, str]:
        """
        Adaptive Selector:
        Returns (complexity_score, category, predicted_time_sec, method_used)
        """
        heuristic_score, category, heuristic_time = self.predict_heuristic(features)
        
        if session and SKLEARN_AVAILABLE:
            if not self.is_trained:
                self.train_ml_model(session)
                
            if self.is_trained and self.ml_model:
                norm = self._normalize_features(features)
                X_input = np.array([[norm["P"], norm["S"], norm["O"], norm["I"], norm["L"]]])
                ml_time = float(self.ml_model.predict(X_input)[0])
                ml_time = max(round(ml_time, 2), 2.0)
                return heuristic_score, category, ml_time, "ML_RANDOM_FOREST"
                
        return heuristic_score, category, heuristic_time, "HEURISTIC_WEIGHTED"

workload_predictor = WorkloadPredictor()
