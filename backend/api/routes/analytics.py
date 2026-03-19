"""Frontend-facing analytics endpoints (Task 13 Phase 3)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api.auth.router import get_current_active_user
from backend.api.auth.models import User
from backend.monitoring.analytics_tracker import (
    get_user_activity_overview_sync,
    get_analysis_performance_timeseries_sync,
)


router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/me/overview")
async def my_activity_overview(
    days: int = Query(default=7, ge=1, le=90),
    current_user: User = Depends(get_current_active_user),
):
    """Return dashboard cards for current user's recent activity."""
    return get_user_activity_overview_sync(user_id=str(current_user.id), days=days)


@router.get("/performance")
async def analysis_performance(
    days: int = Query(default=7, ge=1, le=90),
    current_user: User = Depends(get_current_active_user),
):
    """Return analysis/performance time series for dashboard charts."""
    return get_analysis_performance_timeseries_sync(days=days)
