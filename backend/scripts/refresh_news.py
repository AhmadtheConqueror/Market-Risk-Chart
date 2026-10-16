"""Dormant news job. Default is plan-only; --run requires operator approval."""
from __future__ import annotations
import argparse
import asyncio
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Collect approved existing sources once")
    args = parser.parse_args(argv)
    if not args.run:
        print(json.dumps({"enabled": False, "message": "Plan only. No requests or database access. No hosting job is installed."}))
        return 0
    from fastapi import HTTPException
    from app.db.session import get_session_factory
    from app.services.news_ingestion import refresh_news
    try:
        with get_session_factory()() as db:
            summary = asyncio.run(refresh_news(db))
        print(json.dumps({"sources_requested": summary.sources_requested,
            "sources_succeeded": summary.sources_succeeded, "failed": summary.failed,
            "stored": summary.stored, "updated": summary.updated, "unchanged": summary.unchanged}))
        return 1 if summary.sources_succeeded == 0 else 0
    except HTTPException as exc:
        if exc.status_code == 409:
            print(json.dumps({"skipped": True, "reason": "Refresh already in progress"}))
            return 0
        raise
    except Exception as exc:
        # Never emit credentials or arbitrary driver errors into scheduler logs.
        print(json.dumps({"failed": True, "error_type": type(exc).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
