from fastapi import APIRouter
from app.api.ai import router as ai_router
from app.api.calendar import router as calendar_router
from app.api.dashboard import get_risk_register, router as dashboard_router, update_risk_register
from app.api.health import router as health_router
from app.api.macro import router as macro_router
from app.api.market import router as market_router
from app.api.news import router as news_router
from app.schemas.dashboard import RiskRegisterItem

api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
api_router.include_router(market_router)
api_router.include_router(news_router)
api_router.include_router(macro_router)
api_router.include_router(dashboard_router)
api_router.include_router(ai_router)
api_router.include_router(calendar_router)

api_router.add_api_route("/risk-register", get_risk_register, methods=["GET"], response_model=list[RiskRegisterItem], tags=["risk-register"])
api_router.add_api_route("/risk-register", update_risk_register, methods=["PUT"], response_model=list[RiskRegisterItem], tags=["risk-register"])

__all__ = ["api_router"]
