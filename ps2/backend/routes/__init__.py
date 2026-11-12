from .assessments import router as assessments_router
from .submissions import router as submissions_router
from .evaluations import router as evaluations_router
from .moderation import router as moderation_router

__all__ = [
    "assessments_router",
    "submissions_router",
    "evaluations_router",
    "moderation_router",
]

