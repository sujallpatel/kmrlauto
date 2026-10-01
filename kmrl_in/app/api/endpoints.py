from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks
from sqlmodel import Session, select, func
from app.db.session import get_session
from app.models.schema import Document, Task, Worker, ProcessingHistory
from load_balancer.router import router as lb_router
from load_balancer.worker_manager import worker_manager
from load_balancer.workload_predictor import workload_predictor
from workers.tasks import execute_document_processing_pipeline

router = APIRouter()

@router.post("/documents/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    safety_criticality: float = Form(0.0),
    regulatory_importance: float = Form(0.0),
    business_importance: float = Form(0.0),
    deadline_urgency: float = Form(0.0),
    language: str = Form("English"),
    document_type: str = Form("General"),
    page_count: Optional[int] = Form(None),
    ocr_required: Optional[bool] = Form(None),
    auto_execute: bool = Form(True),
    session: Session = Depends(get_session)
):
    """
    Uploads a document, extracts features, calculates workload & business priority, 
    selects the optimal worker, and queues the task.
    """
    file_bytes = await file.read()
    
    meta_override = {
        "language": language,
        "document_type": document_type
    }
    if page_count is not None:
        meta_override["page_count"] = page_count
    if ocr_required is not None:
        meta_override["ocr_required"] = ocr_required
        
    doc, task, selected_worker, routing_meta = lb_router.route_document(
        session=session,
        filename=file.filename,
        file_bytes=file_bytes,
        safety_criticality=safety_criticality,
        regulatory_importance=regulatory_importance,
        business_importance=business_importance,
        deadline_urgency=deadline_urgency,
        meta_override=meta_override
    )
    
    if auto_execute:
        # Schedule execution in background
        background_tasks.add_task(
            execute_document_processing_pipeline,
            doc.id,
            task.id,
            selected_worker.worker_id,
            task.processing_version
        )
        
    return {
        "message": "Document uploaded and intelligently routed successfully",
        "document_id": doc.id,
        "doc_uuid": doc.doc_uuid,
        "filename": doc.filename,
        "file_size": doc.file_size,
        "page_count": doc.page_count,
        "ocr_required": doc.ocr_required,
        "language": doc.language,
        "workload": {
            "complexity_score": doc.complexity_score,
            "complexity_category": doc.complexity_category,
            "predicted_processing_time_sec": doc.predicted_processing_time,
            "prediction_method": routing_meta["prediction_method"]
        },
        "priority": {
            "base_priority": doc.base_priority,
            "effective_priority": routing_meta["effective_priority"],
            "combined_task_score": routing_meta["combined_task_score"]
        },
        "assigned_worker": selected_worker.worker_id,
        "predicted_completion_time": routing_meta["predicted_completion_time"],
        "task_id": task.id,
        "status": task.status
    }

