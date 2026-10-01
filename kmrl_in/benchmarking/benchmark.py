import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import time
import json
from datetime import datetime, timezone
from typing import Dict, Any, List
from sqlmodel import Session, select, delete
from app.db.session import init_db, engine
from app.models.schema import Document, Task, Worker, ProcessingHistory
from load_balancer.router import router as lb_router
from load_balancer.worker_manager import worker_manager
from workers.tasks import execute_document_processing_pipeline
from benchmarking.generator import SyntheticDocumentGenerator

class BenchmarkSuite:
    """
    Evaluation Suite comparing:
    - Experiment A: Standard Round-Robin Load Balancing
    - Experiment B: Intelligent Workload & Priority Load Balancing
    
    Measures:
    1. Average Processing Time
    2. System Throughput
    3. Worker Utilization & Load Distribution
    4. Load Imbalance Index
    """
    
    def __init__(self):
        init_db()

    def reset_db_and_workers(self):
        with Session(engine) as session:
            session.exec(delete(Task))
            session.exec(delete(ProcessingHistory))
            session.exec(delete(Document))
            session.exec(delete(Worker))
            session.commit()
            
            worker_manager.register_or_update_heartbeat(
                session, worker_id="Worker_1", hostname="worker1.node",
                cpu_usage=10.0, memory_usage=20.0,
                supported_languages=["English"], supported_tasks=["OCR", "NLP"]
            )
            worker_manager.register_or_update_heartbeat(
                session, worker_id="Worker_2", hostname="worker2.node",
                cpu_usage=10.0, memory_usage=20.0,
                supported_languages=["English", "Malayalam"], supported_tasks=["OCR", "NLP"]
            )
            worker_manager.register_or_update_heartbeat(
                session, worker_id="Worker_3", hostname="worker3.node",
                cpu_usage=10.0, memory_usage=20.0,
                supported_languages=["English", "Malayalam", "Mixed"], supported_tasks=["OCR", "NLP"]
            )

    def refresh_heartbeats(self):
        now = datetime.now(timezone.utc)
        with Session(engine) as session:
            workers = session.exec(select(Worker)).all()
            for w in workers:
                w.last_heartbeat = now
                w.status = "HEALTHY"
            session.commit()

    def run_round_robin_experiment(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        self.reset_db_and_workers()
        start_time = time.time()
        
        worker_ids = ["Worker_1", "Worker_2", "Worker_3"]
        worker_loads = {w: 0.0 for w in worker_ids}
        worker_doc_counts = {w: 0 for w in worker_ids}
        
        results = []
        for idx, item in enumerate(documents):
            self.refresh_heartbeats()
            assigned_worker = worker_ids[idx % len(worker_ids)]
            
            with Session(engine) as session:
                doc, task, selected_w, meta = lb_router.route_document(
                    session=session,
                    filename=item["filename"],
                    file_bytes=item["file_bytes"],
                    safety_criticality=item["safety_criticality"],
                    regulatory_importance=item["regulatory_importance"],
                    business_importance=item["business_importance"],
                    deadline_urgency=item["deadline_urgency"],
                    meta_override={
                        "page_count": item["page_count"],
                        "scanned_pages": item["scanned_pages"],
                        "language": item["language"],
                        "ocr_required": item["ocr_required"],
                        "document_type": item["document_type"]
                    }
                )
                
                task.assigned_worker = assigned_worker
                session.commit()
                
                res = execute_document_processing_pipeline(
                    doc.id, task.id, assigned_worker, task.processing_version, simulation_speed_multiplier=10.0
                )
                actual_time = res.get("actual_processing_time", doc.predicted_processing_time)
                
                worker_loads[assigned_worker] += actual_time
                worker_doc_counts[assigned_worker] += 1
                results.append(actual_time)
                
        total_wall_time = time.time() - start_time
        avg_time = sum(results) / len(results) if results else 0.0
        throughput = len(documents) / max(total_wall_time, 0.001)
        
        loads = list(worker_loads.values())
        avg_w_load = sum(loads) / max(len(loads), 1)
        imbalance_index = (max(loads) - min(loads)) / max(avg_w_load, 0.001)
        
        return {
            "strategy": "Round Robin",
            "total_documents": len(documents),
            "total_wall_time_sec": round(total_wall_time, 2),
            "average_processing_time_sec": round(avg_time, 2),
            "throughput_docs_per_sec": round(throughput, 4),
            "worker_document_counts": worker_doc_counts,
            "worker_total_workloads_sec": {k: round(v, 2) for k, v in worker_loads.items()},
            "load_imbalance_index": round(imbalance_index, 4)
        }

    def run_intelligent_routing_experiment(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        self.reset_db_and_workers()
        start_time = time.time()
        
        worker_ids = ["Worker_1", "Worker_2", "Worker_3"]
        worker_loads = {w: 0.0 for w in worker_ids}
        worker_doc_counts = {w: 0 for w in worker_ids}
        
        results = []
        for item in documents:
            self.refresh_heartbeats()
            with Session(engine) as session:
                doc, task, selected_w, meta = lb_router.route_document(
                    session=session,
                    filename=item["filename"],
                    file_bytes=item["file_bytes"],
                    safety_criticality=item["safety_criticality"],
                    regulatory_importance=item["regulatory_importance"],
                    business_importance=item["business_importance"],
                    deadline_urgency=item["deadline_urgency"],
                    meta_override={
                        "page_count": item["page_count"],
                        "scanned_pages": item["scanned_pages"],
                        "language": item["language"],
                        "ocr_required": item["ocr_required"],
                        "document_type": item["document_type"]
                    }
                )
                
                assigned_worker = selected_w.worker_id
                res = execute_document_processing_pipeline(
                    doc.id, task.id, assigned_worker, task.processing_version, simulation_speed_multiplier=10.0
                )
                actual_time = res.get("actual_processing_time", doc.predicted_processing_time)
                
                if assigned_worker not in worker_loads:
                    worker_loads[assigned_worker] = 0.0
                    worker_doc_counts[assigned_worker] = 0
                worker_loads[assigned_worker] += actual_time
                worker_doc_counts[assigned_worker] += 1
                results.append(actual_time)
                
        total_wall_time = time.time() - start_time
        avg_time = sum(results) / len(results) if results else 0.0
        throughput = len(documents) / max(total_wall_time, 0.001)
        
        loads = list(worker_loads.values())
        avg_w_load = sum(loads) / max(len(loads), 1)
        imbalance_index = (max(loads) - min(loads)) / max(avg_w_load, 0.001)
        
        return {
            "strategy": "Intelligent Load Balancer",
            "total_documents": len(documents),
            "total_wall_time_sec": round(total_wall_time, 2),
            "average_processing_time_sec": round(avg_time, 2),
            "throughput_docs_per_sec": round(throughput, 4),
            "worker_document_counts": worker_doc_counts,
            "worker_total_workloads_sec": {k: round(v, 2) for k, v in worker_loads.items()},
            "load_imbalance_index": round(imbalance_index, 4)
        }

if __name__ == "__main__":
    suite = BenchmarkSuite()
    docs = SyntheticDocumentGenerator.generate_document_batch(count=30, seed=42)
    
    print("--- RUNNING EXPERIMENT A: ROUND ROBIN ---")
    res_rr = suite.run_round_robin_experiment(docs)
    print(json.dumps(res_rr, indent=2))
    
    print("\n--- RUNNING EXPERIMENT B: INTELLIGENT LOAD BALANCER ---")
    res_intel = suite.run_intelligent_routing_experiment(docs)
    print(json.dumps(res_intel, indent=2))
