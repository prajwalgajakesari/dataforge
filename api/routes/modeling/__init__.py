"""
Modeling routes aggregation.

This module aggregates all modeling-related routers including
sessions, discovery, profiling, design, and generation.
"""

from fastapi import APIRouter

from .sessions import router as sessions_router
from .discovery import router as discovery_router
from .profiling import router as profiling_router
from .design import router as design_router
from .generation import router as generation_router

router = APIRouter()

# Session management routes
router.include_router(
    sessions_router,
    prefix="/sessions",
    tags=["Sessions"],
)

# Discovery routes (nested under sessions)
router.include_router(
    discovery_router,
    tags=["Discovery"],
)

# Profiling routes (nested under sessions)
router.include_router(
    profiling_router,
    tags=["Profiling"],
)

# Design routes (nested under sessions)
router.include_router(
    design_router,
    tags=["Design"],
)

# Generation routes (nested under sessions)
router.include_router(
    generation_router,
    tags=["Generation"],
)
