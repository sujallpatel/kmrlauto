# KMRL AI-Powered Trainset Induction Planning — Integrated Edition

This edition adds an operator-facing PHP dashboard and a FastAPI induction-planning API to the supplied KMRL intelligent-load-balancer repository. The dashboard covers the six induction decision modules and the configurable multi-objective decision engine.

## Run locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Serve `frontend/` through Apache/PHP or PHP's local server:

```bash
php -S 127.0.0.1:8080 -t frontend
```

The PHP proxy defaults to `http://127.0.0.1:8000`. Set `KMRL_BACKEND_URL` when the API is elsewhere.

## Docker

```bash
docker compose -f docker-compose.integrated.yml up --build
```

Open `http://localhost:8080`. API docs are at `http://localhost:8000/docs`.

## Induction API

GET:
- `/api/ai/induction?action=fleet_status`
- `/api/ai/induction?action=models_status`
- `/api/ai/induction?action=comprehensive_plan`

POST `/api/ai/induction` with `{ "action": "fitness_validation" }`, `job_prioritization`, `branding_optimization`, `mileage_balancing`, `cleaning_schedule`, `stabling_optimization`, or `comprehensive_plan`.

## Important production note

The included fleet is a deterministic demonstration dataset so the dashboard works immediately. Replace it with authorized KMRL/Maximo/CMMS/fleet feeds before operational use. Project-reported metrics in the UI are labeled as such and should be validated against real operational data.
