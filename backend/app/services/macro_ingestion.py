from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import logging
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.macro import MacroIndicator, utc_now
from app.providers.macro.base import MacroDataProvider, MacroObservation
from app.providers.macro.factory import get_macro_providers
from app.schemas.macro import MacroIndicatorResponse, MacroRefreshSummary

logger = logging.getLogger(__name__)

CANONICAL_MACRO_CONFIG: dict[str, dict[str, Any]] = {
    "headline_inflation": {
        "display_name": "Headline Inflation",
        "unit": "%",
        "frequency": "monthly",
        "expected_source": "National Bureau of Statistics Nigeria",
        "min_val": Decimal("-50"),
        "max_val": Decimal("500"),
    },
    "food_inflation": {
        "display_name": "Food Inflation",
        "unit": "%",
        "frequency": "monthly",
        "expected_source": "National Bureau of Statistics Nigeria",
        "min_val": Decimal("-50"),
        "max_val": Decimal("500"),
    },
    "core_inflation": {
        "display_name": "Core Inflation",
        "unit": "%",
        "frequency": "monthly",
        "expected_source": "National Bureau of Statistics Nigeria",
        "min_val": Decimal("-50"),
        "max_val": Decimal("500"),
    },
    "real_gdp_growth": {
        "display_name": "Real GDP Growth",
        "unit": "%",
        "frequency": "quarterly",
        "expected_source": "National Bureau of Statistics Nigeria",
        "min_val": Decimal("-50"),
        "max_val": Decimal("100"),
    },
    "nigeria_pmi": {
        "display_name": "PMI",
        "unit": "index",
        "frequency": "monthly",
        "expected_source": "Stanbic IBTC Bank / S&P Global",
        "min_val": Decimal("0"),
        "max_val": Decimal("100"),
    },
    "crude_oil_production": {
        "display_name": "Crude Oil Production",
        "unit": "mbpd",
        "frequency": "monthly",
        "expected_source": "Nigerian Upstream Petroleum Regulatory Commission",
        "min_val": Decimal("0.1"),
        "max_val": Decimal("10.0"),
    },
}

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


def parse_period_approx_date(period_str: str) -> datetime | None:
    """Approximate the end date of a reporting period for freshness calculation."""
    p = period_str.strip()

    # Match monthly like "Aug 2026" or "August 2026"
    m_match = re.match(r'^([A-Za-z]+)\s+(\d{4})$', p)
    if m_match:
        m_name = m_match.group(1).lower()
        year = int(m_match.group(2))
        month = MONTH_MAP.get(m_name, 1)
        # End of the month approximation (day 28)
        return datetime(year, month, 28, tzinfo=timezone.utc)

    # Match quarterly like "Q2 2026"
    q_match = re.match(r'^Q([1-4])\s+(\d{4})$', p, re.I)
    if q_match:
        quarter = int(q_match.group(1))
        year = int(q_match.group(2))
        month = quarter * 3
        return datetime(year, month, 28, tzinfo=timezone.utc)

    return None


def determine_freshness(
    indicator_key: str,
    reporting_period: str,
    published_at: datetime | None = None,
    as_of: datetime | None = None,
) -> str:
    """
    Determine if macro data is fresh or stale based on publication cadence.
    Macro indicators are monthly or quarterly, not daily.
    - Monthly: fresh if within ~75 days of period end (allowing ~2.5 months for publication cycle).
    - Quarterly: fresh if within ~180 days of period end (allowing ~6 months for release).
    """
    now = as_of or datetime.now(timezone.utc)
    period_end = parse_period_approx_date(reporting_period)
    if not period_end:
        return "fresh"

    config = CANONICAL_MACRO_CONFIG.get(indicator_key, {})
    frequency = config.get("frequency", "monthly")

    days_elapsed = (now - period_end).total_seconds() / 86400.0

    if frequency == "quarterly":
        # GDP is released with a 2-3 month lag after quarter end
        return "fresh" if days_elapsed <= 180 else "stale"
    else:
        # Monthly indicators released 2-4 weeks after month end
        return "fresh" if days_elapsed <= 75 else "stale"


