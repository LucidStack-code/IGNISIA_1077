from datetime import datetime


def train_eta_minutes(scheduled_arrival: datetime, sim_time: datetime) -> int:
    delta = scheduled_arrival - sim_time
    return int(delta.total_seconds() // 60)


def is_train_due(scheduled_arrival: datetime, sim_time: datetime) -> bool:
    return train_eta_minutes(scheduled_arrival, sim_time) <= 0


def should_preposition(scheduled_arrival: datetime, sim_time: datetime) -> bool:
    return train_eta_minutes(scheduled_arrival, sim_time) == 2
