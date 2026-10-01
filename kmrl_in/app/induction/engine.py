from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Any

DEFAULT_WEIGHTS = {
    "safety": 0.30,
    "maintenance": 0.25,
    "revenue": 0.15,
    "cost": 0.15,
    "service": 0.10,
    "efficiency": 0.05,
}

@dataclass
class Trainset:
    trainset_id: str
    fitness_valid: bool
    fitness_expiry_days: int
    maintenance_criticality: float
    overdue_job_cards: int
    branding_exposure: float
    branding_sla_risk: float
    mileage_km: float
    mileage_target_km: float
    cleaning_due: bool
    cleaning_priority: float
    preferred_bay: int
    current_bay: int
    service_readiness: float = 0.9
    component_wear: float = 0.5


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def demo_fleet() -> list[Trainset]:
    return [
        Trainset("TS-01", True, 42, .25, 1, .85, .05, 142000, 150000, False, .15, 3, 3, .95, .45),
        Trainset("TS-02", True, 18, .72, 4, .65, .30, 176000, 150000, True, .75, 8, 4, .82, .70),
        Trainset("TS-03", True, 75, .40, 2, .95, .08, 118000, 150000, True, .60, 12, 12, .92, .38),
        Trainset("TS-04", False, -3, .90, 6, .40, .55, 154000, 150000, True, .90, 15, 7, .30, .82),
        Trainset("TS-05", True, 11, .58, 3, .90, .15, 148000, 150000, False, .20, 20, 20, .88, .54),
        Trainset("TS-06", True, 55, .18, 0, .35, .70, 132000, 150000, False, .10, 22, 22, .97, .40),
    ]


def fitness_validation(t: Trainset) -> dict[str, Any]:
    risk = 1.0 if not t.fitness_valid else (0.8 if t.fitness_expiry_days <= 7 else 0.2 if t.fitness_expiry_days <= 30 else 0.05)
    return {"trainset_id": t.trainset_id, "valid": t.fitness_valid and t.fitness_expiry_days > 0, "expiry_days": t.fitness_expiry_days, "risk": round(risk, 3), "blocker": not (t.fitness_valid and t.fitness_expiry_days > 0)}


def job_prioritization(t: Trainset) -> dict[str, Any]:
    score = _clamp(0.65*t.maintenance_criticality + 0.35*min(t.overdue_job_cards/6, 1))
    return {"trainset_id": t.trainset_id, "score": round(score, 3), "criticality": t.maintenance_criticality, "overdue_job_cards": t.overdue_job_cards}


def branding_optimization(t: Trainset) -> dict[str, Any]:
    risk = _clamp(0.65*t.branding_sla_risk + 0.35*(1-t.branding_exposure))
    return {"trainset_id": t.trainset_id, "exposure": round(t.branding_exposure,3), "sla_risk": round(t.branding_sla_risk,3), "risk": round(risk,3)}


def mileage_balancing(t: Trainset) -> dict[str, Any]:
    deviation = (t.mileage_km - t.mileage_target_km) / max(t.mileage_target_km, 1)
    balance = _clamp(1 - abs(deviation))
    return {"trainset_id": t.trainset_id, "mileage_km": t.mileage_km, "target_km": t.mileage_target_km, "deviation_pct": round(deviation*100,2), "balance_score": round(balance,3), "component_wear": round(t.component_wear,3)}


def cleaning_schedule(t: Trainset, bays: int = 4, staff: int = 6) -> dict[str, Any]:
    resource_pressure = _clamp((1/bays) * 1.5 + (1/max(staff,1)) * 0.5)
    score = _clamp(0.75*t.cleaning_priority + 0.25*(1-resource_pressure))
    return {"trainset_id": t.trainset_id, "due": t.cleaning_due, "priority": round(score,3), "bays": bays, "staff": staff}


def stabling_optimization(fleet: list[Trainset], bay_count: int = 30) -> dict[str, Any]:
    assignments = []
    total_move = 0
    occupied = set()
    for t in sorted(fleet, key=lambda x: (not x.fitness_valid, abs(x.current_bay-x.preferred_bay))):
        bay = t.current_bay if t.current_bay in range(1,bay_count+1) and t.current_bay not in occupied else t.preferred_bay
        if bay in occupied:
            bay = next((b for b in range(1,bay_count+1) if b not in occupied), bay)
        occupied.add(bay)
        move = abs(t.current_bay - bay)
        total_move += move
        assignments.append({"trainset_id": t.trainset_id, "from_bay": t.current_bay, "to_bay": bay, "movement": move})
    return {"bay_count": bay_count, "total_shunting_moves": total_move, "assignments": assignments}


def comprehensive_plan(fleet: list[Trainset] | None = None, weights: dict[str,float] | None = None, bays: int = 4, staff: int = 6, depot_bays: int = 30) -> dict[str, Any]:
    fleet = fleet or demo_fleet()
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    plans=[]
    for t in fleet:
        f=fitness_validation(t); j=job_prioritization(t); b=branding_optimization(t); m=mileage_balancing(t); c=cleaning_schedule(t,bays,staff)
        safety = 1-f["risk"]
        maintenance = 1-j["score"]
        revenue = 1-b["risk"]
        cost = m["balance_score"]
        service = t.service_readiness
        efficiency = 1-c["priority"] if c["due"] else .9
        score = sum((s*v for s,v in [(w["safety"],safety),(w["maintenance"],maintenance),(w["revenue"],revenue),(w["cost"],cost),(w["service"],service),(w["efficiency"],efficiency)]))
        blocker = f["blocker"]
        recommendations=[]
        if blocker: recommendations.append("Do not induct until fitness certificate is valid")
        if j["score"]>.65: recommendations.append("Clear critical maintenance/job cards")
        if b["risk"]>.5: recommendations.append("Protect branding exposure/SLA commitment")
        if abs(m["deviation_pct"])>8: recommendations.append("Use mileage balancing opportunity")
        if c["due"]: recommendations.append("Schedule cleaning before service")
        plans.append({"trainset_id":t.trainset_id,"induction_score":round(score*100,2),"recommended":not blocker,"blocker":blocker,"risk_factors":recommendations,"components":{"fitness":f,"maintenance":j,"branding":b,"mileage":m,"cleaning":c}})
    plans.sort(key=lambda x:x["induction_score"], reverse=True)
    for i,p in enumerate(plans,1): p["rank"]=i
    stable=stabling_optimization(fleet,depot_bays)
    recommended=[p for p in plans if p["recommended"]]
    return {"generated_at":datetime.utcnow().isoformat()+"Z","weights":w,"trainset_rankings":plans,"recommended_trainsets":[p["trainset_id"] for p in recommended],"blockers":[p["trainset_id"] for p in plans if p["blocker"]],"stabling":stable,"resource_summary":{"cleaning_bays":bays,"cleaning_staff":staff,"depot_bays":depot_bays,"trainsets_evaluated":len(fleet)}}
