from fastapi import APIRouter

from app.api.routes import (
    applications,
    capture,
    health,
    intel,
    interview,
    jobs,
    profiles,
    resumes,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(profiles.router)
api_router.include_router(resumes.router)
api_router.include_router(jobs.router)
api_router.include_router(applications.router)
api_router.include_router(intel.router)
api_router.include_router(interview.router)
api_router.include_router(capture.router)
