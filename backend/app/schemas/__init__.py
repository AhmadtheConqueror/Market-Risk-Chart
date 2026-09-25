from app.schemas.ai import (
    AIAnalyseRequest,
    AIAnalyseResponse,
    AIChatRequest,
    AIChatResponse,
)
from app.schemas.dashboard import (
    DashboardContentItem,
    DashboardSnapshotResponse,
    MacroIndicatorItem,
    RiskRegisterItem,
)
from app.schemas.health import HealthResponse
from app.schemas.market import (
    HistoryPoint,
    InstrumentStatsResponse,
    MarketHistoryResponse,
    MarketInstrumentResponse,
    MarketLatestResponse,
    MarketRefreshResponse,
    NormalizedObservation,
    ProductSpreadItem,
)

# Backwards compatibility alias
MarketObservationResponse = NormalizedObservation

__all__ = [
    "AIAnalyseRequest",
    "AIAnalyseResponse",
    "AIChatRequest",
    "AIChatResponse",
    "DashboardContentItem",
    "DashboardSnapshotResponse",
    "HealthResponse",
    "HistoryPoint",
    "InstrumentStatsResponse",
    "MacroIndicatorItem",
    "MarketHistoryResponse",
    "MarketInstrumentResponse",
    "MarketLatestResponse",
    "MarketObservationResponse",
    "MarketRefreshResponse",
    "NormalizedObservation",
    "ProductSpreadItem",
    "RiskRegisterItem",
]
