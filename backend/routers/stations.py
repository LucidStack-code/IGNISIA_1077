from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.db import Station, get_db

router = APIRouter(prefix="/stations", tags=["stations"])


@router.get("/")
async def list_stations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Station).order_by(Station.id.asc()))
    stations = result.scalars().all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "lat": s.lat,
            "lng": s.lng,
            "city": s.city,
            "station_type": s.station_type.value,
            "exit_ratio": s.exit_ratio,
            "current_demand": s.current_demand,
            "demand_level": s.demand_level.value,
            "assigned_vehicles": s.assigned_vehicles,
            "platform_count": s.platform_count,
        }
        for s in stations
    ]
