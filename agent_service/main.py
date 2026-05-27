from fastapi import FastAPI

from shared.api_contracts.state import StateUpdateRequest, StateUpdateResponse
from shared.api_contracts.agent import AgentDecideRequest, AgentDecideResponse
from shared.api_contracts.workout import WorkoutPlanRequest, WorkoutSessionRequest
from shared.api_contracts.equipment import GymStatusResponse
from shared.api_contracts.report import DailyReportRequest, DailyReportResponse

app = FastAPI(title="Fitness Agent Service", version="1.0.0")


@app.post("/api/v1/state/update", response_model=StateUpdateResponse)
async def update_state(request: StateUpdateRequest):
    pass


@app.post("/api/v1/agent/decide", response_model=AgentDecideResponse)
async def agent_decide(request: AgentDecideRequest):
    pass


@app.post("/api/v1/workout/plan")
async def create_workout_plan(request: WorkoutPlanRequest):
    pass


@app.post("/api/v1/workout/session")
async def log_workout_session(request: WorkoutSessionRequest):
    pass


@app.get("/api/v1/equipment/status", response_model=GymStatusResponse)
async def get_equipment_status():
    pass


@app.get("/api/v1/report/daily", response_model=DailyReportResponse)
async def get_daily_report(user_id: str, date: str):
    pass
