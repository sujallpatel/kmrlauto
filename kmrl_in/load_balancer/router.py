import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List
from sqlmodel import Session, select
from app.core.config import settings
from app.models.schema import Document, Task, Worker, ProcessingHistory
from load_balancer.feature_extractor import FeatureExtractor
from load_balancer.workload_predictor import workload_predictor
from load_balancer.prioritizer import prioritizer
from load_balancer.worker_manager import worker_manager

class IntelligentRouter:
    """
    Intelligent Load Balancer Engine.
    Executes feature extraction, workload prediction, priority calculation, 
    capability filtering, worker completion time estimation, and celery routing.
    """
    
    @staticmethod
    def route_document(
        session: Session,
        filename: str,
        file_bytes: bytes,
        safety_criticality: float = 0.0,
        regulatory_importance: float = 0.0,
        business_importance: float = 0.0,
        deadline_urgency: float = 0.0,
        meta_override: Dict[str, Any] = None
    ) -> Tuple[Document, Task, Worker, Dict[str, Any]]:
        meta_override = meta_override or {}
        
        # 1. Feature Extraction
        features = FeatureExtractor.extract_features(
            file_path="", 
            filename=filename, 
            file_bytes=file_bytes, 
            meta_override=meta_override
        )
        
        # 2. Workload Prediction
        complexity_score, category, predicted_time_sec, method_used = workload_predictor.predict_adaptive(
            features, session=session
        )
        
        # 3. Base Priority Calculation
        base_priority = prioritizer.calculate_base_priority(
            safety_criticality=safety_criticality,
            regulatory_importance=regulatory_importance,
            business_importance=business_importance,
            deadline_urgency=deadline_urgency
        )
        
        # 4. Save Document Record
        doc_uuid = str(uuid.uuid4())
        doc = Document(
            doc_uuid=doc_uuid,
            filename=filename,
            file_type=features["file_type"],
            file_size=features["file_size"],
            page_count=features["page_count"],
            scanned_pages=features["scanned_pages"],
            text_pages=features["text_pages"],
            image_density=features["image_density"],
            language=features["language"],
            ocr_required=features["ocr_required"],
            document_type=features["document_type"],
            estimated_tokens=features["estimated_tokens"],
            safety_criticality=safety_criticality,
            regulatory_importance=regulatory_importance,
            business_importance=business_importance,
            deadline_urgency=deadline_urgency,
            base_priority=base_priority,
            complexity_score=complexity_score,
            complexity_category=category,
            predicted_processing_time=predicted_time_sec,
            status="QUEUED"
        )
        session.add(doc)
        session.commit()
        session.refresh(doc)
        
        # 5. Retrieve Worker States & Apply Capability + Health Filters
        eligible_workers = worker_manager.get_eligible_workers(
            session=session,
            required_language=features["language"],
            required_ocr=features["ocr_required"]
        )
        
        if not eligible_workers:
            default_w = worker_manager.register_or_update_heartbeat(
                session=session,
                worker_id="Worker_Fallback",
                supported_languages=["English", "Malayalam", "Mixed"],
                supported_tasks=["OCR", "NLP"]
            )
            eligible_workers = [default_w]
            
        # 6. Worker Score & Completion Time Estimation
        worker_evaluations = []
        for w in eligible_workers:
            current_workload_sec = (w.active_tasks + w.queue_length) * w.average_processing_time
            predicted_completion_time = round(current_workload_sec + predicted_time_sec, 2)
            
            cpu_avail = max(1.0 - (w.cpu_usage / 100.0), 0.0)
            ram_avail = max(1.0 - (w.memory_usage / 100.0), 0.0)
            R = 0.5 * cpu_avail + 0.5 * ram_avail
            
            Q = 1.0 / (1.0 + w.active_tasks + w.queue_length)
            C = 1.0
            P = 1.0 / (1.0 + (w.average_processing_time / 60.0))
            F = max(1.0 - (w.consecutive_failures / 3.0), 0.0)
            
            w_score = (
                settings.WEIGHT_RESOURCES * R +
                settings.WEIGHT_QUEUE * Q +
                settings.WEIGHT_CAPABILITY * C +
                settings.WEIGHT_PERFORMANCE * P +
                settings.WEIGHT_RELIABILITY * F
            )
            
            worker_evaluations.append({
                "worker": w,
                "score": round(w_score, 4),
                "predicted_completion_time": predicted_completion_time,
                "current_workload_sec": round(current_workload_sec, 2)
            })
            
        best_eval = min(
            worker_evaluations, 
            key=lambda x: (x["predicted_completion_time"], -x["score"])
        )
        selected_worker = best_eval["worker"]
        
        selected_worker.queue_length += 1
        session.commit()
        
        task_uuid = str(uuid.uuid4())
        effective_p = prioritizer.calculate_effective_priority(base_priority, doc.created_at)
        combined_score = prioritizer.calculate_combined_task_score(effective_p, predicted_time_sec)
        
        task = Task(
            task_uuid=task_uuid,
            document_id=doc.id,
            task_type="OCR_NLP_PIPELINE",
            base_priority=base_priority,
            effective_priority=effective_p,
            predicted_workload=predicted_time_sec,
            combined_score=combined_score,
            assigned_worker=selected_worker.worker_id,
            status="ASSIGNED",
            retry_count=0,
            processing_version=1
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        session.refresh(doc)
        session.refresh(selected_worker)
        
        routing_metadata = {
            "prediction_method": method_used,
            "complexity_category": category,
            "predicted_time_sec": predicted_time_sec,
            "base_priority": base_priority,
            "effective_priority": effective_p,
            "combined_task_score": combined_score,
            "selected_worker": selected_worker.worker_id,
            "predicted_completion_time": best_eval["predicted_completion_time"],
            "eligible_worker_count": len(eligible_workers)
        }
        
        return doc, task, selected_worker, routing_metadata

router = IntelligentRouter()
