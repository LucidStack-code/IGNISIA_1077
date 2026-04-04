"""
Fleet Optimization Engine
Pre-positions drivers before predicted demand using OR-Tools or simplified greedy algorithm
"""
import math
from typing import List, Dict, Tuple, Optional
from datetime import datetime


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in km between two lat/lon points"""
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


BATTERY_CRITICAL = 0.05
BATTERY_LOW = 0.20
RESTRICTED_RADIUS_KM = 2.0


def score_driver_for_hotspot(
    driver: Dict,
    hotspot: Dict,
    distance_km: float,
    weight_distance: float = 0.5,
    weight_idle: float = 0.3,
    weight_rating: float = 0.2,
) -> float:
    """
    Lower score = better candidate
    Score = w_dist * normalized_dist - w_rating * rating + w_idle * (1/idle_minutes)
    """
    dist_score = distance_km / 10.0  # normalize to 0–1 for 10km range

    idle_since = driver.get("idle_since")
    if idle_since:
        if isinstance(idle_since, str):
            idle_since = datetime.fromisoformat(idle_since.replace("Z", "+00:00").replace("+00:00", ""))
        idle_minutes = max(1, (datetime.utcnow() - idle_since.replace(tzinfo=None)).total_seconds() / 60)
    else:
        idle_minutes = 10

    idle_score = 1 / (1 + idle_minutes / 30)  # longer idle = lower score (best)
    rating_score = (5.0 - driver.get("rating", 4.5)) / 5.0 

    # Battery factor: lower battery is worse for far hotspots
    battery = driver.get("battery_level", 1.0)
    battery_penalty = 0
    if battery < BATTERY_LOW:
        battery_penalty = (BATTERY_LOW - battery) * 5.0 # High penalty
    
    total = (weight_distance * dist_score) + (weight_idle * idle_score) + (weight_rating * rating_score) + battery_penalty
    return round(total, 4)


def greedy_assignment(
    drivers: List[Dict],
    hotspots: List[Dict],
    radius_km: float = 5.0,
) -> List[Dict]:
    """
    Greedy fleet pre-positioning algorithm:
    1. For each hotspot (sorted by predicted demand desc), find candidate drivers
    2. Assign best drivers to cover predicted demand
    3. Return assignment list
    """
    assignments = []
    assigned_driver_ids = set()

    # Sort hotspots by demand (descending)
    sorted_hotspots = sorted(hotspots, key=lambda h: h.get("predicted_passengers", 0), reverse=True)

    for hotspot in sorted_hotspots:
        hlat = hotspot.get("lat", 0)
        hlon = hotspot.get("lon", 0)
        predicted = hotspot.get("predicted_passengers", 50)
        station_id = hotspot.get("station_id", "")

        # Estimate vehicles needed: 1 vehicle per 3 passengers (avg occupancy 3)
        vehicles_needed = max(1, math.ceil(predicted / 3))

        # Find available unassigned drivers within radius
        candidates = []
        for driver in drivers:
            if not driver.get("is_online") or not driver.get("is_available"):
                continue
            if driver["id"] in assigned_driver_ids:
                continue

            # Battery constraints (Twist 2)
            battery = driver.get("battery_level", 1.0)
            is_charging = driver.get("is_charging", False)
            
            if battery < BATTERY_CRITICAL or is_charging:
                continue
            
            dist = haversine(driver["lat"], driver["lon"], hlat, hlon)
            
            # Restricted routing for low battery: Only trips < 2km
            if battery < BATTERY_LOW:
                if dist > RESTRICTED_RADIUS_KM:
                    continue # too far for restricted driver
            
            if dist <= radius_km:
                score = score_driver_for_hotspot(driver, hotspot, dist)
                candidates.append((score, dist, driver))

        # Sort by score (ascending = best first)
        candidates.sort(key=lambda x: x[0])

        # Assign top N drivers
        assigned_count = 0
        for score, dist, driver in candidates:
            if assigned_count >= vehicles_needed:
                break
            assignments.append({
                "driver_id": driver["id"],
                "driver_name": driver.get("name", ""),
                "vehicle_type": driver.get("vehicle_type", "auto"),
                "driver_lat": driver["lat"],
                "driver_lon": driver["lon"],
                "hotspot_station_id": station_id,
                "hotspot_lat": hlat,
                "hotspot_lon": hlon,
                "predicted_passengers": predicted,
                "vehicles_needed": vehicles_needed,
                "distance_km": round(dist, 2),
                "score": score,
                "eta_minutes": round(dist / 0.4, 1),  # assume 24km/h avg speed
            })
            assigned_driver_ids.add(driver["id"])
            assigned_count += 1

    return assignments


def surge_rebalance(
    drivers: List[Dict],
    hotspots: List[Dict],
    active_surges: int = 1,
) -> Tuple[List[Dict], float]:
    """
    Surge rebalancing: expand radius 5→8km when multiple train arrivals overlap
    Returns expanded assignments and coverage ratio
    """
    base_radius = 5.0
    expanded_radius = 5.0 + min(3.0, active_surges * 1.5)

    assignments = greedy_assignment(drivers, hotspots, radius_km=expanded_radius)

    total_demand = sum(h.get("predicted_passengers", 0) for h in hotspots)
    covered_demand = sum(a.get("predicted_passengers", 0) for a in assignments)
    coverage = min(1.0, covered_demand / max(1, total_demand))

    return assignments, round(coverage, 3), expanded_radius


def real_time_match(
    passenger: Dict,
    available_drivers: List[Dict],
    max_radius_km: float = 3.0,
) -> Optional[Dict]:
    """
    Real-time passenger ↔ driver matching
    Scoring: distance (40%) + wait_time (35%) - rating bonus (25%)
    Returns best driver or None
    """
    plat = passenger.get("pickup_lat", 0)
    plon = passenger.get("pickup_lon", 0)

    best_driver = None
    best_score = float("inf")

    for driver in available_drivers:
        if not driver.get("is_available") or not driver.get("is_online"):
            continue
        dist = haversine(plat, plon, driver["lat"], driver["lon"])
        if dist > max_radius_km:
            continue

        # Estimate wait time (24 km/h city speed)
        wait_min = (dist / 24) * 60

        dist_score = dist / max_radius_km
        wait_score = wait_min / 15  # normalize to 15 min max
        rating_bonus = (driver.get("rating", 4.0) - 4.0) / 1.0  # 0 to 1

        score = 0.40 * dist_score + 0.35 * wait_score - 0.25 * rating_bonus

        if score < best_score:
            best_score = score
            best_driver = {**driver, "distance_km": round(dist, 2),
                           "eta_minutes": round(wait_min, 1), "match_score": round(score, 4)}

    return best_driver


def proactive_rebalance_future(
    drivers: List[Dict],
    future_hotspots: List[Dict],
    radius_km: float = 8.0,
) -> List[Dict]:
    """
    Twist 1: Pre-positioning logic for future surges (T+30).
    Filters for high-battery drivers (>40%) to ensure they have enough power 
    for proactive long-distance repositioning.
    """
    assignments = []
    assigned_driver_ids = set()

    for hotspot in future_hotspots:
        hlat = hotspot.get("lat", 0)
        hlon = hotspot.get("lon", 0)
        predicted = hotspot.get("predicted_passengers", 50)
        station_id = hotspot.get("station_id", "")

        # Target 1 driver per 4 pax for proactive rebalance
        vehicles_needed = max(1, math.ceil(predicted / 4))

        candidates = []
        for driver in drivers:
            if not driver.get("is_online") or not driver.get("is_available"):
                continue
            if driver["id"] in assigned_driver_ids:
                continue

            # Battery filtering (Restoration of Twist 1 Logic)
            battery = driver.get("battery_level", 1.0)
            if battery < 0.4 or driver.get("is_charging", False):
                continue

            dist = haversine(driver["lat"], driver["lon"], hlat, hlon)
            if dist <= radius_km:
                score = score_driver_for_hotspot(driver, hotspot, dist)
                candidates.append((score, dist, driver))

        candidates.sort(key=lambda x: x[0])

        assigned_count = 0
        for score, dist, driver in candidates:
            if assigned_count >= vehicles_needed:
                break
            assignments.append({
                "driver_id": driver["id"],
                "hotspot_station_id": station_id,
                "hotspot_lat": hlat,
                "hotspot_lon": hlon,
                "predicted_passengers": predicted,
                "distance_km": round(dist, 2),
                "score": score,
                "eta_minutes": round(dist / 0.4, 1),
            })
            assigned_driver_ids.add(driver["id"])
            assigned_count += 1

    return assignments
