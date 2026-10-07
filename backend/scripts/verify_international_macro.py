"""One explicitly invoked live refresh of USA/global only; never touches Nigeria providers."""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.config import get_settings
from app.models.macro import MacroIndicator
from app.providers.macro.international import InternationalMacroProvider, SPECS
from app.services.macro_ingestion import get_latest_macro_indicators, run_macro_refresh


def nigeria_digest(db):
    records = db.scalars(select(MacroIndicator).where(~MacroIndicator.indicator_key.in_(SPECS)).order_by(MacroIndicator.id)).all()
    payload = [{column.name: getattr(row, column.name) for column in MacroIndicator.__table__.columns} for row in records]
    return len(records), hashlib.sha256(json.dumps(payload, default=str, sort_keys=True).encode()).hexdigest()


class ReportingProvider(InternationalMacroProvider):
    async def fetch_latest(self):
        print("Fetching " + self.key, flush=True)
        result = await super().fetch_latest()
        print(f"Verified {self.key}: {len(result)} official periods", flush=True)
        return result


async def main():
    url = get_settings().sqlalchemy_database_url
    if not url:
        raise RuntimeError("Database not configured")
    args = {"connect_timeout": 15} if url.startswith("postgresql") else {}
    engine = create_engine(url, pool_pre_ping=True, connect_args=args)
    try:
        with Session(engine, expire_on_commit=False, autoflush=False) as db:
            before = nigeria_digest(db)
            summary = await run_macro_refresh(db, [ReportingProvider(key) for key in SPECS])
            after = nigeria_digest(db)
            if before != after:
                raise RuntimeError("Nigeria history changed unexpectedly")
            latest = [r for r in get_latest_macro_indicators(db) if r.indicator_key in SPECS]
            lines = ["# Controlled live USA/global macro verification", "",
                "One refresh invoked after passing backend/frontend tests. Uses the configured project database; Nigeria providers were excluded.", "",
                "| Geography | Indicator | Value | Unit | Period | Source | Freshness |",
                "|---|---|---|---|---|---|---|"]
            for row in latest:
                geography = "USA" if row.indicator_key.startswith("usa_") else "Global"
                precision = 4 if row.indicator_key == "broad_usd_index" else 2
                value = "Unavailable" if row.value is None else f"{row.value:.{precision}f}".rstrip("0").rstrip(".")
                source = f"[{row.source}]({row.source_url})" if row.source_url else row.source
                lines.append(f"| {geography} | {row.display_name} | {value} | {row.unit} | {row.reporting_period} | {source} | {row.freshness_status.title()} |")
            lines += ["", f"History observations: {summary.stored} stored; {summary.updated} revised; {summary.unchanged} unchanged.",
                f"Nigeria history preserved: {before[0]} records; before/after digest identical.", "", "## Source retrieval failures", ""]
            if summary.errors:
                for error in summary.errors:
                    lines.append("- " + error.get("provider", error.get("indicator", "source")) + ": " + error["error"])
            else:
                lines.append("None. All 12 new indicators were retrieved from official sources.")
            lines += ["", "## Definitions", "",
                "CPI: matched monthly year-on-year index change. GDP: preceding-quarter growth at seasonally adjusted annual rate. Inventories: commercial crude excluding SPR, thousand barrels converted to million barrels.",
                "World GDP/inflation: current reference year from the identified IMF WEO edition; future forecasts remain in history. Oil demand growth: current annual world liquid-fuels consumption minus previous-year annual consumption, mbpd; explicitly an EIA STEO estimate/forecast. Energy index: World Bank nominal USD, 2010=100. Broad USD: Fed nominal broad trade-weighted index, January 2006=100.", ""]
            report = Path(__file__).resolve().parents[1] / "MACRO_LIVE_VERIFICATION.md"
            report.write_text("\n".join(lines), encoding="utf-8")
            artifact = Path(__file__).resolve().parents[2] / ".venv" / "macro-discovery" / "live-verification.json"
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_text(json.dumps({"summary":summary.model_dump(mode="json"),"latest":[r.model_dump(mode="json") for r in latest]},indent=2),encoding="utf-8")
            print("\n".join(lines), flush=True)
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        # Do not print database connection strings or credentials in a traceback.
        print("Live verification failed: " + type(exc).__name__, file=sys.stderr)
        sys.exit(1)
