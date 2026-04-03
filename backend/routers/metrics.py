from fastapi import APIRouter, Request

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/")
async def get_metrics(request: Request):
    engine = request.app.state.sim_engine
    return await engine.metrics()
