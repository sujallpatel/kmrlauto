import os
from pydantic import BaseModel

class Settings(BaseModel):
    APP_NAME: str = "KMRL Intelligent Document Processing System"
    VERSION: str = "1.0.0"
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "sqlite:///./kmrl_system.db"
    )
    
    # Celery & RabbitMQ / Redis
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
    
    # Workload Heuristic Weights
    WEIGHT_PAGE: float = 0.35
    WEIGHT_FILE_SIZE: float = 0.15
    WEIGHT_OCR: float = 0.25
    WEIGHT_IMAGE: float = 0.15
    WEIGHT_LANGUAGE: float = 0.10
    
    # Task Priority Weights
    WEIGHT_SAFETY: float = 0.30
    WEIGHT_REGULATORY: float = 0.25
    WEIGHT_BUSINESS: float = 0.20
    WEIGHT_DEADLINE: float = 0.15
    WEIGHT_WAITING: float = 0.10
    
    # Priority Aging Factor (points per minute waiting)
    AGING_FACTOR: float = 0.5
    
    # Combined Task Score Weights
    ALPHA_PRIORITY: float = 0.70
    BETA_WORKLOAD: float = 0.30
    
    # Worker Selection Scoring Weights
    WEIGHT_RESOURCES: float = 0.30
    WEIGHT_QUEUE: float = 0.25
    WEIGHT_CAPABILITY: float = 0.20
    WEIGHT_PERFORMANCE: float = 0.15
    WEIGHT_RELIABILITY: float = 0.10
    
    # Heartbeat & Health Thresholds
    HEARTBEAT_TIMEOUT_SEC: float = 30.0
    DEGRADED_CPU_THRESHOLD: float = 80.0
    DEGRADED_RAM_THRESHOLD: float = 85.0
    
    # Circuit Breaker
    MAX_CONSECUTIVE_FAILURES: int = 3
    CIRCUIT_COOLDOWN_SEC: float = 60.0
    
    # Retry policy
    MAX_RETRIES: int = 3
    RETRY_BACKOFF_BASE_SEC: int = 5

settings = Settings()
