from __future__ import annotations

import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

print("--- 1. Testing GET /api/health ---")
r = client.get("/api/health")
print("Status:", r.status_code)
print("Payload:", r.json())
assert r.status_code == 200
assert r.json()["database"] == "connected"

print("\n--- 2. Testing GET /api/market/instruments ---")
r = client.get("/api/market/instruments")
print("Status:", r.status_code)
insts = r.json()
print("Count:", len(insts))
for inst in insts:
    print(f"  • {inst['instrument_key']}: {inst['display_name']} ({inst['unit']})")
assert r.status_code == 200
assert len(insts) == 7

print("\n--- 3. Testing GET /api/market/latest ---")
r = client.get("/api/market/latest")
print("Status:", r.status_code)
print("Payload:", r.json())
assert r.status_code == 200

print("\n--- 4. Testing GET /api/market/history?instrument=brent&days=90 ---")
r = client.get("/api/market/history?instrument=brent&days=90")
print("Status:", r.status_code)
print("Payload:", r.json())
assert r.status_code == 200

print("\n--- 5. Testing GET /api/dashboard/snapshot ---")
r = client.get("/api/dashboard/snapshot")
print("Status:", r.status_code)
snap = r.json()
print("Snapshot Date:", snap.get("snapshot_date"))
print("Market stats count:", len(snap.get("market_stats", [])))
print("Product spreads count:", len(snap.get("product_spreads", [])))
print("Macro indicators count:", len(snap.get("macro_indicators", [])))
print("Risk register count:", len(snap.get("risk_register", [])))
assert r.status_code == 200

print("\n--- 6. Testing POST /api/ai/analyse ---")
r = client.post("/api/ai/analyse", json={"context": {}})
print("Status:", r.status_code)
print("Payload:", r.json())
assert r.status_code == 200
assert r.json()["status"] == "unconfigured"
assert r.json()["configured"] is False

print("\n--- 7. Testing POST /api/ai/chat ---")
r = client.post("/api/ai/chat", json={"message": "What is the Brent risk?", "context": {}})
print("Status:", r.status_code)
print("Payload:", r.json())
assert r.status_code == 200
assert r.json()["status"] == "unconfigured"
assert r.json()["configured"] is False

print("\n=== ALL LIVE SUPABASE ENDPOINT VERIFICATIONS PASSED SUCCESSFULLY ===")
