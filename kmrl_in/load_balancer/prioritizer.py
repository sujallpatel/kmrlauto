from datetime import datetime, timezone
from typing import Dict, Any, Tuple
from app.core.config import settings

class Prioritizer:
    """
    Priority Calculator & Aging Engine to prevent task starvation.
    """
    
    @staticmethod
    def calculate_base_priority(
        safety_criticality: float = 0.0,
        regulatory_importance: float = 0.0,
        business_importance: float = 0.0,
        deadline_urgency: float = 0.0,
        waiting_time_minutes: float = 0.0
    ) -> float:
        S = min(max(safety_criticality, 0.0), 100.0)
        R = min(max(regulatory_importance, 0.0), 100.0)
        B = min(max(business_importance, 0.0), 100.0)
        D = min(max(deadline_urgency, 0.0), 100.0)
        W = min(max(waiting_time_minutes * 2.0, 0.0), 100.0)
        
        priority = (
            settings.WEIGHT_SAFETY * S +
            settings.WEIGHT_REGULATORY * R +
            settings.WEIGHT_BUSINESS * B +
            settings.WEIGHT_DEADLINE * D +
            settings.WEIGHT_WAITING * W
        )
        return round(priority, 2)

    @staticmethod
    def classify_priority(priority_score: float) -> str:
        if priority_score >= 90.0:
            return "CRITICAL"
        elif priority_score >= 70.0:
            return "HIGH"
        elif priority_score >= 40.0:
            return "NORMAL"
        else:
            return "LOW"

    @staticmethod
    def calculate_effective_priority(
        base_priority: float, 
        created_at: datetime
    ) -> float:
        now = datetime.now(timezone.utc)
        if created_at and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
            
        waiting_seconds = (now - created_at).total_seconds()
        waiting_minutes = max(waiting_seconds / 60.0, 0.0)
        
        effective_p = base_priority + (settings.AGING_FACTOR * waiting_minutes)
        return round(min(effective_p, 100.0), 2)

    @staticmethod
    def calculate_combined_task_score(
        effective_priority: float, 
        predicted_workload_sec: float
    ) -> float:
        norm_workload = min((predicted_workload_sec / 150.0) * 100.0, 100.0)
        combined = (
            settings.ALPHA_PRIORITY * effective_priority +
            settings.BETA_WORKLOAD * norm_workload
        )
        return round(combined, 2)

prioritizer = Prioritizer()
