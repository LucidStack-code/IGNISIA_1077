import os
import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Boolean,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./transitmind.db",
)

engine = create_async_engine(DATABASE_URL, future=True, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


class StationType(str, enum.Enum):
    TERMINUS = "TERMINUS"
    MAJOR_JUNCTION = "MAJOR_JUNCTION"
    INTERMEDIATE = "INTERMEDIATE"


class DemandLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    SURGE = "SURGE"


class VehicleType(str, enum.Enum):
    AUTO = "AUTO"
    EBIKE = "EBIKE"
    CAB = "CAB"


class VehicleStatus(str, enum.Enum):
    IDLE = "IDLE"
    DISPATCHED = "DISPATCHED"
    EN_ROUTE = "EN_ROUTE"
    AT_STATION = "AT_STATION"
    SURGE_DEPLOYED = "SURGE_DEPLOYED"


class CoachType(str, enum.Enum):
    SLEEPER = "SLEEPER"
    GENERAL = "GENERAL"
    LOCAL_EMU = "LOCAL_EMU"


class TrainStatus(str, enum.Enum):
    ON_TIME = "ON_TIME"
    DELAYED = "DELAYED"
    ARRIVED = "ARRIVED"
    CANCELLED = "CANCELLED"


class DemandSource(str, enum.Enum):
    CALCULATED = "CALCULATED"
    ACTUAL = "ACTUAL"


class Station(Base):
    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    station_type: Mapped[StationType] = mapped_column(Enum(StationType), nullable=False)
    exit_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    current_demand: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    demand_level: Mapped[DemandLevel] = mapped_column(Enum(DemandLevel), default=DemandLevel.LOW, nullable=False)
    assigned_vehicles: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    platform_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    vehicles: Mapped[list["Vehicle"]] = relationship(back_populates="assigned_station")
    trains: Mapped[list["Train"]] = relationship(back_populates="station")


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    label: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    vehicle_type: Mapped[VehicleType] = mapped_column(Enum(VehicleType), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[VehicleStatus] = mapped_column(Enum(VehicleStatus), default=VehicleStatus.IDLE, nullable=False)
    current_lat: Mapped[float] = mapped_column(Float, nullable=False)
    current_lng: Mapped[float] = mapped_column(Float, nullable=False)
    assigned_station_id: Mapped[Optional[int]] = mapped_column(ForeignKey("stations.id"), nullable=True)
    passengers_onboard: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    assigned_station: Mapped[Optional[Station]] = relationship(back_populates="vehicles")


class Train(Base):
    __tablename__ = "trains"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    train_number: Mapped[str] = mapped_column(String(20), nullable=False)
    coach_count: Mapped[int] = mapped_column(Integer, nullable=False)
    coach_type: Mapped[CoachType] = mapped_column(Enum(CoachType), nullable=False)
    coach_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_arrival: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    actual_arrival: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), nullable=False)
    occupancy_factor: Mapped[float] = mapped_column(Float, default=0.6, nullable=False)
    expected_passengers: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[TrainStatus] = mapped_column(Enum(TrainStatus), default=TrainStatus.ON_TIME, nullable=False)
    is_delayed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    delay_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    station: Mapped[Station] = relationship(back_populates="trains")


class DemandLog(Base):
    __tablename__ = "demand_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    demand_value: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[DemandSource] = mapped_column(Enum(DemandSource), default=DemandSource.CALCULATED, nullable=False)
    formula_breakdown: Mapped[str] = mapped_column(Text, nullable=False)
    triggered_by: Mapped[str] = mapped_column(String(140), nullable=False)


class FleetLog(Base):
    __tablename__ = "fleet_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=False)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    passengers_served: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
