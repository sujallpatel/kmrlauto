from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from app.core.config import settings
from app.db.session import init_db, engine
from app.api.endpoints import router as api_router
from app.api.induction import router as induction_router
from app.models.schema import Worker
from load_balancer.worker_manager import worker_manager

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Intelligent Document Load Balancer Service between FastAPI and Celery Workers"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")
app.include_router(induction_router, prefix="/api")

@app.on_event("startup")
def on_startup():
    init_db()
    with Session(engine) as session:
        # Pre-seed candidate workers if database is empty
        existing = session.exec(select(Worker)).all()
        if not existing:
            # Worker 1: Standard OCR/NLP (English)
            worker_manager.register_or_update_heartbeat(
                session, worker_id="Worker_1", hostname="worker1.node",
                cpu_usage=35.0, memory_usage=40.0,
                supported_languages=["English"], supported_tasks=["OCR", "NLP"]
            )
            # Worker 2: Specialized Malayalam + English OCR/NLP
            worker_manager.register_or_update_heartbeat(
                session, worker_id="Worker_2", hostname="worker2.node",
                cpu_usage=55.0, memory_usage=50.0,
                supported_languages=["English", "Malayalam"], supported_tasks=["OCR", "NLP"]
            )
            # Worker 3: High Capacity Worker
            worker_manager.register_or_update_heartbeat(
                session, worker_id="Worker_3", hostname="worker3.node",
                cpu_usage=20.0, memory_usage=25.0,
                supported_languages=["English", "Malayalam", "Mixed"], supported_tasks=["OCR", "NLP", "HIGH_CAPACITY"]
            )

@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "docs_url": "/docs",
        "api_prefix": "/api"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
