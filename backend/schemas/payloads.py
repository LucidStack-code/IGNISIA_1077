from pydantic import BaseModel


class TriggerDelayPayload(BaseModel):
    train_id: int
    delay_minutes: int


class BookRidePayload(BaseModel):
    from_lat: float
    from_lng: float
    to_station_id: int


class TriggerDemoPayload(BaseModel):
    type: str = "TRIGGER_DEMO"


class RequestSnapshotPayload(BaseModel):
    type: str = "REQUEST_SNAPSHOT"