def validate_macro_observation(obs: MacroObservation) -> None:
    """Validate macro observation against canonical definitions and sanity bounds."""
    if obs.indicator_key not in CANONICAL_MACRO_CONFIG:
        raise ValueError(f"Unknown indicator key '{obs.indicator_key}'. Must be one of {list(CANONICAL_MACRO_CONFIG.keys())}")

    config = CANONICAL_MACRO_CONFIG[obs.indicator_key]
    if obs.unit != config["unit"]:
        raise ValueError(f"Unit mismatch for {obs.indicator_key}: expected '{config['unit']}', got '{obs.unit}'")

    if not isinstance(obs.value, (Decimal, int, float)):
        raise ValueError(f"Value for {obs.indicator_key} must be numeric, got {type(obs.value)}")

    val_dec = Decimal(str(obs.value))
    if val_dec < config["min_val"] or val_dec > config["max_val"]:
        raise ValueError(
            f"Sanity check failed for {obs.indicator_key}: value {val_dec} out of bounds "
            f"[{config['min_val']}, {config['max_val']}]"
        )

    if not obs.reporting_period or not obs.reporting_period.strip():
        raise ValueError(f"Reporting period missing for {obs.indicator_key}")

    if not obs.source or not obs.source.strip():
        raise ValueError(f"Source missing for {obs.indicator_key}")


def upsert_macro_observation(db: Session, obs: MacroObservation) -> tuple[MacroIndicator, str]:
    """
    Idempotent upsert of a macro observation.
    Composite key: (indicator_key, reporting_period, source)
    Returns (record, "stored" | "updated" | "unchanged").
    """
    validate_macro_observation(obs)

    stmt = select(MacroIndicator).where(
        MacroIndicator.indicator_key == obs.indicator_key,
        MacroIndicator.reporting_period == obs.reporting_period,
        MacroIndicator.source == obs.source,
    )
    existing = db.execute(stmt).scalars().first()

    now = utc_now()
    if existing is None:
        new_record = MacroIndicator(
            indicator_key=obs.indicator_key,
            display_name=obs.display_name,
            value=obs.value,
            unit=obs.unit,
            reporting_period=obs.reporting_period,
            source=obs.source,
            source_url=obs.source_url,
            published_at=obs.published_at,
            status=obs.status,
            metadata_json=obs.metadata_json,
            retrieved_at=obs.retrieved_at or now,
            created_at=now,
        )
        db.add(new_record)
        db.commit()
        db.refresh(new_record)
        return new_record, "stored"

    # Check if value or metadata changed (revision)
    val_diff = abs(Decimal(str(existing.value)) - Decimal(str(obs.value))) > Decimal("0.00000001")
    if val_diff:
        # Official revision detected
        meta = existing.metadata_json or {}
        revisions = meta.get("revision_history", [])
        revisions.append({
            "previous_value": float(existing.value),
            "revised_to": float(obs.value),
            "revised_at": now.isoformat(),
        })
        new_meta = {**meta, **(obs.metadata_json or {}), "revision_history": revisions, "revised": True}

        existing.value = obs.value
        existing.status = "revised"
        existing.source_url = obs.source_url or existing.source_url
        existing.published_at = obs.published_at or existing.published_at
        existing.metadata_json = new_meta
        existing.retrieved_at = now
        db.commit()
        db.refresh(existing)
        return existing, "updated"
    else:
        # Unchanged observation; update retrieved_at timestamp
        existing.retrieved_at = now
        if obs.metadata_json and existing.metadata_json != obs.metadata_json:
            existing.metadata_json = {**(existing.metadata_json or {}), **obs.metadata_json}
        db.commit()
        db.refresh(existing)
        return existing, "unchanged"


