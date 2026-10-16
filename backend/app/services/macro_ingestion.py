from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import logging
import re
from typing import Any

from sqlalchemy import select, func, or_, and_
from sqlalchemy.sql.functions import FunctionElement
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.types import Integer
from sqlalchemy.orm import Session

from app.models.macro import MacroIndicator, utc_now
from app.providers.macro.base import MacroDataProvider, MacroObservation
from app.providers.macro.factory import get_macro_providers
from app.providers.macro.international import SPECS
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

# Existing Nigeria definitions remain unchanged; prefixed keys need no schema migration.
for _key, (_title, _unit, _source, _cycle, _series) in SPECS.items():
    CANONICAL_MACRO_CONFIG[_key] = {
        "display_name": _title, "unit": _unit, "frequency": _cycle,
        "expected_source": _source, "min_val": Decimal("-100"),
        "max_val": Decimal("100000"),
    }

for _key in SPECS:
    _config = CANONICAL_MACRO_CONFIG[_key]
    if _key in {"usa_policy_rate", "usa_unemployment_rate", "china_manufacturing_pmi"}:
        _config.update(min_val=Decimal("0"), max_val=Decimal("100"))
    elif _config["unit"] == "index" or _key == "usa_crude_inventories":
        _config.update(min_val=Decimal("0.00000001"), max_val=Decimal("10000"))
    elif _key == "global_oil_demand_growth":
        _config.update(min_val=Decimal("-50"), max_val=Decimal("50"))
    else:
        _config.update(min_val=Decimal("-50"), max_val=Decimal("500"))


def macro_geography(key: str) -> str:
    return "usa" if key.startswith("usa_") else "global" if key in SPECS else "nigeria"


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


def parse_period_approx_date(period_str: str) -> datetime | None:
    """Approximate the end date of a reporting period for freshness calculation."""
    p = period_str.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p):
        try:
            return datetime.fromisoformat(p).replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    if re.fullmatch(r"\d{4}", p):
        return datetime(int(p), 12, 31, tzinfo=timezone.utc)

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
    now = aware(as_of or datetime.now(timezone.utc))
    frequency = CANONICAL_MACRO_CONFIG.get(indicator_key, {}).get("frequency", "monthly")
    if frequency in {"weo", "outlook"}:
        if published_at is None:
            return "stale"
        window = 220 if frequency == "weo" else 75
        return "fresh" if (now - aware(published_at)).days <= window else "stale"
    period_end = parse_period_approx_date(reporting_period)
    if not period_end:
        return "stale"

    config = CANONICAL_MACRO_CONFIG.get(indicator_key, {})
    frequency = config.get("frequency", "monthly")

    days_elapsed = (now - period_end).total_seconds() / 86400.0

    if frequency in {"daily", "weekly"}:
        return "fresh" if days_elapsed <= (10 if frequency == "daily" else 21) else "stale"
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
    if not val_dec.is_finite():
        raise ValueError("Macro value must be finite")
    if val_dec < config["min_val"] or val_dec > config["max_val"]:
        raise ValueError(
            f"Sanity check failed for {obs.indicator_key}: value {val_dec} out of bounds "
            f"[{config['min_val']}, {config['max_val']}]"
        )

    if not obs.reporting_period or not obs.reporting_period.strip():
        raise ValueError(f"Reporting period missing for {obs.indicator_key}")

    if not obs.source or not obs.source.strip():
        raise ValueError(f"Source missing for {obs.indicator_key}")


def upsert_macro_observation(db: Session, obs: MacroObservation, *, commit: bool = True, records_by_key: dict | None = None) -> tuple[MacroIndicator, str]:
    """
    Idempotent upsert of a macro observation.
    Composite key: (indicator_key, reporting_period, source)
    Returns (record, "stored" | "updated" | "unchanged").
    """
    validate_macro_observation(obs)
    obs.metadata_json = {
        **(obs.metadata_json or {}), "geography": macro_geography(obs.indicator_key),
        "expected_publication_cycle": CANONICAL_MACRO_CONFIG[obs.indicator_key]["frequency"],
    }

    stmt = select(MacroIndicator).where(
        MacroIndicator.indicator_key == obs.indicator_key,
        MacroIndicator.reporting_period == obs.reporting_period,
        MacroIndicator.source == obs.source,
    )
    cache_key = (obs.indicator_key, obs.reporting_period, obs.source)
    existing = records_by_key.get(cache_key) if records_by_key is not None else db.execute(stmt).scalars().first()

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
        if records_by_key is not None:
            records_by_key[cache_key] = new_record
        if commit:
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
        if commit:
            db.commit()
            db.refresh(existing)
        return existing, "updated"
    else:
        # Unchanged observation; update retrieved_at timestamp
        existing.retrieved_at = now
        if obs.metadata_json and existing.metadata_json != obs.metadata_json:
            existing.metadata_json = {**(existing.metadata_json or {}), **obs.metadata_json}
        if commit:
            db.commit()
            db.refresh(existing)
        return existing, "unchanged"


