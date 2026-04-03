from __future__ import annotations

from datetime import datetime
from math import sqrt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.db import Vehicle, VehicleStatus, FleetLog, Station


def _distance(a_lat: float, a_lng: float, b_lat: float, b_lng: float) -> float:
    return sqrt((a_lat - b_lat) ** 2 + (a_lng - b_lng) ** 2)


async def preposition_for_station(session: AsyncSession, station: Station, reason: str, now: datetime) -> int:
    result = await session.execute(select(Vehicle).where(Vehicle.assigned_station_id == station.id))
    assigned = result.scalars().all()
    moved = 0
    for vehicle in assigned:
        if vehicle.status in {VehicleStatus.IDLE, VehicleStatus.AT_STATION}:
            vehicle.status = VehicleStatus.EN_ROUTE
            session.add(
                FleetLog(
                    vehicle_id=vehicle.id,
                    station_id=station.id,
                    timestamp=now,
                    action="PRE_POSITIONED",
                    reason=reason,
                    passengers_served=0,
                )
            )
            moved += 1
            if moved >= 2:
                break
    return moved


async def normal_allocate(session: AsyncSession, station: Station, now: datetime) -> int:
    if station.current_demand <= station.assigned_vehicles * 20:
        return 0
    result = await session.execute(select(Vehicle).where(Vehicle.assigned_station_id == station.id))
    vehicles = result.scalars().all()
    deployed = 0
    for vehicle in vehicles:
        if vehicle.status in {VehicleStatus.IDLE, VehicleStatus.AT_STATION}:
            vehicle.status = VehicleStatus.DISPATCHED
            session.add(
                FleetLog(
                    vehicle_id=vehicle.id,
                    station_id=station.id,
                    timestamp=now,
                    action="DEPLOYED",
                    reason=f"Demand {station.current_demand} exceeded threshold",
                    passengers_served=0,
                )
            )
            deployed += 1
    return deployed


async def surge_allocate(session: AsyncSession, target: Station, now: datetime, reason: str) -> list[str]:
    moved_labels: list[str] = []
    donor_result = await session.execute(select(Station).where(Station.id != target.id).order_by(Station.current_demand.asc()))
    donors = donor_result.scalars().all()

    for donor in donors:
        donor_vehicles_result = await session.execute(select(Vehicle).where(Vehicle.assigned_station_id == donor.id))
        donor_vehicles = donor_vehicles_result.scalars().all()
        if len(donor_vehicles) <= 1:
            continue

        transferable = [v for v in donor_vehicles if v.status in {VehicleStatus.IDLE, VehicleStatus.AT_STATION, VehicleStatus.EN_ROUTE}]
        quota = max(0, len(donor_vehicles) - 1)
        for vehicle in transferable[:quota]:
            vehicle.assigned_station_id = target.id
            vehicle.status = VehicleStatus.SURGE_DEPLOYED
            moved_labels.append(vehicle.label)
            session.add(
                FleetLog(
                    vehicle_id=vehicle.id,
                    station_id=target.id,
                    timestamp=now,
                    action="SURGE_DISPATCHED",
                    reason=f"{reason}; donor={donor.name}",
                    passengers_served=0,
                )
            )
            target.assigned_vehicles += 1
            donor.assigned_vehicles = max(1, donor.assigned_vehicles - 1)
            if len(moved_labels) >= 3:
                return moved_labels
    return moved_labels


async def move_vehicles_towards_station(session: AsyncSession) -> None:
    result = await session.execute(select(Vehicle, Station).join(Station, Vehicle.assigned_station_id == Station.id, isouter=True))
    rows = result.all()
    step = 0.001
    for vehicle, station in rows:
        if station is None:
            continue

        d = _distance(vehicle.current_lat, vehicle.current_lng, station.lat, station.lng)
        if d < 0.0008:
            vehicle.current_lat = station.lat
            vehicle.current_lng = station.lng
            if vehicle.status in {VehicleStatus.EN_ROUTE, VehicleStatus.DISPATCHED, VehicleStatus.SURGE_DEPLOYED}:
                vehicle.status = VehicleStatus.AT_STATION
            continue

        if vehicle.current_lat < station.lat:
            vehicle.current_lat += step
        elif vehicle.current_lat > station.lat:
            vehicle.current_lat -= step

        if vehicle.current_lng < station.lng:
            vehicle.current_lng += step
        elif vehicle.current_lng > station.lng:
            vehicle.current_lng -= step
