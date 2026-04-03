import asyncio
import os
from collections import deque
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.db import (
    AsyncSessionLocal,
    DemandLevel,
    DemandLog,
    DemandSource,
    FleetLog,
    Station,
    Train,
    TrainStatus,
    Vehicle,
    VehicleStatus,
)
from backend.simulation.allocator import (
    move_vehicles_towards_station,
    normal_allocate,
    preposition_for_station,
    surge_allocate,
)
from backend.simulation.demand import (
    calculate_exits,
    demand_level_from_value,
    occupancy_factor_for_hour,
)
from backend.simulation.scheduler import is_train_due, should_preposition, train_eta_minutes
from backend.websocket.hub import ConnectionHub


class SimulationEngine:
    def __init__(self, hub: ConnectionHub) -> None:
        self.hub = hub
        self.sim_time = datetime.fromisoformat(
            os.getenv("SIM_START_TIME", "2026-01-01T17:55:00")
        )
        self.running = False
        self.task: asyncio.Task | None = None
        self.speed_multiplier = 1
        self.logs = deque(maxlen=50)
        self.formula_snapshots = deque(maxlen=20)
        self.demand_history = deque(maxlen=30)
        self.surge_active = False
        self.surge_stations: list[int] = []

    async def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self.running = False
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    async def _run(self) -> None:
        while self.running:
            async with AsyncSessionLocal() as session:
                await self.tick(session)
            await asyncio.sleep(max(0.2, 1 / max(1, self.speed_multiplier)))

    def _append_log(self, item: dict[str, Any]) -> None:
        self.logs.append(item)

    async def tick(self, session: AsyncSession) -> None:
        self.sim_time += timedelta(minutes=1)

        station_rows = await session.execute(select(Station))
        stations = station_rows.scalars().all()

        train_rows = await session.execute(select(Train).where(Train.status != TrainStatus.CANCELLED))
        trains = train_rows.scalars().all()

        for train in trains:
            train.occupancy_factor = occupancy_factor_for_hour(self.sim_time.hour)

        for train in trains:
            if train.status != TrainStatus.ARRIVED and is_train_due(train.scheduled_arrival, self.sim_time):
                station = next((s for s in stations if s.id == train.station_id), None)
                if not station:
                    continue
                exits = calculate_exits(
                    train.coach_count,
                    train.coach_capacity,
                    train.occupancy_factor,
                    station.exit_ratio,
                )
                station.current_demand += exits
                train.expected_passengers = exits
                train.actual_arrival = self.sim_time
                train.status = TrainStatus.ARRIVED
                formula = (
                    f"{train.coach_count}×{train.coach_capacity}×"
                    f"{train.occupancy_factor:.2f}×{station.exit_ratio:.2f}={exits}"
                )
                self.formula_snapshots.append({"train": train.name, "breakdown": formula})
                session.add(
                    DemandLog(
                        station_id=station.id,
                        timestamp=self.sim_time,
                        demand_value=station.current_demand,
                        source=DemandSource.CALCULATED,
                        formula_breakdown=formula,
                        triggered_by=f"ARRIVAL:{train.name}",
                    )
                )
                self._append_log(
                    {
                        "timestamp": self.sim_time.isoformat(),
                        "action": "ARRIVAL",
                        "reason": f"{train.name} arrived with {exits} passengers",
                        "station": station.name,
                    }
                )

        detected_surge_station_ids: list[int] = []
        surge_reason_by_station: dict[int, str] = {}

        for station in stations:
            station_trains = [
                t
                for t in trains
                if t.station_id == station.id and t.actual_arrival is not None and t.status == TrainStatus.ARRIVED
            ]
            simultaneous = False
            for i in range(len(station_trains)):
                for j in range(i + 1, len(station_trains)):
                    if abs((station_trains[i].actual_arrival - station_trains[j].actual_arrival).total_seconds()) <= 300:
                        simultaneous = True
                        break
                if simultaneous:
                    break

            unmet = max(0, station.current_demand - station.assigned_vehicles * 20)
            if simultaneous or station.current_demand > 80 or unmet > 40:
                detected_surge_station_ids.append(station.id)
                if simultaneous:
                    reason = "2 trains arrived within 5 sim-min"
                elif station.current_demand > 80:
                    reason = "demand > 80"
                else:
                    reason = "unmet demand > 40"
                surge_reason_by_station[station.id] = reason

        self.surge_stations = detected_surge_station_ids
        self.surge_active = len(self.surge_stations) > 0

        for train in trains:
            if train.status != TrainStatus.ARRIVED:
                station = next((s for s in stations if s.id == train.station_id), None)
                if station and should_preposition(train.scheduled_arrival, self.sim_time):
                    moved = await preposition_for_station(
                        session,
                        station,
                        f"Pre-position for {train.name} arrival",
                        self.sim_time,
                    )
                    if moved:
                        self._append_log(
                            {
                                "timestamp": self.sim_time.isoformat(),
                                "action": "PRE_POSITIONED",
                                "reason": f"Moved {moved} vehicles before {train.name}",
                                "station": station.name,
                            }
                        )

        for station in stations:
            if station.id in self.surge_stations:
                moved_labels = await surge_allocate(
                    session,
                    station,
                    self.sim_time,
                    surge_reason_by_station.get(station.id, "SURGE"),
                )
                if moved_labels:
                    reason = surge_reason_by_station.get(station.id, "SURGE")
                    self._append_log(
                        {
                            "timestamp": self.sim_time.isoformat(),
                            "action": "SURGE_DISPATCHED",
                            "reason": f"SURGE at {station.name}: {reason}. Deploying {', '.join(moved_labels)}",
                            "station": station.name,
                        }
                    )
                    await self.hub.broadcast(
                        {
                            "type": "SURGE_ALERT",
                            "station": station.name,
                            "reason": reason,
                            "passengers": station.current_demand,
                        }
                    )
            else:
                deployed = await normal_allocate(session, station, self.sim_time)
                if deployed:
                    self._append_log(
                        {
                            "timestamp": self.sim_time.isoformat(),
                            "action": "DEPLOYED",
                            "reason": f"Deployed {deployed} vehicles for load balancing",
                            "station": station.name,
                        }
                    )

        await move_vehicles_towards_station(session)

        vehicle_rows = await session.execute(select(Vehicle))
        vehicles = vehicle_rows.scalars().all()

        total_demand = 0
        total_served = 0
        for station in stations:
            station_vehicles = [v for v in vehicles if v.assigned_station_id == station.id]
            per_tick_capacity = sum(
                v.capacity
                for v in station_vehicles
                if v.status in {VehicleStatus.AT_STATION, VehicleStatus.DISPATCHED, VehicleStatus.SURGE_DEPLOYED}
            )
            served = min(station.current_demand, per_tick_capacity)
            station.current_demand = max(0, station.current_demand - served)
            total_demand += station.current_demand + served
            total_served += served
            station.demand_level = DemandLevel(demand_level_from_value(station.current_demand))
            station.assigned_vehicles = len(station_vehicles)

        active_vehicles = len([v for v in vehicles if v.status != VehicleStatus.IDLE])
        total_vehicles = max(1, len(vehicles))
        unmet = max(0, total_demand - total_served)

        metrics = {
            "matching_efficiency": round((total_served / max(1, total_demand)) * 100, 2),
            "fleet_utilization": round((active_vehicles / total_vehicles) * 100, 2),
            "avg_wait_time": round(max(1.0, unmet / max(1, total_vehicles * 5)), 2),
            "unmet_demand_pct": round((unmet / max(1, total_demand)) * 100, 2),
        }

        self.demand_history.append(
            {
                "time": self.sim_time.strftime("%H:%M"),
                **{s.name: s.current_demand for s in stations},
            }
        )

        await session.commit()
        await self.hub.broadcast(await self._build_state_payload(session, metrics))

    async def _build_state_payload(
        self, session: AsyncSession, metrics: dict[str, float] | None = None
    ) -> dict[str, Any]:
        station_rows = await session.execute(select(Station))
        train_rows = await session.execute(select(Train))
        vehicle_rows = await session.execute(select(Vehicle))

        stations = station_rows.scalars().all()
        trains = train_rows.scalars().all()
        vehicles = vehicle_rows.scalars().all()

        if metrics is None:
            total_demand = sum(s.current_demand for s in stations)
            active = len([v for v in vehicles if v.status != VehicleStatus.IDLE])
            metrics = {
                "matching_efficiency": 100 - min(100, round((total_demand / max(1, total_demand + 1)) * 100, 2)),
                "fleet_utilization": round((active / max(1, len(vehicles))) * 100, 2),
                "avg_wait_time": round(max(1.0, total_demand / max(1, len(vehicles) * 5)), 2),
                "unmet_demand_pct": round((total_demand / max(1, total_demand + 100)) * 100, 2),
            }

        fleet_logs_rows = await session.execute(select(FleetLog).order_by(FleetLog.timestamp.desc()).limit(20))
        fleet_logs = fleet_logs_rows.scalars().all()

        payload = {
            "type": "STATE_UPDATE",
            "sim_time": self.sim_time.isoformat(),
            "stations": [
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
            ],
            "vehicles": [
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
            ],
            "trains": [
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
                    "eta_minutes": train_eta_minutes(t.scheduled_arrival, self.sim_time),
                    "formula": (
                        f"{t.coach_count}×{t.coach_capacity}×{t.occupancy_factor:.2f}×"
                        f"{next((s.exit_ratio for s in stations if s.id == t.station_id), 0.15):.2f}="
                        f"{t.expected_passengers or 0}"
                    ),
                }
                for t in trains
            ],
            "metrics": metrics,
            "logs": list(self.logs)[-20:]
            + [
                {
                    "timestamp": row.timestamp.isoformat(),
                    "action": row.action,
                    "reason": row.reason,
                    "station_id": row.station_id,
                }
                for row in reversed(fleet_logs)
            ],
            "surge_active": self.surge_active,
            "surge_stations": self.surge_stations,
            "formula_snapshots": list(self.formula_snapshots),
            "demand_series": list(self.demand_history),
        }
        return payload

    async def trigger_delay(self, train_id: int, delay_minutes: int) -> dict[str, Any]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Train).where(Train.id == train_id))
            train = result.scalar_one_or_none()
            if not train:
                return {"ok": False, "error": "Train not found"}
            train.delay_minutes += delay_minutes
            train.scheduled_arrival = train.scheduled_arrival + timedelta(minutes=delay_minutes)
            train.is_delayed = train.delay_minutes > 0
            train.status = TrainStatus.DELAYED if train.is_delayed else TrainStatus.ON_TIME
            await session.commit()
            update_payload = {
                "type": "TRAIN_UPDATE",
                "train_id": train.id,
                "status": train.status.value,
                "delay": train.delay_minutes,
            }
            await self.hub.broadcast(update_payload)
            return {"ok": True, **update_payload}

    async def trigger_demo(self) -> dict[str, Any]:
        return await self.trigger_delay(train_id=1, delay_minutes=5)

    async def book_ride(self, from_lat: float, from_lng: float, to_station_id: int) -> dict[str, Any]:
        async with AsyncSessionLocal() as session:
            station_row = await session.execute(select(Station).where(Station.id == to_station_id))
            station = station_row.scalar_one_or_none()
            if not station:
                return {"ok": False, "message": "Station not found"}

            result = await session.execute(select(Vehicle).where(Vehicle.assigned_station_id == to_station_id))
            vehicles = result.scalars().all()
            available = [v for v in vehicles if v.status in {VehicleStatus.IDLE, VehicleStatus.AT_STATION, VehicleStatus.DISPATCHED}]
            if not available:
                return {"ok": False, "message": "High demand — join waitlist"}

            picked = sorted(available, key=lambda v: abs(v.current_lat - from_lat) + abs(v.current_lng - from_lng))[0]
            picked.status = VehicleStatus.DISPATCHED
            eta = int(max(1, ((abs(picked.current_lat - from_lat) + abs(picked.current_lng - from_lng)) / 0.001)))
            await session.commit()
            return {
                "ok": True,
                "vehicle": picked.label,
                "eta_minutes": eta,
                "message": f"Assigned {picked.label}",
            }

    async def snapshot(self) -> dict[str, Any]:
        async with AsyncSessionLocal() as session:
            return await self._build_state_payload(session)

    async def metrics(self) -> dict[str, float]:
        async with AsyncSessionLocal() as session:
            state = await self._build_state_payload(session)
            return state["metrics"]