async def run_macro_refresh(
    db: Session,
    providers: list[MacroDataProvider] | None = None,
) -> MacroRefreshSummary:
    """
    Refresh all macro indicators from official publisher providers with fault isolation.
    """
    active_providers = providers if providers is not None else get_macro_providers()
    total_requested = len(CANONICAL_MACRO_CONFIG)
    stored_count = 0
    updated_count = 0
    unchanged_count = 0
    failed_count = 0
    errors: list[dict[str, str]] = []
    processed_indicators: list[MacroIndicatorResponse] = []

    for provider in active_providers:
        provider_name = provider.provider_name
        try:
            observations = await provider.fetch_latest()
            for obs in observations:
                try:
                    record, outcome = upsert_macro_observation(db, obs)
                    if outcome == "stored":
                        stored_count += 1
                    elif outcome == "updated":
                        updated_count += 1
                    else:
                        unchanged_count += 1

                    freshness = determine_freshness(
                        record.indicator_key,
                        record.reporting_period,
                        record.published_at,
                    )

                    processed_indicators.append(
                        MacroIndicatorResponse(
                            id=record.id,
                            indicator_key=record.indicator_key,
                            display_name=record.display_name,
                            value=float(record.value),
                            unit=record.unit,
                            reporting_period=record.reporting_period,
                            source=record.source,
                            source_url=record.source_url,
                            published_at=record.published_at.isoformat() if record.published_at else None,
                            retrieved_at=record.retrieved_at.isoformat() if record.retrieved_at else None,
                            status=record.status,
                            freshness_status=freshness,
                            metadata_json=record.metadata_json or {},
                        )
                    )
                except Exception as ex:
                    logger.error("Failed to persist observation %s: %s", obs.indicator_key, ex)
                    failed_count += 1
                    errors.append({
                        "indicator": obs.indicator_key,
                        "source": provider_name,
                        "error": str(ex),
                    })
        except Exception as e:
            logger.error("Macro provider %s failed during fetch: %s", provider_name, e)
            failed_count += 1
            errors.append({
                "provider": provider_name,
                "error": str(e),
            })

    return MacroRefreshSummary(
        requested=total_requested,
        stored=stored_count,
        updated=updated_count,
        unchanged=unchanged_count,
        failed=failed_count,
        indicators=processed_indicators,
        errors=errors,
    )


def get_latest_macro_indicators(db: Session) -> list[MacroIndicatorResponse]:
    """
    Retrieve the latest verified period for each of the six canonical indicators.
    Returns honest unavailable state if an indicator is not yet stored.
    """
    results: list[MacroIndicatorResponse] = []

    for key, config in CANONICAL_MACRO_CONFIG.items():
        stmt = (
            select(MacroIndicator)
            .where(MacroIndicator.indicator_key == key)
            .order_by(MacroIndicator.id.desc())
            .limit(1)
        )
        record = db.execute(stmt).scalars().first()

        if record is not None:
            freshness = determine_freshness(
                record.indicator_key,
                record.reporting_period,
                record.published_at,
            )
            results.append(
                MacroIndicatorResponse(
                    id=record.id,
                    indicator_key=record.indicator_key,
                    display_name=record.display_name,
                    value=float(record.value),
                    unit=record.unit,
                    reporting_period=record.reporting_period,
                    source=record.source,
                    source_url=record.source_url,
                    published_at=record.published_at.isoformat() if record.published_at else None,
                    retrieved_at=record.retrieved_at.isoformat() if record.retrieved_at else None,
                    status=record.status,
                    freshness_status=freshness,
                    metadata_json=record.metadata_json or {},
                )
            )
        else:
            # Unavailable in database
            results.append(
                MacroIndicatorResponse(
                    id=None,
                    indicator_key=key,
                    display_name=config["display_name"],
                    value=None,
                    unit=config["unit"],
                    reporting_period="Unavailable",
                    source=config["expected_source"],
                    source_url=None,
                    published_at=None,
                    retrieved_at=None,
                    status="unavailable",
                    freshness_status="unavailable",
                    metadata_json={},
                )
            )

    return results


def get_macro_history(db: Session, indicator_key: str, limit: int = 50) -> list[MacroIndicatorResponse]:
    """Retrieve historical observations for a specific macro indicator."""
    if indicator_key not in CANONICAL_MACRO_CONFIG:
        raise ValueError(f"Unknown indicator key '{indicator_key}'")

    stmt = (
        select(MacroIndicator)
        .where(MacroIndicator.indicator_key == indicator_key)
        .order_by(MacroIndicator.id.desc())
        .limit(limit)
    )
    records = db.execute(stmt).scalars().all()

    results: list[MacroIndicatorResponse] = []
    for r in records:
        freshness = determine_freshness(r.indicator_key, r.reporting_period, r.published_at)
        results.append(
            MacroIndicatorResponse(
                id=r.id,
                indicator_key=r.indicator_key,
                display_name=r.display_name,
                value=float(r.value),
                unit=r.unit,
                reporting_period=r.reporting_period,
                source=r.source,
                source_url=r.source_url,
                published_at=r.published_at.isoformat() if r.published_at else None,
                retrieved_at=r.retrieved_at.isoformat() if r.retrieved_at else None,
                status=r.status,
                freshness_status=freshness,
                metadata_json=r.metadata_json or {},
            )
        )
    return results
