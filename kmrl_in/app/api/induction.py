from fastapi import APIRouter, Body
from app.induction.engine import demo_fleet, comprehensive_plan, fitness_validation, job_prioritization, branding_optimization, mileage_balancing, cleaning_schedule, stabling_optimization
router = APIRouter(prefix="/ai/induction", tags=["AI Induction Planning"])

def fleet_status():
    fleet=demo_fleet()
    return {"total":len(fleet),"fit":sum(fitness_validation(t)["valid"] for t in fleet),"blocked":sum(fitness_validation(t)["blocker"] for t in fleet),"avg_mileage_km":round(sum(t.mileage_km for t in fleet)/len(fleet)),"cleaning_due":sum(t.cleaning_due for t in fleet)}

@router.get("")
def induction_get(action: str = "fleet_status"):
    if action=="fleet_status": return fleet_status()
    if action=="models_status":
        return {"models":[{"name":"Fitness Validator","status":"READY","type":"Rule/ML validation","metric":"100% project-reported accuracy"},{"name":"Job Card Prioritizer","status":"READY","type":"Regression/prioritization","metric":"94.7% project-reported R²"},{"name":"Branding Optimizer","status":"READY","type":"Risk scoring"},{"name":"Mileage Balancer","status":"READY","type":"Optimization"},{"name":"Cleaning Scheduler","status":"READY","type":"Constraint scheduling"},{"name":"Stabling Optimizer","status":"READY","type":"Geometry optimization"},{"name":"Decision Engine","status":"READY","type":"Multi-objective weighted scoring"}]}
    if action=="comprehensive_plan": return comprehensive_plan()
    return {"error":"Unknown action"}

@router.post("")
def induction_post(payload: dict = Body(default={} )):
    action=payload.get("action","comprehensive_plan")
    fleet=demo_fleet()
    if action=="fitness_validation": return [fitness_validation(t) for t in fleet]
    if action=="job_prioritization": return [job_prioritization(t) for t in fleet]
    if action=="branding_optimization": return [branding_optimization(t) for t in fleet]
    if action=="mileage_balancing": return [mileage_balancing(t) for t in fleet]
    if action=="cleaning_schedule": return [cleaning_schedule(t,payload.get("bays",4),payload.get("staff",6)) for t in fleet]
    if action=="stabling_optimization": return stabling_optimization(fleet,payload.get("depot_bays",30))
    return comprehensive_plan(fleet,payload.get("weights"),payload.get("bays",4),payload.get("staff",6),payload.get("depot_bays",30))
