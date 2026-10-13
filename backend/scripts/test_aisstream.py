"""Bounded server-side AISStream diagnostic. No database or raw-frame persistence."""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import json
import logging
import math
import os
from pathlib import Path
import random
import re
import time

from dotenv import load_dotenv
from websockets.asyncio.client import connect

URL = "wss://stream.aisstream.io/v0/stream"
AREAS = {
    "lagos": [[5.9, 3.0], [6.65, 3.7]],
    "gulf": [[3.5, 1.5], [6.7, 8.5]],
}
NAVIGATION = {0: "Under way (engine)", 1: "At anchor", 2: "Not under command",
    3: "Restricted manoeuvrability", 4: "Constrained draught", 5: "Moored",
    6: "Aground", 7: "Fishing", 8: "Under way (sailing)", 15: "Not available"}


def number(value, lower, upper):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) and lower <= value < upper else None


def observed_time(value):
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.strip().removesuffix(" UTC").replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else result.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def safe_text(value, key):
    # Sanitize even vessel names: no control sequences, table separators or credentials.
    return re.sub(r"[\x00-\x1f\x7f|]", " ", str(value or "").replace(key, "[REDACTED]")).strip()[:60]


async def diagnose(area):
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    key = os.environ.get("AISSTREAM_API_KEY", "").strip()
    if not key:
        print("AISSTREAM_API_KEY is not configured; no connection attempted.")
        return 2
    # Never enable frame logging: subscriptions contain credentials.
    logging.getLogger("websockets").disabled = True
    start = time.monotonic()
    deadline = start + 60
    counts = Counter()
    vessels = set()
    timestamps = []
    ages = []
    field_counts = Counter()
    errors = []
    auth = False
    compression = False
    attempts = 0
    rejected = False
    binary = 0
    print(f"Area: {area}; latitude/longitude bounding box: {AREAS[area]}")
    print("Limit: 30 distinct MMSIs or 60 seconds total; one connection at a time")
    print("Time (UTC) | Vessel | MMSI | Lat | Lon | SOG (kn) | COG (deg) | Nav Status", flush=True)
    while time.monotonic() < deadline and len(vessels) < 30 and attempts < 3 and not rejected:
        attempts += 1
        try:
            remaining = deadline - time.monotonic()
            async with asyncio.timeout(remaining):
                async with connect(URL, compression="deflate", open_timeout=min(12, remaining),
                    ping_interval=20, ping_timeout=15, close_timeout=1, max_queue=32,
                    max_size=1024*1024, logger=logging.getLogger("websockets")) as socket:
                    # Send the complete subscription immediately, well within three seconds.
                    await socket.send(json.dumps({"APIKey": key, "BoundingBoxes": [AREAS[area]],
                        "FilterMessageTypes": ["PositionReport"]}))
                    async for frame in socket:
                        if isinstance(frame, bytes):
                            binary += 1
                            frame = frame.decode("utf-8")
                        try:
                            message = json.loads(frame)
                        except (json.JSONDecodeError, UnicodeError):
                            counts["malformed"] += 1
                            continue
                        if not isinstance(message, dict):
                            counts["malformed"] += 1
                            continue
                        if message.get("error") or message.get("Error"):
                            # Do not echo provider error text or raw payloads.
                            errors.append("Subscription/provider error received (payload withheld)")
                            rejected = True
                            break
                        message_type = message.get("MessageType")
                        if message_type == "SubscriptionConfirmation":
                            auth = True
                            confirmation = message.get("Message", {})
                            confirmation = confirmation.get("SubscriptionConfirmation", confirmation)
                            compression = bool(confirmation.get("CompressionEnabled"))
                            continue
                        if message_type != "PositionReport":
                            counts["other"] += 1
                            continue
                        auth = True  # Delivery also proves an accepted authenticated subscription.
                        counts["ais"] += 1
                        metadata = message.get("MetaData") or {}
                        report = (message.get("Message") or {}).get("PositionReport") or {}
                        mmsi = str(metadata.get("MMSI") or report.get("UserID") or "")
                        valid_mmsi = bool(re.fullmatch(r"[0-9]{9}", mmsi))
                        name = safe_text(metadata.get("ShipName"), key)
                        named = bool(name and name.upper() not in {"UNKNOWN", "N/A", "NONE"})
                        counts["named"] += int(named)
                        latitude = number(report.get("Latitude", metadata.get("latitude", metadata.get("Latitude"))), -90, 90.00001)
                        longitude = number(report.get("Longitude", metadata.get("longitude", metadata.get("Longitude"))), -180, 180.00001)
                        sog = number(report.get("Sog"), 0, 102.3)
                        cog = number(report.get("Cog"), 0, 360)
                        heading = number(report.get("TrueHeading"), 0, 360)
                        nav = report.get("NavigationalStatus")
                        timestamp = observed_time(metadata.get("time_utc"))
                        received = datetime.now(timezone.utc)
                        if timestamp:
                            timestamps.append(timestamp)
                            ages.append((received - timestamp).total_seconds())
                        fields = {"MMSI": valid_mmsi, "name": named, "position": latitude is not None and longitude is not None,
                            "SOG": sog is not None, "COG": cog is not None, "heading": heading is not None,
                            "nav_status": isinstance(nav, int) and nav != 15, "metadata_timestamp": timestamp is not None,
                            "decoded_valid": report.get("Valid") is True}
                        field_counts.update({field: int(available) for field, available in fields.items()})
                        if valid_mmsi and mmsi not in vessels:
                            vessels.add(mmsi)
                            def fmt(value, digits):
                                return f"{value:.{digits}f}" if value is not None else "—"
                            stamp = timestamp.strftime("%H:%M:%S") if timestamp else received.strftime("%H:%M:%S") + " (received)"
                            status = NAVIGATION.get(nav, f"Code {nav}" if isinstance(nav, int) else "Unavailable")
                            print(f"{stamp} | {name or 'Unavailable'} | {mmsi} | {fmt(latitude,5)} | {fmt(longitude,5)} | {fmt(sog,1)} | {fmt(cog,1)} | {status}", flush=True)
                        if len(vessels) >= 30:
                            break
        except TimeoutError:
            if time.monotonic() < deadline - 0.1:
                errors.append("Connection/read timeout")
            else:
                break
        except Exception as exc:
            # Exception messages may contain remote data; only expose type and numeric close code.
            close = getattr(exc, "rcvd", None)
            code = getattr(close, "code", None)
            errors.append(type(exc).__name__ + (f" (close code {code})" if isinstance(code, int) else ""))
        if len(vessels) < 30 and not rejected and time.monotonic() < deadline:
            delay = min(2 ** (attempts-1) + random.uniform(0, 0.25), max(0, deadline-time.monotonic()))
            await asyncio.sleep(delay)
    elapsed = time.monotonic() - start
    print("\nSanitized summary:")
    print(f"Authentication accepted: {auth}; server-confirmed compression: {compression}")
    print(f"Runtime: {elapsed:.2f}s; AIS messages: {counts['ais']}; distinct MMSIs: {len(vessels)}; named messages: {counts['named']}")
    print(f"Connection attempts: {attempts}; reconnects: {max(0,attempts-1)}; binary frames: {binary}; malformed messages: {counts['malformed']}")
    print("Usable fields by AIS message:", dict(field_counts))
    if timestamps:
        print(f"Oldest metadata UTC: {min(timestamps).isoformat()}; newest: {max(timestamps).isoformat()}")
        print(f"Metadata age at receipt: min {min(ages):.2f}s; max {max(ages):.2f}s")
    else:
        print("No parseable full metadata UTC timestamps received.")
    print("Connection/provider errors:", errors or "none")
    print("Metadata time is feed context, not proof of the vessel's last AIS transmission; AIS Timestamp contains only UTC seconds.")
    print("No raw frames or AIS records were written to disk or a database.")
    return 0 if auth else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--area", choices=AREAS, default="lagos")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(diagnose(args.area)))
