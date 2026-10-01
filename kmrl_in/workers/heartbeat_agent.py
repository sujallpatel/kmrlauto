import time
import psutil
from typing import List
from sqlmodel import Session
from app.db.session import engine
from load_balancer.worker_manager import worker_manager

class HeartbeatAgent:
    """
    Background worker process reporting CPU, RAM, active task count, 
    supported languages, and capabilities to the Load Balancer database.
    """
    
    def __init__(
        self, 
        worker_id: str, 
        hostname: str = "localhost",
        supported_languages: List[str] = None,
        supported_tasks: List[str] = None
    ):
        self.worker_id = worker_id
        self.hostname = hostname
        self.supported_languages = supported_languages or ["English"]
        self.supported_tasks = supported_tasks or ["OCR", "NLP"]
        
    def send_heartbeat(self):
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory().percent
        
        with Session(engine) as session:
            w = worker_manager.register_or_update_heartbeat(
                session=session,
                worker_id=self.worker_id,
                hostname=self.hostname,
                cpu_usage=cpu,
                memory_usage=mem,
                supported_languages=self.supported_languages,
                supported_tasks=self.supported_tasks
            )
            return w

    def start_loop(self, interval_sec: float = 10.0, max_iterations: int = None):
        count = 0
        while True:
            self.send_heartbeat()
            count += 1
            if max_iterations and count >= max_iterations:
                break
            time.sleep(interval_sec)

if __name__ == "__main__":
    agent = HeartbeatAgent(
        worker_id="Worker_1", 
        supported_languages=["English", "Malayalam"], 
        supported_tasks=["OCR", "NLP"]
    )
    agent.send_heartbeat()
    print("Sent heartbeat for Worker_1")
