import asyncio
import json
from pathlib import Path
import sys
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.providers.news.african_energy_chamber import AfricanEnergyChamberNewsProvider


async def verify():
    print("=" * 70)
    print("CONTROLLED LIVE VERIFICATION: AFRICAN ENERGY CHAMBER")
    print("=" * 70)

    # 1. Direct provider fetch test
    provider = AfricanEnergyChamberNewsProvider()
    print(f"Fetching from official source: {provider.NEWS_URL}")
    items = await provider.fetch()

    print(f"\n1. DISCOVERY RESULTS:")
    print(f"   Items discovered: {len(items)}")
    if items:
        newest = max(items, key=lambda x: x.published_at)
        print(f"   Newest publication date: {newest.published_at.isoformat()} ({newest.title[:60]}...)")
        
        region_counts = {}
        topic_counts = {}
        for item in items:
            region_counts[item.region] = region_counts.get(item.region, 0) + 1
            topic_counts[item.topic] = topic_counts.get(item.topic, 0) + 1
        
        print(f"   Regions assigned: {region_counts}")
        print(f"   Topics assigned:  {topic_counts}")
        print("\n   Sample discovered items:")
        for idx, item in enumerate(items[:5], 1):
            print(f"     [{idx}] [{item.region.upper():13}] [{item.topic:15}] {item.published_at.strftime('%Y-%m-%d')}: {item.title[:65]}...")
    else:
        print("   WARNING: No items discovered.")

    # 2. Trigger live refresh via FastAPI server (running on port 8000)
    print("\n2. LIVE POST /api/news/refresh:")
    try:
        req = urllib.request.Request("http://localhost:8000/api/news/refresh", method="POST", data=b"")
        with urllib.request.urlopen(req) as resp:
            refresh_data = json.loads(resp.read().decode())
            print(f"   Status Code: {resp.status}")
            print(f"   Sources Requested: {refresh_data.get('sources_requested')}")
            print(f"   Sources Succeeded: {refresh_data.get('sources_succeeded')}")
            print(f"   Items Found:       {refresh_data.get('items_found')}")
            print(f"   Stored:            {refresh_data.get('stored')}")
            print(f"   Updated:           {refresh_data.get('updated')}")
            print(f"   Unchanged:         {refresh_data.get('unchanged')}")
            print(f"   Failed:            {refresh_data.get('failed')}")
            if refresh_data.get("errors"):
                print(f"   Errors (non-blocking): {refresh_data.get('errors')}")

            aec_source = next((s for s in refresh_data.get("sources", []) if s.get("source_key") == "african_energy_chamber"), None)
            if aec_source:
                print(f"   AEC Source Summary: status={aec_source.get('status')}, found={aec_source.get('items_found')}, stored={aec_source.get('stored')}, updated={aec_source.get('updated')}, unchanged={aec_source.get('unchanged')}")
    except Exception as exc:
        print(f"   Failed to call refresh endpoint: {exc}")

    # 3. Verify GET /api/news/latest?region=africa
    print("\n3. LIVE GET /api/news/latest?region=africa:")
    try:
        url = "http://localhost:8000/api/news/latest?region=africa"
        with urllib.request.urlopen(url) as resp:
            latest_data = json.loads(resp.read().decode())
            items = latest_data.get("items", [])
            print(f"   Status Code: {resp.status}")
            print(f"   Total Africa items returned: {len(items)}")
            aec_africa_items = [it for it in items if it.get("source_key") == "african_energy_chamber"]
            print(f"   AEC Africa items in 7-day window: {len(aec_africa_items)}")
            for idx, it in enumerate(aec_africa_items[:5], 1):
                print(f"     [{idx}] {it.get('published_at')}: {it.get('title')}")
                print(f"         URL: {it.get('url')}")
                print(f"         Topic: {it.get('topic')}")
                print(f"         Snippet: {str(it.get('snippet'))[:80]}...")
    except Exception as exc:
        print(f"   Failed to call latest news endpoint: {exc}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(verify())
