from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.ai import AIAnalysis
from app.models.macro import MacroIndicator
from app.models.risk import DashboardContent, RiskRegisterEntry
from app.schemas.dashboard import (
    DashboardContentItem,
    DashboardSnapshotResponse,
    MacroIndicatorItem,
    RiskRegisterItem,
)
from app.schemas.ai import saved_analysis_payload
from app.services.macro_ingestion import get_latest_macro_indicators

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

DEFAULT_RISK_REGISTER_SEEDS = [
    {
        "risk_category": "Capital Adequacy Risk",
        "materiality": "Major",
        "trend": "unchanged",
        "risk_owner": "CFO",
        "display_order": 1,
    },
    {
        "risk_category": "Legal and Contract Management Risk",
        "materiality": "Moderate",
        "trend": "unchanged",
        "risk_owner": "General Counsel",
        "display_order": 2,
    },
    {
        "risk_category": "Counterparty Default Risk",
        "materiality": "Major",
        "trend": "increasing",
        "risk_owner": "Chief Risk Officer",
        "display_order": 3,
    },
    {
        "risk_category": "Project Selection and Planning Risk",
        "materiality": "Moderate",
        "trend": "unchanged",
        "risk_owner": "COO",
        "display_order": 4,
    },
    {
        "risk_category": "Market Opportunity Risk",
        "materiality": "Moderate",
        "trend": "decreasing",
        "risk_owner": "Commercial Director",
        "display_order": 5,
    },
]


def ensure_risk_register_seeded(db: Session) -> list[RiskRegisterEntry]:
    risk_stmt = (
        select(RiskRegisterEntry)
        .where(RiskRegisterEntry.active.is_(True))
        .order_by(RiskRegisterEntry.display_order, RiskRegisterEntry.id)
    )
    risks = list(db.scalars(risk_stmt).all())
    if not risks:
        for seed in DEFAULT_RISK_REGISTER_SEEDS:
            entry = RiskRegisterEntry(
                risk_category=seed["risk_category"],
                materiality=seed["materiality"],
                trend=seed["trend"],
                risk_owner=seed["risk_owner"],
                display_order=seed["display_order"],
                active=True,
            )
            db.add(entry)
        db.commit()
        risks = list(db.scalars(risk_stmt).all())
    return risks


def normalize_trend(val: Any) -> str:
    v = str(val or "").strip().lower()
    if v in ("increased", "increasing"):
        return "increasing"
    if v in ("reduced", "decreasing"):
        return "decreasing"
    return "unchanged"


def normalize_materiality(val: Any) -> str:
    allowed = {"low": "Low", "moderate": "Moderate", "major": "Major", "catastrophic": "Catastrophic"}
    return allowed.get(str(val or "").strip().lower(), "Moderate")