async def run_macro_refresh(
    db: Session,
    providers: list[MacroDataProvider] | None = None,
) -> MacroRefreshSummary:
    """Isolate fetch failures; commit each publisher batch without per-history-row round trips."""
    active = providers if providers is not None else get_macro_providers()
    counts = {"stored": 0, "updated": 0, "unchanged": 0}
    errors = []
    processed = []
    for provider in active:
        try:
            observations = await provider.fetch_latest()
        except Exception as exc:
            logger.warning("Macro provider %s could not be retrieved", provider.provider_name)
            errors.append({"provider": provider.provider_name, "error": str(exc)})
            continue
        valid = []
        for obs in observations:
            try:
                validate_macro_observation(obs)
                valid.append(obs)
            except Exception as exc:
                errors.append({"indicator": obs.indicator_key, "source": provider.provider_name, "error": str(exc)})
        if not valid:
            if not observations:
                errors.append({"provider": provider.provider_name, "error": "Official publication returned no observations"})
            continue
        try:
            keys = {obs.indicator_key for obs in valid}
            records = db.scalars(select(MacroIndicator).where(MacroIndicator.indicator_key.in_(keys))).all()
            cache = {(r.indicator_key, r.reporting_period, r.source): r for r in records}
            outcomes = [upsert_macro_observation(db, obs, commit=False, records_by_key=cache) for obs in valid]
            db.commit()
            for record, outcome in outcomes:
                counts[outcome] += 1
                processed.append(macro_response(record))
        except Exception as exc:
            db.rollback()
            logger.warning("Macro batch %s could not be persisted", provider.provider_name)
            errors.append({"provider": provider.provider_name, "error": str(exc)})
    return MacroRefreshSummary(requested=len(CANONICAL_MACRO_CONFIG), **counts,
        failed=len(errors), indicators=processed, errors=errors)


def macro_response(record) -> MacroIndicatorResponse:
    return MacroIndicatorResponse(
        id=record.id, indicator_key=record.indicator_key, display_name=record.display_name,
        value=float(record.value), unit=record.unit, reporting_period=record.reporting_period,
        source=record.source, source_url=record.source_url,
        published_at=record.published_at.isoformat() if record.published_at else None,
        retrieved_at=record.retrieved_at.isoformat() if record.retrieved_at else None,
        status=record.status,
        freshness_status=determine_freshness(record.indicator_key, record.reporting_period, record.published_at),
        metadata_json=record.metadata_json or {},
    )


class MacroPeriodRank(FunctionElement):
    """Exact chronological key for parse_period_approx_date, evaluated in DB."""
    type = Integer()
    inherit_cache = True


@compiles(MacroPeriodRank, "sqlite")
def _sqlite_period_rank(element, compiler, **kw):
    return "snapshot_period_rank(" + compiler.process(list(element.clauses)[0], **kw) + ")"


