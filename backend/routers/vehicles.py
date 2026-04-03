from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.db import Vehicle, get_db

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.get("/")
async def list_vehicles(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Vehicle).order_by(Vehicle.id.asc()))
    vehicles = result.scalars().all()
    return [
        {
            "id": v.id,
            "label": v.label,
            "vehicle_type": v.vehicle_type.value,
            "capacity": v.capacity,
            "status": v.status.value,
            "current_lat": v.current_lat,
            "current_lng": v.current_lng,
            "assigned_station_id": v.assigned_station_id,
            "passengers_onboard": v.passengers_onboard,
        }
        for v in vehicles
    ]
