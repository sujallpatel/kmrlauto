from datetime import datetime, timezone
from typing import Optional, List
from sqlmodel import SQLModel, Field, Column, JSON

def get_utc_now():
    return datetime.now(timezone.utc)

class Document(SQLModel, table=True):
    __tablename__ = "documents"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    doc_uuid: str = Field(index=True, unique=True)
    filename: str
    file_type: str  # e.g., 'pdf', 'png'
    file_size: int  # in bytes
    page_count: int = 1
    scanned_pages: int = 0
    text_pages: int = 1
    image_density: str = "LOW"  # LOW, MEDIUM, HIGH
    language: str = "English"  # Malayalam, English, Mixed
    ocr_required: bool = False
    document_type: str = "General"  # Engineering, Safety, Regulatory, Reference
    estimated_tokens: int = 0
    
    # Priority Factors (0 to 100)
    safety_criticality: float = 0.0
    regulatory_importance: float = 0.0
    business_importance: float = 0.0
    deadline_urgency: float = 0.0
    
    # Computed Scores
    base_priority: float = 0.0
    complexity_score: float = 0.0
    complexity_category: str = "LOW"  # LOW, MEDIUM, HIGH, VERY HIGH
    predicted_processing_time: float = 0.0  # in seconds
    
    status: str = Field(default="QUEUED")  # QUEUED, PROCESSING, COMPLETED, FAILED
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)

class Task(SQLModel, table=True):
    __tablename__ = "tasks"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    task_uuid: str = Field(index=True, unique=True)
    document_id: int = Field(foreign_key="documents.id")
    task_type: str = "OCR_NLP_PIPELINE"
    
    # Priority & Scheduling
    base_priority: float = 0.0
    effective_priority: float = 0.0
    predicted_workload: float = 0.0  # predicted processing time in seconds
    combined_score: float = 0.0
    
    assigned_worker: Optional[str] = None
    status: str = Field(default="QUEUED")  # QUEUED, ASSIGNED, PROCESSING, COMPLETED, FAILED, DEAD_LETTER
    retry_count: int = 0
    processing_version: int = 1  # For idempotency check
    
    created_at: datetime = Field(default_factory=get_utc_now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

class Worker(SQLModel, table=True):
    __tablename__ = "workers"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    worker_id: str = Field(index=True, unique=True)  # e.g., "Worker_1"
    hostname: str = "localhost"
    
    # Resource & Queue metrics
    cpu_usage: float = 0.0  # Percentage (0 - 100)
    memory_usage: float = 0.0  # Percentage (0 - 100)
    active_tasks: int = 0
    queue_length: int = 0
    average_processing_time: float = 30.0  # historical average in seconds
    
    # Capability lists stored as JSON arrays
    supported_languages: List[str] = Field(default_factory=lambda: ["English"], sa_column=Column(JSON))
    supported_tasks: List[str] = Field(default_factory=lambda: ["OCR", "NLP"], sa_column=Column(JSON))
    
    # State & Health Machine
    status: str = Field(default="HEALTHY")  # STARTING, HEALTHY, DEGRADED, UNHEALTHY
    circuit_status: str = Field(default="CLOSED")  # CLOSED, OPEN, HALF_OPEN
    consecutive_failures: int = 0
    circuit_cooldown_until: Optional[datetime] = None
    last_heartbeat: datetime = Field(default_factory=get_utc_now)

class ProcessingHistory(SQLModel, table=True):
    __tablename__ = "processing_history"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="documents.id")
    worker_id: str
    
    # Document Features at processing time
    pages: int
    file_size: int
    ocr_required: bool
    language: str
    scanned_ratio: float
    document_type: str
    
    # Prediction vs Actual metrics
    predicted_complexity: float
    predicted_time: float
    actual_processing_time: float
    
    success: bool = True
    failure_reason: Optional[str] = None
    timestamp: datetime = Field(default_factory=get_utc_now)
