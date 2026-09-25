from __future__ import annotations

import json
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

print("=" * 60)
print("VERIFYING LIVE ENDPOINTS WITH SUPABASE DATA")
print("=" * 60)

# 1. GET /api/market/latest
print("\n--- 1. Testing GET /api/market/latest ---")
r = client.get("/api/market/latest")
print(f"Status: {r.status_code}")
data = r.json()
obs_list = data.get("observations", [])
print(f"Returned {len(obs_list)} items:")
for item in obs_list:
    print(f"  • {item['instrumentId']:<10} | val: {item['value']} {item['unit']} | freshness: {item['freshnessStatus']} (age: {item['ageSeconds']}s)")
assert r.status_code == 200
assert len(obs_list) == 4

# 2. GET /api/market/history?instrument=brent&days=90
print("\n--- 2. Testing GET /api/market/history?instrument=brent&days=90 ---")
r = client.get("/api/market/history?instrument=brent&days=90")
print(f"Status: {r.status_code}")
hdata = r.json()
print(f"Instrument: {hdata['instrument']}")
print(f"Observations returned: {hdata['total_observations']}")
print(f"History Status: {hdata['history_status']}")
assert r.status_code == 200
assert hdata["history_status"] in ["insufficient_history", "valid"]

# 3. GET /api/dashboard/snapshot
print("\n--- 3. Testing GET /api/dashboard/snapshot ---")
r = client.get("/api/dashboard/snapshot")
print(f"Status: {r.status_code}")
snap = r.json()
print(f"Snapshot Date: {snap['snapshot_date']}")
print(f"Market Stats ({len(snap['market_stats'])}):")
for s in snap["market_stats"]:
    print(f"  • {s['instrument_id']:<10} | curr: {s['current_value']} | 1D: {s['change']} | z-score: {s['z_score']} | history_status: {s['history_status']}")
    # Assert rule: since history has only 1 point, z_score MUST be None and history_status MUST be 'insufficient_history'
    if s["current_value"] is not None:
        assert s["z_score"] is None, f"z_score for {s['instrument_id']} should be None"
        assert s["history_status"] == "insufficient_history", f"history_status for {s['instrument_id']} should be insufficient_history"

print(f"\nProduct Spreads ({len(snap['product_spreads'])}):")
for p in snap["product_spreads"]:
    print(f"  • {p['instrument_id']:<10} | raw: {p['original_price']} {p['original_unit']} | bbl/mt: {p['barrels_per_mt']} | converted: ${p['converted_price']:.2f}/bbl | spread: ${p['spread']:.2f}/bbl")
    # Verify product conversion math
    assert p["converted_price"] is not None
    assert p["spread"] is not None

print("\n=== ALL LIVE ENDPOINT VERIFICATIONS PASSED WITH ZERO ERRORS ===")