@router.get("/snapshot", response_model=DashboardSnapshotResponse)
def get_dashboard_snapshot(db: Annotated[Session, Depends(get_db)]) -> DashboardSnapshotResponse:
    now = datetime.now(timezone.utc)
    today_str = now.date().isoformat()

    # Official latest values, statistics and spreads share one exact Platts lineage.
    from app.services.official_market import official_market_snapshot
    market_stats, outliers, product_spreads = official_market_snapshot(db)

    # 3. Macro indicators (from verified official publisher records in database)
    latest_macros = get_latest_macro_indicators(db)
    macro_items = [
        MacroIndicatorItem(
            id=m.id,
            indicator_key=m.indicator_key,
            display_name=m.display_name,
            value=m.value,
            unit=m.unit,
            reporting_period=m.reporting_period,
            source=m.source,
            source_url=m.source_url,
            published_at=m.published_at,
            retrieved_at=m.retrieved_at,
            status=m.status,
            freshness_status=m.freshness_status,
            metadata_json=m.metadata_json or {},
        )
        for m in latest_macros
    ]

    # 4. Risk register (simplified fields)
    risks = ensure_risk_register_seeded(db)
    risk_items = [
        RiskRegisterItem(
            id=r.id,
            risk_category=r.risk_category,
            materiality=r.materiality,
            trend=r.trend,
            risk_owner=r.risk_owner,
            display_order=r.display_order,
            active=r.active,
        )
        for r in risks
    ]

    # 5. Dashboard content
    content_stmt = (
        select(DashboardContent)
        .where(DashboardContent.active.is_(True))
        .order_by(DashboardContent.section_key, DashboardContent.display_order, DashboardContent.id)
    )
    contents = db.scalars(content_stmt).all()
    content_items = [
        DashboardContentItem(
            id=c.id,
            section_key=c.section_key,
            item_key=c.item_key,
            title=c.title,
            content=c.content,
            classification=c.classification,
            metadata_json=c.metadata_json or {},
            display_order=c.display_order,
            active=c.active,
        )
        for c in contents
    ]

    # 6. Latest AI analysis
    ai_stmt = (
        select(AIAnalysis.output_json)
        .where(
            AIAnalysis.analysis_type == "daily_dashboard_analysis",
            AIAnalysis.status == "completed",
            AIAnalysis.output_json.is_not(None),
        )
        .order_by(desc(AIAnalysis.generated_at), desc(AIAnalysis.id))
        .limit(1)
    )
    latest_ai = db.scalars(ai_stmt).first()
    ai_analysis_dict = saved_analysis_payload(latest_ai) if latest_ai else None

    return DashboardSnapshotResponse(
        snapshot_date=today_str,
        generated_at=now.isoformat(),
        market_stats=market_stats,
        outliers=outliers,
        product_spreads=product_spreads,
        macro_indicators=macro_items,
        risk_register=risk_items,
        dashboard_content=content_items,
        ai_analysis=ai_analysis_dict,
    )


@router.get("/risk-register", response_model=list[RiskRegisterItem])
def get_risk_register(db: Annotated[Session, Depends(get_db)]) -> list[RiskRegisterItem]:
    risks = ensure_risk_register_seeded(db)
    return [
        RiskRegisterItem(
            id=r.id,
            risk_category=r.risk_category,
            materiality=r.materiality,
            trend=r.trend,
            risk_owner=r.risk_owner,
            display_order=r.display_order,
            active=r.active,
        )
        for r in risks
    ]


@router.put("/risk-register", response_model=list[RiskRegisterItem])
def update_risk_register(
    body: list[dict[str, Any]] | dict[str, Any],
    db: Annotated[Session, Depends(get_db)],
) -> list[RiskRegisterItem]:
    raw_rows = body if isinstance(body, list) else body.get("rows", [])
    if not isinstance(raw_rows, list):
        raise HTTPException(status_code=400, detail="Invalid risk register format")

    existing = db.scalars(select(RiskRegisterEntry).where(RiskRegisterEntry.active.is_(True))).all()
    for e in existing:
        e.active = False

    for idx, row in enumerate(raw_rows):
        cat = str(row.get("risk_category") or row.get("riskCategory") or "").strip()
        if not cat:
            continue
        mat = normalize_materiality(row.get("materiality"))
        tr = normalize_trend(row.get("trend") or row.get("movement"))
        owner = str(row.get("risk_owner") or row.get("riskOwner") or "").strip()
        disp = int(row.get("display_order") or (idx + 1))
        entry = RiskRegisterEntry(
            risk_category=cat,
            materiality=mat,
            trend=tr,
            risk_owner=owner,
            display_order=disp,
            active=True,
        )
        db.add(entry)

    db.commit()

    risks = db.scalars(
        select(RiskRegisterEntry)
        .where(RiskRegisterEntry.active.is_(True))
        .order_by(RiskRegisterEntry.display_order, RiskRegisterEntry.id)
    ).all()

    return [
        RiskRegisterItem(
            id=r.id,
            risk_category=r.risk_category,
            materiality=r.materiality,
            trend=r.trend,
            risk_owner=r.risk_owner,
            display_order=r.display_order,
            active=r.active,
        )
        for r in risks
    ]
