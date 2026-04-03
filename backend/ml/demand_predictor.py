# Hybrid XGBoost + LSTM demand predictor
"""
Hybrid ML Demand Prediction Module
Uses XGBoost (main) + LSTM-like pattern (mock) for passenger demand forecasting
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import random
import json


# ── Synthetic historical demand data generator ──────────────────────────────
def generate_historical_data(n_samples: int = 2000) -> pd.DataFrame:
    """Generate realistic historical passenger demand data"""
    records = []
    station_ids = [
        "PCMC", "SANT_TUKARAM", "BHOSARI", "KASARWADI", "PIMPRI",
        "CHINCHWAD", "AKURDI", "NIGDI", "SWARGATE", "MARKET_YARD",
        "SHIVAJINAGAR", "CIVIL_COURT", "PUNE_STATION", "RUBY_HALL", "RANGE_HILLS"
    ]
    station_base_demand = {
        "PUNE_STATION": 280, "SHIVAJINAGAR": 240, "SWARGATE": 220,
        "PCMC": 200, "CHINCHWAD": 180, "CIVIL_COURT": 170,
        "MARKET_YARD": 160, "PIMPRI": 150, "KASARWADI": 130,
        "RUBY_HALL": 120, "RANGE_HILLS": 110, "SANT_TUKARAM": 100,
        "BHOSARI": 90, "AKURDI": 85, "NIGDI": 80,
    }

    for _ in range(n_samples):
        station_id = random.choice(station_ids)
        ts = datetime.utcnow() - timedelta(days=random.randint(0, 90),
                                            hours=random.randint(0, 23),
                                            minutes=random.randint(0, 59))
        hour = ts.hour
        dow = ts.weekday()  # 0=Mon, 6=Sun

        # Peak hours multiplier
        if hour in [7, 8, 9]:     peak_mult = 2.5
        elif hour in [17, 18, 19]: peak_mult = 2.8
        elif hour in [10, 11, 12]: peak_mult = 1.4
        elif hour in [13, 14]:     peak_mult = 1.2
        elif hour in [6, 20, 21]:  peak_mult = 0.9
        else:                       peak_mult = 0.4

        # Weekend discount
        weekend_mult = 0.65 if dow >= 5 else 1.0

        # Weather effect
        weather = random.choices(
            ["clear", "cloudy", "rainy", "heavy_rain"],
            weights=[55, 25, 15, 5]
        )[0]
        weather_mult = {"clear": 1.0, "cloudy": 0.95, "rainy": 1.2, "heavy_rain": 1.45}[weather]

        # Delay effect (delays increase demand as more people wait)
        delay = max(0, random.gauss(2, 3))
        delay_mult = 1 + delay * 0.04

        base = station_base_demand.get(station_id, 100)
        noise = random.gauss(0, 10)
        demand = max(5, int(base * peak_mult * weekend_mult * weather_mult * delay_mult + noise))

        records.append({
            "station_id": station_id,
            "hour": hour,
            "day_of_week": dow,
            "delay_minutes": round(delay, 1),
            "weather": weather,
            "month": ts.month,
            "is_weekend": int(dow >= 5),
            "demand": demand,
        })

    return pd.DataFrame(records)


# ── Feature engineering ──────────────────────────────────────────────────────
STATION_ENCODING = {
    "PCMC": 0, "SANT_TUKARAM": 1, "BHOSARI": 2, "KASARWADI": 3,
    "PIMPRI": 4, "CHINCHWAD": 5, "AKURDI": 6, "NIGDI": 7,
    "SWARGATE": 8, "MARKET_YARD": 9, "SHIVAJINAGAR": 10,
    "CIVIL_COURT": 11, "PUNE_STATION": 12, "RUBY_HALL": 13, "RANGE_HILLS": 14,
}
WEATHER_ENCODING = {"clear": 0, "cloudy": 1, "rainy": 2, "heavy_rain": 3}


def encode_features(station_id: str, hour: int, day_of_week: int,
                    delay_minutes: float, weather: str, month: int) -> np.ndarray:
    station_enc = STATION_ENCODING.get(station_id, 0)
    weather_enc = WEATHER_ENCODING.get(weather, 0)
    is_weekend = int(day_of_week >= 5)
    # Cyclic hour encoding
    hour_sin = np.sin(2 * np.pi * hour / 24)
    hour_cos = np.cos(2 * np.pi * hour / 24)
    dow_sin = np.sin(2 * np.pi * day_of_week / 7)
    dow_cos = np.cos(2 * np.pi * day_of_week / 7)
    return np.array([
        station_enc, hour, day_of_week, delay_minutes,
        weather_enc, month, is_weekend,
        hour_sin, hour_cos, dow_sin, dow_cos
    ])


# ── XGBoost Model ────────────────────────────────────────────────────────────
class XGBoostDemandModel:
    """XGBoost-based demand prediction model"""

    def __init__(self):
        self.model = None
        self.is_trained = False
        self._train()

    def _train(self):
        try:
            import xgboost as xgb
            df = generate_historical_data(3000)
            X = np.array([
                encode_features(r.station_id, r.hour, r.day_of_week,
                                r.delay_minutes, r.weather, r.month)
                for r in df.itertuples()
            ])
            y = df["demand"].values

            self.model = xgb.XGBRegressor(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.1,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                verbosity=0,
            )
            self.model.fit(X, y)
            self.is_trained = True
            print("✅ XGBoost model trained successfully")
        except Exception as e:
            print(f"⚠️  XGBoost training note: {e}. Using fallback model.")
            self.is_trained = False

    def predict(self, station_id: str, hour: int, day_of_week: int,
                delay_minutes: float, weather: str, month: int) -> int:
        if self.is_trained and self.model:
            features = encode_features(station_id, hour, day_of_week,
                                       delay_minutes, weather, month)
            pred = self.model.predict(features.reshape(1, -1))[0]
            return max(10, int(round(pred)))
        else:
            return self._fallback_predict(station_id, hour, day_of_week, delay_minutes, weather)

    def _fallback_predict(self, station_id, hour, day_of_week, delay_minutes, weather) -> int:
        """Rule-based fallback when XGBoost unavailable"""
        base = {"PUNE_STATION": 280, "SHIVAJINAGAR": 240, "SWARGATE": 220,
                "PCMC": 200}.get(station_id, 120)
        if hour in [7, 8, 9]: base *= 2.5
        elif hour in [17, 18, 19]: base *= 2.8
        elif 10 <= hour <= 14: base *= 1.3
        if day_of_week >= 5: base *= 0.65
        if weather == "rainy": base *= 1.2
        elif weather == "heavy_rain": base *= 1.45
        base *= (1 + delay_minutes * 0.04)
        return max(10, int(base + random.gauss(0, 10)))


# ── LSTM Pattern Mock ────────────────────────────────────────────────────────
class LSTMPatternMock:
    """
    Mock LSTM that captures temporal patterns via exponential smoothing
    and historical sequence simulation — mimics LSTM output
    """

    def __init__(self):
        self.alpha = 0.3  # smoothing factor
        self._history: Dict[str, List[float]] = {}

    def update(self, station_id: str, actual_demand: float):
        if station_id not in self._history:
            self._history[station_id] = []
        self._history[station_id].append(actual_demand)
        if len(self._history[station_id]) > 48:  # keep 48 time-steps
            self._history[station_id].pop(0)

    def predict_trend_multiplier(self, station_id: str) -> float:
        """Returns trend multiplier based on recent history (1.0 = neutral)"""
        hist = self._history.get(station_id, [])
        if len(hist) < 4:
            return 1.0
        recent = hist[-4:]
        older = hist[-8:-4] if len(hist) >= 8 else recent
        recent_avg = np.mean(recent)
        older_avg = np.mean(older)
        if older_avg == 0:
            return 1.0
        trend = recent_avg / older_avg
        return float(np.clip(trend, 0.7, 1.4))


# ── Hybrid Predictor ─────────────────────────────────────────────────────────
class HybridDemandPredictor:
    """
    Combines XGBoost point estimate with LSTM trend multiplier
    XGBoost contributes 75%, LSTM trend 25% to final prediction
    """

    def __init__(self):
        print("🤖 Initializing Hybrid ML Demand Predictor...")
        self.xgb_model = XGBoostDemandModel()
        self.lstm_mock = LSTMPatternMock()
        print("✅ Hybrid Demand Predictor ready")

    def predict(
        self,
        station_id: str,
        minutes_until_arrival: int = 10,
        delay_minutes: float = 0.0,
        weather: str = "clear",
    ) -> Dict:
        now = datetime.utcnow()
        target_time = now + timedelta(minutes=minutes_until_arrival)
        hour = target_time.hour
        dow = target_time.weekday()
        month = target_time.month

        xgb_pred = self.xgb_model.predict(
            station_id, hour, dow, delay_minutes, weather, month
        )
        lstm_trend = self.lstm_mock.predict_trend_multiplier(station_id)

        # Hybrid: 75% XGBoost + 25% trend adjustment
        hybrid_pred = int(xgb_pred * (0.75 + 0.25 * lstm_trend))

        # Confidence based on hour (peak hours = higher confidence)
        if hour in [7, 8, 9, 17, 18, 19]:
            confidence = round(random.uniform(0.85, 0.95), 2)
        elif 10 <= hour <= 16:
            confidence = round(random.uniform(0.75, 0.88), 2)
        else:
            confidence = round(random.uniform(0.60, 0.78), 2)

        return {
            "station_id": station_id,
            "predicted_passengers": hybrid_pred,
            "xgboost_estimate": xgb_pred,
            "lstm_trend_multiplier": round(lstm_trend, 3),
            "confidence": confidence,
            "time_window_start": target_time.isoformat(),
            "time_window_end": (target_time + timedelta(minutes=15)).isoformat(),
            "weather": weather,
            "peak_label": _peak_label(hour),
        }

    def batch_predict(self, stations: List[Dict]) -> List[Dict]:
        results = []
        for s in stations:
            pred = self.predict(
                station_id=s.get("station_id"),
                minutes_until_arrival=s.get("minutes_until_arrival", 10),
                delay_minutes=s.get("delay_minutes", 0),
                weather=s.get("weather", "clear"),
            )
            pred["lat"] = s.get("lat", 18.5726)
            pred["lon"] = s.get("lon", 73.8546)
            results.append(pred)
        return results


def _peak_label(hour: int) -> str:
    if hour in [7, 8, 9]: return "Morning Peak"
    if hour in [17, 18, 19]: return "Evening Peak"
    if 10 <= hour <= 14: return "Midday"
    if hour in [6, 20, 21]: return "Off-Peak"
    return "Night"


# Singleton instance
_predictor_instance = None


def get_predictor() -> HybridDemandPredictor:
    global _predictor_instance
    if _predictor_instance is None:
        _predictor_instance = HybridDemandPredictor()
    return _predictor_instance