@router.get("/documents/{id}/status")
def get_document_status(id: int, session: Session = Depends(get_session)):
    doc = session.get(Document, id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    tasks = session.exec(select(Task).where(Task.document_id == id)).all()
    return {
        "document_id": doc.id,
        "doc_uuid": doc.doc_uuid,
        "filename": doc.filename,
        "status": doc.status,
        "complexity_category": doc.complexity_category,
        "base_priority": doc.base_priority,
        "tasks": [
            {
                "task_id": t.id,
                "task_type": t.task_type,
                "assigned_worker": t.assigned_worker,
                "status": t.status,
                "retry_count": t.retry_count,
                "effective_priority": t.effective_priority,
                "combined_score": t.combined_score,
                "created_at": t.created_at,
                "completed_at": t.completed_at,
                "error_message": t.error_message
            }
            for t in tasks
        ]
    }

@router.get("/workers")
def list_workers(session: Session = Depends(get_session)):
    worker_manager.update_health_states(session)
    workers = session.exec(select(Worker)).all()
    return [
        {
            "worker_id": w.worker_id,
            "hostname": w.hostname,
            "status": w.status,
            "circuit_status": w.circuit_status,
            "cpu_usage": w.cpu_usage,
            "memory_usage": w.memory_usage,
            "active_tasks": w.active_tasks,
            "queue_length": w.queue_length,
            "average_processing_time": w.average_processing_time,
            "supported_languages": w.supported_languages,
            "supported_tasks": w.supported_tasks,
            "consecutive_failures": w.consecutive_failures,
            "last_heartbeat": w.last_heartbeat
        }
        for w in workers
    ]

@router.get("/tasks")
def list_tasks(status: Optional[str] = None, session: Session = Depends(get_session)):
    statement = select(Task)
    if status:
        statement = statement.where(Task.status == status.upper())
    statement = statement.order_by(Task.combined_score.desc())
    tasks = session.exec(statement).all()
    return tasks

@router.get("/dead-letter-queue")
def get_dead_letter_queue(session: Session = Depends(get_session)):
    statement = select(Task).where(Task.status == "DEAD_LETTER")
    dlq_tasks = session.exec(statement).all()
    result = []
    for t in dlq_tasks:
        doc = session.get(Document, t.document_id)
        result.append({
            "task_id": t.id,
            "document_id": t.document_id,
            "filename": doc.filename if doc else "Unknown",
            "assigned_worker": t.assigned_worker,
            "retry_count": t.retry_count,
            "error_message": t.error_message,
            "created_at": t.created_at
        })
    return result

@router.post("/tasks/{id}/retry")
def retry_failed_task(
    id: int, 
    background_tasks: BackgroundTasks, 
    session: Session = Depends(get_session)
):
    task = session.get(Task, id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    doc = session.get(Document, task.document_id)
    task.status = "QUEUED"
    task.retry_count = 0
    task.processing_version += 1
    session.commit()
    
    # Re-route
    eligible = worker_manager.get_eligible_workers(
        session, 
        required_language=doc.language if doc else "English",
        required_ocr=doc.ocr_required if doc else False
    )
    selected_worker_id = eligible[0].worker_id if eligible else "Worker_Fallback"
    
    task.assigned_worker = selected_worker_id
    task.status = "ASSIGNED"
    session.commit()
    
    background_tasks.add_task(
        execute_document_processing_pipeline,
        doc.id,
        task.id,
        selected_worker_id,
        task.processing_version
    )
    
    return {"message": f"Task {id} requeued and reassigned to {selected_worker_id}"}

@router.get("/metrics")
def get_metrics(session: Session = Depends(get_session)):
    total_docs = session.exec(select(func.count(Document.id))).one()
    completed_docs = session.exec(select(func.count(Document.id)).where(Document.status == "COMPLETED")).one()
    failed_docs = session.exec(select(func.count(Document.id)).where(Document.status == "FAILED")).one()
    queued_tasks = session.exec(select(func.count(Task.id)).where(Task.status == "QUEUED")).one()
    processing_tasks = session.exec(select(func.count(Task.id)).where(Task.status == "PROCESSING")).one()
    dlq_tasks = session.exec(select(func.count(Task.id)).where(Task.status == "DEAD_LETTER")).one()
    
    workers = session.exec(select(Worker)).all()
    healthy_workers = sum(1 for w in workers if w.status == "HEALTHY")
    
    history_records = session.exec(select(ProcessingHistory)).all()
    if history_records:
        avg_processing_time = round(sum(r.actual_processing_time for r in history_records) / len(history_records), 2)
    else:
        avg_processing_time = 0.0
        
    return {
        "workers_total": len(workers),
        "workers_healthy": healthy_workers,
        "total_documents": total_docs,
        "completed_documents": completed_docs,
        "failed_documents": failed_docs,
        "queued_tasks": queued_tasks,
        "processing_tasks": processing_tasks,
        "dead_letter_tasks": dlq_tasks,
        "average_processing_time_sec": avg_processing_time,
        "ml_model_trained": workload_predictor.is_trained
    }
