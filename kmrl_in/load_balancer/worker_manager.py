from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from sqlmodel import Session, select
from app.core.config import settings
from app.models.schema import Worker

class WorkerManager:
    """
    Worker Registry, Health Monitor (State Machine), and Circuit Breaker.
    """
    
    @staticmethod
    def register_or_update_heartbeat(
        session: Session,
        worker_id: str,
        hostname: str = "localhost",
        cpu_usage: float = 0.0,
        memory_usage: float = 0.0,
        active_tasks: int = 0,
        queue_length: int = 0,
        average_processing_time: float = 30.0,
        supported_languages: List[str] = None,
        supported_tasks: List[str] = None
    ) -> Worker:
        supported_languages = supported_languages or ["English"]
        supported_tasks = supported_tasks or ["OCR", "NLP"]
        
        statement = select(Worker).where(Worker.worker_id == worker_id)
        worker = session.exec(statement).first()
        now = datetime.now(timezone.utc)
        
        if cpu_usage > settings.DEGRADED_CPU_THRESHOLD or memory_usage > settings.DEGRADED_RAM_THRESHOLD:
            status = "DEGRADED"
        else:
            status = "HEALTHY"
            
        if not worker:
            worker = Worker(
                worker_id=worker_id,
                hostname=hostname,
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                active_tasks=active_tasks,
                queue_length=queue_length,
                average_processing_time=average_processing_time,
                supported_languages=supported_languages,
                supported_tasks=supported_tasks,
                status=status,
                circuit_status="CLOSED",
                consecutive_failures=0,
                last_heartbeat=now
            )
            session.add(worker)
        else:
            worker.hostname = hostname
            worker.cpu_usage = cpu_usage
            worker.memory_usage = memory_usage
            worker.active_tasks = active_tasks
            worker.queue_length = queue_length
            worker.average_processing_time = average_processing_time
            worker.supported_languages = supported_languages
            worker.supported_tasks = supported_tasks
            worker.last_heartbeat = now
            
            lh = worker.last_heartbeat.replace(tzinfo=timezone.utc) if worker.last_heartbeat.tzinfo is None else worker.last_heartbeat
            if worker.status != "UNHEALTHY" or (now - lh).total_seconds() < settings.HEARTBEAT_TIMEOUT_SEC:
                worker.status = status
                
        session.commit()
        session.refresh(worker)
        return worker

    @staticmethod
    def update_health_states(session: Session) -> List[Worker]:
        statement = select(Worker)
        workers = session.exec(statement).all()
        now = datetime.now(timezone.utc)
        
        for w in workers:
            lh = w.last_heartbeat.replace(tzinfo=timezone.utc) if w.last_heartbeat and w.last_heartbeat.tzinfo is None else w.last_heartbeat
            if lh:
                seconds_since_heartbeat = (now - lh).total_seconds()
                if seconds_since_heartbeat > settings.HEARTBEAT_TIMEOUT_SEC:
                    w.status = "UNHEALTHY"
                
            if w.circuit_status == "OPEN" and w.circuit_cooldown_until:
                cc = w.circuit_cooldown_until.replace(tzinfo=timezone.utc) if w.circuit_cooldown_until.tzinfo is None else w.circuit_cooldown_until
                if now >= cc:
                    w.circuit_status = "HALF_OPEN"
                    
        session.commit()
        return workers

    @staticmethod
    def record_task_failure(session: Session, worker_id: str) -> None:
        statement = select(Worker).where(Worker.worker_id == worker_id)
        w = session.exec(statement).first()
        if w:
            w.consecutive_failures += 1
            if w.consecutive_failures >= settings.MAX_CONSECUTIVE_FAILURES:
                w.circuit_status = "OPEN"
                w.circuit_cooldown_until = datetime.now(timezone.utc) + timedelta(seconds=settings.CIRCUIT_COOLDOWN_SEC)
                w.status = "DEGRADED"
            session.commit()

    @staticmethod
    def record_task_success(session: Session, worker_id: str, processing_time: float) -> None:
        statement = select(Worker).where(Worker.worker_id == worker_id)
        w = session.exec(statement).first()
        if w:
            w.consecutive_failures = 0
            if w.circuit_status in ["OPEN", "HALF_OPEN"]:
                w.circuit_status = "CLOSED"
                w.status = "HEALTHY"
            w.average_processing_time = round(0.8 * w.average_processing_time + 0.2 * processing_time, 2)
            session.commit()

    @staticmethod
    def get_eligible_workers(
        session: Session, 
        required_language: str = "English", 
        required_ocr: bool = False
    ) -> List[Worker]:
        WorkerManager.update_health_states(session)
        statement = select(Worker)
        all_workers = session.exec(statement).all()
        
        eligible = []
        for w in all_workers:
            if w.status == "UNHEALTHY":
                continue
            if w.circuit_status == "OPEN":
                continue
            req_lang = required_language.lower()
            supported_langs = [l.lower() for l in (w.supported_languages or [])]
            if req_lang == "malayalam" and not any("malayalam" in l for l in supported_langs):
                continue
            if required_ocr:
                supported_tasks = [t.upper() for t in (w.supported_tasks or [])]
                if "OCR" not in supported_tasks:
                    continue
            eligible.append(w)
            
        return eligible

worker_manager = WorkerManager()
