from fastapi import APIRouter
from app.api.ai import router as ai_router
from app.api.dashboard import router as dashboard_router
from app.api.health import router as health_router
from app.api.macro import router as macro_router
from app.api.market import router as market_router
from app.api.news import router as news_router

api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
api_router.include_router(market_router)
api_router.include_router(news_router)
api_router.include_router(macro_router)
api_router.include_router(dashboard_router)
api_router.include_router(ai_router)

__all__ = ["api_router"]
