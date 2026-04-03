from backend.models.db import StationType


def occupancy_factor_for_hour(hour: int) -> float:
    if 8 <= hour <= 10 or 17 <= hour <= 21:
        return 0.95
    if 11 <= hour <= 16:
        return 0.60
    return 0.30


def exit_ratio_for_station_type(station_type: StationType) -> float:
    if station_type == StationType.TERMINUS:
        return 0.95
    if station_type == StationType.MAJOR_JUNCTION:
        return 0.40
    return 0.15


def calculate_exits(coach_count: int, coach_capacity: int, occupancy_factor: float, exit_ratio: float) -> int:
    return int(round(coach_count * coach_capacity * occupancy_factor * exit_ratio))


def demand_level_from_value(value: int) -> str:
    if value >= 150:
        return "SURGE"
    if value >= 80:
        return "HIGH"
    if value >= 30:
        return "MEDIUM"
    return "LOW"
