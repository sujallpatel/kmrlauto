import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import time
from datetime import datetime, timedelta, timezone
from sqlmodel import Session, select, delete
from app.db.session import init_db, engine
from app.models.schema import Document, Task, Worker, ProcessingHistory
from load_balancer.feature_extractor import FeatureExtractor
from load_balancer.workload_predictor import workload_predictor
from load_balancer.prioritizer import prioritizer
from load_balancer.worker_manager import worker_manager
from load_balancer.router import router as lb_router
from workers.tasks import execute_document_processing_pipeline

@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    with Session(engine) as session:
        session.exec(delete(Task))
        session.exec(delete(ProcessingHistory))
        session.exec(delete(Document))
        session.exec(delete(Worker))
        session.commit()

def test_feature_extractor():
    features = FeatureExtractor.extract_features(
        file_path="",
        filename="test_scan.pdf",
        file_bytes=b"dummy content",
        meta_override={
            "page_count": 250,
            "scanned_pages": 230,
            "language": "Malayalam",
            "document_type": "Engineering"
        }
    )
    assert features["page_count"] == 250
    assert features["scanned_pages"] == 230
    assert features["scan_ratio"] > 0.9
    assert features["image_density"] == "HIGH"
    assert features["language"] == "Malayalam"

def test_workload_predictor_stage_a():
    features_low = {
        "page_count": 2,
        "file_size": 100 * 1024,
        "ocr_required": False,
        "scan_ratio": 0.0,
        "language": "English"
    }
    score_low, cat_low, time_low = workload_predictor.predict_heuristic(features_low)
    assert cat_low == "LOW"
    assert score_low < 0.30

    features_high = {
        "page_count": 300,
        "file_size": 18 * 1024 * 1024,
        "ocr_required": True,
        "scan_ratio": 0.95,
        "language": "Malayalam"
    }
    score_high, cat_high, time_high = workload_predictor.predict_heuristic(features_high)
    assert cat_high in ["HIGH", "VERY HIGH"]
    assert score_high >= 0.60
    assert time_high > time_low

def test_priority_and_aging():
    base_p = prioritizer.calculate_base_priority(
        safety_criticality=100.0,
        regulatory_importance=90.0,
        business_importance=80.0,
        deadline_urgency=90.0
    )
    assert base_p >= 80.0
    assert prioritizer.classify_priority(base_p) in ["HIGH", "CRITICAL"]

    created_time = datetime.now(timezone.utc) - timedelta(minutes=60)
    effective_p = prioritizer.calculate_effective_priority(30.0, created_time)
    assert effective_p == 60.0  # 30 + 0.5 * 60 = 60

def test_worker_manager_and_circuit_breaker():
    with Session(engine) as session:
        w1 = worker_manager.register_or_update_heartbeat(
            session, "W1", supported_languages=["English"], supported_tasks=["OCR"]
        )
        w2 = worker_manager.register_or_update_heartbeat(
            session, "W2", supported_languages=["Malayalam"], supported_tasks=["OCR"]
        )
        
        eligible = worker_manager.get_eligible_workers(session, required_language="Malayalam", required_ocr=True)
        eligible_ids = [w.worker_id for w in eligible]
        assert "W2" in eligible_ids
        assert "W1" not in eligible_ids

        worker_manager.record_task_failure(session, "W1")
        worker_manager.record_task_failure(session, "W1")
        worker_manager.record_task_failure(session, "W1")
        
        w1_updated = session.exec(select(Worker).where(Worker.worker_id == "W1")).first()
        assert w1_updated.circuit_status == "OPEN"

def test_intelligent_routing_and_execution():
    with Session(engine) as session:
        worker_manager.register_or_update_heartbeat(
            session, "W1", cpu_usage=80.0, active_tasks=3, supported_languages=["English", "Malayalam"]
        )
        worker_manager.register_or_update_heartbeat(
            session, "W2", cpu_usage=20.0, active_tasks=0, supported_languages=["English", "Malayalam"]
        )

        doc, task, selected_worker, meta = lb_router.route_document(
            session=session,
            filename="malayalam_safety_report.pdf",
            file_bytes=b"test data",
            safety_criticality=90.0,
            meta_override={"page_count": 25, "language": "Malayalam", "ocr_required": True}
        )
        
        doc_id = doc.id
        task_id = task.id
        worker_id = selected_worker.worker_id
        version = task.processing_version
        
        assert worker_id == "W2"
        assert task.status == "ASSIGNED"

    res = execute_document_processing_pipeline(doc_id, task_id, worker_id, version)
    assert res["status"] == "COMPLETED"

    res_repeat = execute_document_processing_pipeline(doc_id, task_id, worker_id, version)
    assert res_repeat["status"] == "ALREADY_PROCESSED"
