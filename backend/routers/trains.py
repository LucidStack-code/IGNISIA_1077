from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.db import Train, get_db
from backend.simulation.scheduler import train_eta_minutes

router = APIRouter(prefix="/trains", tags=["trains"])


@router.get("/")
async def list_trains(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Train).order_by(Train.scheduled_arrival.asc()))
    trains = result.scalars().all()
    now = datetime.utcnow()
    return [
        {
            "id": t.id,
            "name": t.name,
            "train_number": t.train_number,
            "coach_count": t.coach_count,
            "coach_type": t.coach_type.value,
            "coach_capacity": t.coach_capacity,
            "scheduled_arrival": t.scheduled_arrival.isoformat(),
            "actual_arrival": t.actual_arrival.isoformat() if t.actual_arrival else None,
            "station_id": t.station_id,
            "occupancy_factor": t.occupancy_factor,
            "expected_passengers": t.expected_passengers,
            "status": t.status.value,
            "is_delayed": t.is_delayed,
            "delay_minutes": t.delay_minutes,
            "eta_minutes": train_eta_minutes(t.scheduled_arrival, now),
        }
        for t in trains
    ]
