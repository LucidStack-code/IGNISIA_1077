import asyncio
from datetime import datetime

from sqlalchemy import delete

from backend.models.db import (
    AsyncSessionLocal,
    CoachType,
    DemandLevel,
    DemandLog,
    FleetLog,
    Station,
    StationType,
    Train,
    TrainStatus,
    Vehicle,
    VehicleStatus,
    VehicleType,
    init_db,
)
from backend.simulation.demand import calculate_exits


async def seed() -> None:
    await init_db()

    async with AsyncSessionLocal() as session:
        await session.execute(delete(FleetLog))
        await session.execute(delete(DemandLog))
        await session.execute(delete(Train))
        await session.execute(delete(Vehicle))
        await session.execute(delete(Station))
        await session.commit()

        pune = Station(
            name="Pune Junction",
            lat=18.5284,
            lng=73.8744,
            city="Pune",
            station_type=StationType.TERMINUS,
            exit_ratio=0.95,
            current_demand=0,
            demand_level=DemandLevel.LOW,
            assigned_vehicles=4,
            platform_count=6,
        )
        shivaji = Station(
            name="Shivajinagar",
            lat=18.5314,
            lng=73.8446,
            city="Pune",
            station_type=StationType.MAJOR_JUNCTION,
            exit_ratio=0.40,
            current_demand=0,
            demand_level=DemandLevel.LOW,
            assigned_vehicles=4,
            platform_count=2,
        )
        hadapsar = Station(
            name="Hadapsar",
            lat=18.4967,
            lng=73.9269,
            city="Pune",
            station_type=StationType.INTERMEDIATE,
            exit_ratio=0.15,
            current_demand=0,
            demand_level=DemandLevel.LOW,
            assigned_vehicles=2,
            platform_count=2,
        )
        session.add_all([pune, shivaji, hadapsar])
        await session.flush()

        t1_expected = calculate_exits(18, 72, 0.95, 0.95)
        t2_expected = calculate_exits(14, 72, 0.95, 0.95)
        t3_expected = calculate_exits(12, 200, 0.95, 0.40)

        trains = [
            Train(
                name="Deccan Express",
                train_number="12127",
                coach_count=18,
                coach_type=CoachType.SLEEPER,
                coach_capacity=72,
                scheduled_arrival=datetime.fromisoformat("2026-01-01T18:00:00"),
                station_id=pune.id,
                occupancy_factor=0.95,
                expected_passengers=t1_expected,
                status=TrainStatus.ON_TIME,
                is_delayed=False,
                delay_minutes=0,
            ),
            Train(
                name="Sahyadri Express",
                train_number="11023",
                coach_count=14,
                coach_type=CoachType.SLEEPER,
                coach_capacity=72,
                scheduled_arrival=datetime.fromisoformat("2026-01-01T18:05:00"),
                station_id=pune.id,
                occupancy_factor=0.95,
                expected_passengers=t2_expected,
                status=TrainStatus.ON_TIME,
                is_delayed=False,
                delay_minutes=0,
            ),
            Train(
                name="Pune Local EMU",
                train_number="LOCAL-01",
                coach_count=12,
                coach_type=CoachType.LOCAL_EMU,
                coach_capacity=200,
                scheduled_arrival=datetime.fromisoformat("2026-01-01T18:10:00"),
                station_id=shivaji.id,
                occupancy_factor=0.95,
                expected_passengers=t3_expected,
                status=TrainStatus.ON_TIME,
                is_delayed=False,
                delay_minutes=0,
            ),
        ]
        session.add_all(trains)

        vehicles = [
            Vehicle(label="AUTO-01", vehicle_type=VehicleType.AUTO, capacity=3, status=VehicleStatus.AT_STATION, current_lat=18.5284, current_lng=73.8744, assigned_station_id=pune.id, passengers_onboard=0),
            Vehicle(label="AUTO-02", vehicle_type=VehicleType.AUTO, capacity=3, status=VehicleStatus.AT_STATION, current_lat=18.5280, current_lng=73.8740, assigned_station_id=pune.id, passengers_onboard=0),
            Vehicle(label="AUTO-03", vehicle_type=VehicleType.AUTO, capacity=3, status=VehicleStatus.AT_STATION, current_lat=18.5278, current_lng=73.8750, assigned_station_id=pune.id, passengers_onboard=0),
            Vehicle(label="CAB-01", vehicle_type=VehicleType.CAB, capacity=4, status=VehicleStatus.AT_STATION, current_lat=18.5290, current_lng=73.8745, assigned_station_id=pune.id, passengers_onboard=0),
            Vehicle(label="AUTO-04", vehicle_type=VehicleType.AUTO, capacity=3, status=VehicleStatus.AT_STATION, current_lat=18.5314, current_lng=73.8446, assigned_station_id=shivaji.id, passengers_onboard=0),
            Vehicle(label="AUTO-05", vehicle_type=VehicleType.AUTO, capacity=3, status=VehicleStatus.AT_STATION, current_lat=18.5310, current_lng=73.8450, assigned_station_id=shivaji.id, passengers_onboard=0),
            Vehicle(label="EBIKE-01", vehicle_type=VehicleType.EBIKE, capacity=1, status=VehicleStatus.AT_STATION, current_lat=18.5320, current_lng=73.8440, assigned_station_id=shivaji.id, passengers_onboard=0),
            Vehicle(label="CAB-02", vehicle_type=VehicleType.CAB, capacity=4, status=VehicleStatus.AT_STATION, current_lat=18.5308, current_lng=73.8438, assigned_station_id=shivaji.id, passengers_onboard=0),
            Vehicle(label="AUTO-06", vehicle_type=VehicleType.AUTO, capacity=3, status=VehicleStatus.AT_STATION, current_lat=18.4967, current_lng=73.9269, assigned_station_id=hadapsar.id, passengers_onboard=0),
            Vehicle(label="EBIKE-02", vehicle_type=VehicleType.EBIKE, capacity=1, status=VehicleStatus.AT_STATION, current_lat=18.4970, current_lng=73.9272, assigned_station_id=hadapsar.id, passengers_onboard=0),
        ]
        session.add_all(vehicles)
        await session.commit()

    print("Seed completed for TransitMind AI Pune scenario.")


if __name__ == "__main__":
    asyncio.run(seed())