@compiles(MacroPeriodRank, "postgresql")
def _postgres_period_rank(element, compiler, **kw):
    p = "regexp_replace(" + compiler.process(list(element.clauses)[0], **kw) + ", '^[[:space:]]+|[[:space:]]+$', '', 'g')"
    year = f"CAST(right({p}, 4) AS integer)"
    iso_year = f"CAST(left({p}, 4) AS integer)"
    month = f"CAST(substr({p}, 6, 2) AS integer)"
    day = f"CAST(right({p}, 2) AS integer)"
    month_name = f"lower(regexp_replace({p}, '[[:space:]]+[0-9]{{4}}$', ''))"
    named_month = "CASE " + month_name + " " + " ".join(
        f"WHEN '{name}' THEN {number}" for name, number in MONTH_MAP.items()) + " ELSE 1 END"
    # Guard make_date before calling it, including invalid ISO leap/month days.
    return f"""(CASE
      WHEN {p} ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}$' THEN
        CASE WHEN {iso_year} BETWEEN 1 AND 9999 AND {month} BETWEEN 1 AND 12 THEN
          CASE WHEN {day} BETWEEN 1 AND extract(day FROM
            (make_date({iso_year}, {month}, 1) + interval '1 month - 1 day'))
          THEN {iso_year}*10000 + {month}*100 + {day} ELSE 10101 END ELSE 10101 END
      WHEN {p} ~ '^[0-9]{{4}}$' THEN CAST({p} AS integer)*10000 + 1231
      WHEN {p} ~ '^[A-Za-z]+[[:space:]]+[0-9]{{4}}$'
        THEN {year}*10000 + ({named_month})*100 + 28
      WHEN {p} ~* '^Q[1-4][[:space:]]+[0-9]{{4}}$'
        THEN {year}*10000 + CAST(substr({p}, 2, 1) AS integer)*300 + 28
      ELSE 10101 END)"""


def get_latest_macro_indicators(db: Session) -> list[MacroIndicatorResponse]:
    """
    Retrieve the latest verified period for each canonical indicator.
    Returns honest unavailable state if an indicator is not yet stored.
    """
    results: list[MacroIndicatorResponse] = []
    # PostgreSQL parses periods in SQL; SQLite registers the same pure parser
    # for fixture parity. No history rows or period dictionary leave the DB.
    if db.get_bind().dialect.name == "sqlite":
        def period_rank_value(period):
            parsed = parse_period_approx_date(period)
            return parsed.year * 10000 + parsed.month * 100 + parsed.day if parsed else 10101
        db.connection().connection.driver_connection.create_function(
            "snapshot_period_rank", 1, period_rank_value, deterministic=True)
    period_rank = MacroPeriodRank(MacroIndicator.reporting_period)
    forecast_keys = [key for key, config in CANONICAL_MACRO_CONFIG.items()
                     if config["frequency"] in {"weo", "outlook"}]
    eligible = or_(MacroIndicator.indicator_key.not_in(forecast_keys), and_(
        MacroIndicator.indicator_key.in_(forecast_keys),
        MacroIndicator.reporting_period == str(datetime.now(timezone.utc).year)))
    ranked = select(MacroIndicator.id, func.row_number().over(
        partition_by=MacroIndicator.indicator_key,
        order_by=(period_rank.desc(),
                  func.coalesce(MacroIndicator.published_at, datetime.min.replace(tzinfo=timezone.utc)).desc(),
                  MacroIndicator.id.desc())).label("position")).where(
        MacroIndicator.indicator_key.in_(CANONICAL_MACRO_CONFIG), eligible).subquery()
    chosen = db.scalars(select(MacroIndicator).join(ranked,
        MacroIndicator.id == ranked.c.id).where(ranked.c.position == 1)).all()
    records = {record.indicator_key: record for record in chosen}
    for key, config in CANONICAL_MACRO_CONFIG.items():
        record = records.get(key)

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
                    metadata_json={"geography": macro_geography(key),
                                   "expected_publication_cycle": config["frequency"]},
                )
            )

    return results


def get_macro_history(db: Session, indicator_key: str, limit: int = 50) -> list[MacroIndicatorResponse]:
    """Retrieve historical observations for a specific macro indicator."""
    if indicator_key not in CANONICAL_MACRO_CONFIG:
        raise ValueError(f"Unknown indicator key '{indicator_key}'")

    periods = db.execute(select(MacroIndicator.id, MacroIndicator.reporting_period, MacroIndicator.published_at).where(
        MacroIndicator.indicator_key == indicator_key)).all()
    ids = [row.id for row in sorted(periods, key=period_sort_key, reverse=True)[:limit]]
    records = sorted(db.scalars(select(MacroIndicator).where(MacroIndicator.id.in_(ids))).all(),
                     key=period_sort_key, reverse=True)

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


def period_sort_key(record):
    period = parse_period_approx_date(record.reporting_period)
    return (period or datetime.min.replace(tzinfo=timezone.utc),
            aware(record.published_at) if record.published_at else datetime.min.replace(tzinfo=timezone.utc), record.id)
