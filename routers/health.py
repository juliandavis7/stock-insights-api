"""Health check endpoint router."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from rate_limit import user_limiter, HEALTH_USER_LIMIT

router = APIRouter()


@router.get("/health")
@user_limiter.limit(HEALTH_USER_LIMIT)
def health_check(request: Request):
    """Check if the API is running."""
    return JSONResponse(content={"status": "ok"})

