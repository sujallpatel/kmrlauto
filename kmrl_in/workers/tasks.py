import time
from datetime import datetime, timezone
from sqlmodel import Session, select
from app.core.config import settings
from app.db.session import engine
from app.models.schema import Document, Task, Worker, ProcessingHistory
from load_balancer.worker_manager import worker_manager
from load_balancer.workload_predictor import workload_predictor
from workers.celery_app import celery_app

def execute_document_processing_pipeline(
    doc_id: int, 
    task_id: int, 
    assigned_worker_id: str, 
    processing_version: int,
    simulation_speed_multiplier: float = 1.0
) -> dict:
    start_time = time.time()
    
    with Session(engine, expire_on_commit=False) as session:
        task = session.get(Task, task_id)
        doc = session.get(Document, doc_id)
        
        if not task or not doc:
            return {"status": "FAILED", "reason": "Task or Document not found"}
            
        if doc.status == "COMPLETED" and task.processing_version <= processing_version and task.status == "COMPLETED":
            return {"status": "ALREADY_PROCESSED", "document_id": doc_id}
            
        task.status = "PROCESSING"
        task.started_at = datetime.now(timezone.utc)
        doc.status = "PROCESSING"
        session.commit()

        statement = select(Worker).where(Worker.worker_id == assigned_worker_id)
        w = session.exec(statement).first()
        if w:
            w.active_tasks += 1
            w.queue_length = max(w.queue_length - 1, 0)
            session.commit()
            
        base_delay = doc.predicted_processing_time
        doc_page_count = doc.page_count
        doc_file_size = doc.file_size
        doc_ocr_req = doc.ocr_required
        doc_language = doc.language
        doc_scan_ratio = float(doc.scanned_pages / max(doc.page_count, 1))
        doc_type = doc.document_type
        doc_complexity = doc.complexity_score

    # Simulated delay processing
    actual_delay = max((base_delay * 0.05) / simulation_speed_multiplier, 0.05)
    time.sleep(actual_delay)
    
    actual_processing_time = round((time.time() - start_time) * (20.0 * simulation_speed_multiplier), 2)
    
    with Session(engine, expire_on_commit=False) as session:
        task = session.get(Task, task_id)
        doc = session.get(Document, doc_id)
        
        if not task or not doc:
            return {"status": "FAILED", "reason": "Task or Document not found upon completion"}
            
        task.status = "COMPLETED"
        task.completed_at = datetime.now(timezone.utc)
        doc.status = "COMPLETED"
        doc.updated_at = datetime.now(timezone.utc)
        
        statement = select(Worker).where(Worker.worker_id == assigned_worker_id)
        w = session.exec(statement).first()
        if w:
            w.active_tasks = max(w.active_tasks - 1, 0)
            session.commit()

        history = ProcessingHistory(
            document_id=doc_id,
            worker_id=assigned_worker_id,
            pages=doc_page_count,
            file_size=doc_file_size,
            ocr_required=doc_ocr_req,
            language=doc_language,
            scanned_ratio=doc_scan_ratio,
            document_type=doc_type,
            predicted_complexity=doc_complexity,
            predicted_time=base_delay,
            actual_processing_time=actual_processing_time,
            success=True,
            timestamp=datetime.now(timezone.utc)
        )
        session.add(history)
        session.commit()
        
        worker_manager.record_task_success(session, assigned_worker_id, actual_processing_time)
        workload_predictor.train_ml_model(session)
        
    return {
        "status": "COMPLETED",
        "document_id": doc_id,
        "actual_processing_time": actual_processing_time
    }

@celery_app.task(bind=True, max_retries=settings.MAX_RETRIES)
def process_document_task(self, doc_id: int, task_id: int, worker_id: str, processing_version: int):
    try:
        return execute_document_processing_pipeline(doc_id, task_id, worker_id, processing_version)
    except Exception as exc:
        with Session(engine, expire_on_commit=False) as session:
            task = session.get(Task, task_id)
            if task:
                task.retry_count += 1
                if task.retry_count >= settings.MAX_RETRIES:
                    task.status = "DEAD_LETTER"
                    task.error_message = str(exc)
                    session.commit()
                else:
                    session.commit()
                    countdown = settings.RETRY_BACKOFF_BASE_SEC * (3 ** (task.retry_count - 1))
                    raise self.retry(exc=exc, countdown=countdown)
        worker_manager.record_task_failure(Session(engine), worker_id)
        raise exc
