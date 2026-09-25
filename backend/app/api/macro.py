from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.macro import MacroIndicatorResponse, MacroRefreshSummary
from app.services.macro_ingestion import (
    get_latest_macro_indicators,
    get_macro_history,
    run_macro_refresh,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/macro", tags=["macro"])


@router.post("/refresh", response_model=MacroRefreshSummary)
async def refresh_macro(db: Annotated[Session, Depends(get_db)]) -> MacroRefreshSummary:
    """
    Refresh all six macro indicators from official publisher sources:
    - NBS: CPI (Headline, Food, Core Inflation) & Real GDP Growth
    - Stanbic IBTC Bank / S&P Global: PMI
    - NUPRC: Strict Crude Oil Production
    """
    try:
        summary = await run_macro_refresh(db)
        return summary
    except Exception as e:
        logger.error("Error during macro indicators refresh: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Macro indicators refresh failed: {str(e)}",
        )


@router.get("/latest", response_model=list[MacroIndicatorResponse])
def get_latest_macro(db: Annotated[Session, Depends(get_db)]) -> list[MacroIndicatorResponse]:
    """
    Retrieve the latest verified observation for each of the six canonical macro indicators.
    """
    return get_latest_macro_indicators(db)


@router.get("/history", response_model=list[MacroIndicatorResponse])
def get_macro_indicator_history(
    indicator: Annotated[str, Query(description="Canonical indicator key (e.g. headline_inflation)")],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[MacroIndicatorResponse]:
    """
    Retrieve historical observations for a specific macro indicator.
    """
    try:
        return get_macro_history(db, indicator_key=indicator, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
