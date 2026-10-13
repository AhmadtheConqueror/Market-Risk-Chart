"""Three-area static/voyage and position audit; all correlations stay in memory."""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import random
import re
import time

from dotenv import load_dotenv
from websockets.asyncio.client import connect
from test_aisstream import URL, number, observed_time, safe_text

AREAS = {
    "lagos": [[5.9, 3.0], [6.65, 3.7]],
    "delta": [[4.2, 6.5], [5.1, 7.6]],
    "gulf": [[3.5, 1.5], [6.7, 8.5]],
}
TYPES = ["PositionReport", "ShipStaticData", "StaticDataReport",
         "StandardClassBPositionReport", "ExtendedClassBPositionReport"]
POSITION_TYPES = {"PositionReport", "StandardClassBPositionReport", "ExtendedClassBPositionReport"}
FIELDS = ["name", "imo", "callsign", "type_code", "latitude", "longitude", "sog", "cog",
          "heading", "navigation_status", "destination", "eta", "draught", "ais_second",
          "position_envelope_time", "static_envelope_time"]


def clean(value, key):
    text = safe_text(value, key).strip(" @")
    return text if text.upper() not in {"", "UNKNOWN", "N/A", "NONE", "NA", "NOT AVAILABLE", "0", "-"} else None


def imo(value):
    if not isinstance(value, int) or isinstance(value, bool):
        return None
    digits = str(value)
    if len(digits) != 7 or value == 0:
        return None
    return value if sum(int(digits[i])*(7-i) for i in range(6)) % 10 == int(digits[6]) else None


def eta(value):
    if not isinstance(value, dict):
        return None
    month, day, hour, minute = [value.get(k) for k in ["Month", "Day", "Hour", "Minute"]]
    if not all(type(v) is int for v in [month, day, hour, minute]):
        return None
    try:
        datetime(2024,month,day,hour,minute)
    except ValueError:
        return None
    return f"{month:02}-{day:02} {hour:02}:{minute:02} (year unspecified)"


def merge(record, message_type, report, metadata, receipt, key, invalid):
    # Feed metadata may contain cached identity/coordinates; only name is taken from it.
    values = {"name": clean(metadata.get("ShipName"),key)}
    if report.get("Valid") is False:
        invalid["invalid_decoded_message"] += 1
        return
    envelope_time = observed_time(metadata.get("time_utc"))
    if message_type in POSITION_TYPES:
        latitude = number(report.get("Latitude"), -90,90.000001)
        longitude = number(report.get("Longitude"), -180,180.000001)
        if latitude is not None and longitude is not None:
            values.update(latitude=latitude,longitude=longitude,position_receipt_time=receipt.isoformat(),
                position_envelope_time=envelope_time.isoformat() if envelope_time else None)
        values.update(sog=number(report.get("Sog"),0,102.3),cog=number(report.get("Cog"),0,360),
            heading=number(report.get("TrueHeading"),0,360),ais_second=number(report.get("Timestamp"),0,60))
        if message_type == "PositionReport":
            values["navigation_status"] = number(report.get("NavigationalStatus"),0,15)
        if message_type == "ExtendedClassBPositionReport":
            values.update(name=clean(report.get("Name"),key) or values["name"],type_code=number(report.get("Type"),20,100))
    else:
        values.update(static_receipt_time=receipt.isoformat(),static_envelope_time=envelope_time.isoformat() if envelope_time else None)
        if message_type == "ShipStaticData":
            values.update(name=clean(report.get("Name"),key) or values["name"],imo=imo(report.get("ImoNumber")),
                callsign=clean(report.get("CallSign"),key),type_code=number(report.get("Type"),20,100),
                destination=clean(report.get("Destination"),key),eta=eta(report.get("Eta")),
                draught=number(report.get("MaximumStaticDraught"),0.000001,25.500001))
        elif message_type == "StaticDataReport":
            part_a=report.get("ReportA") or {}; part_b=report.get("ReportB") or {}
            if part_a.get("Valid") is True:
                values["name"]=clean(part_a.get("Name"),key) or values["name"]
            if part_b.get("Valid") is True:
                values.update(callsign=clean(part_b.get("CallSign"),key),type_code=number(part_b.get("ShipType"),20,100))
    for field,value in values.items():
        if value is not None:
            record[field]=value
        elif field in FIELDS:
            invalid[field] += 1
    record["receipt_time"]=receipt.isoformat()
    record.setdefault("message_types",set()).add(message_type)


async def run_area(area, seconds, key):
    start=time.monotonic();deadline=start+seconds
    counts=Counter();invalid=Counter();records={};errors=[];metadata_ages=[];positions_ages=[];types=Counter()
    accepted=False;compressed=False;attempts=0;rejected=False
    print(f"START {area}; box={AREAS[area]}; maximum={seconds}s",flush=True)
    next_progress=start+45
    while time.monotonic()<deadline and attempts<4 and not rejected:
        attempts+=1
        try:
            async with asyncio.timeout(deadline-time.monotonic()):
                async with connect(URL,compression="deflate",open_timeout=12,close_timeout=1,ping_interval=20,
                    ping_timeout=20,max_queue=32,max_size=1024*1024,logger=logging.getLogger("websockets")) as socket:
                    await socket.send(json.dumps({"APIKey":key,"BoundingBoxes":[AREAS[area]],"FilterMessageTypes":TYPES}))
                    async for frame in socket:
                        if isinstance(frame,bytes): counts["binary_frames"]+=1
                        try:
                            data=json.loads(frame.decode("utf-8") if isinstance(frame,bytes) else frame)
                        except (UnicodeError,json.JSONDecodeError):
                            counts["malformed"]+=1;continue
                        if not isinstance(data,dict): counts["malformed"]+=1;continue
                        if data.get("error") or data.get("Error"):
                            errors.append("Provider/subscription error (payload withheld)");rejected=True;break
                        kind=data.get("MessageType")
                        if kind=="SubscriptionConfirmation":
                            accepted=True
                            confirmation=data.get("Message") or {}
                            confirmation=confirmation.get("SubscriptionConfirmation",confirmation)
                            compressed=bool(confirmation.get("CompressionEnabled"))
                            print(f"AUTH {area}: accepted; compression={compressed}",flush=True);continue
                        if kind not in TYPES: counts["other"]+=1;continue
                        accepted=True;counts["messages"]+=1;types[kind]+=1
                        counts["position" if kind in POSITION_TYPES else "static"]+=1
                        metadata=data.get("MetaData") or {};report=(data.get("Message") or {}).get(kind) or {}
                        mmsi=str(metadata.get("MMSI") or report.get("UserID") or "")
                        if not re.fullmatch(r"[0-9]{9}",mmsi): counts["invalid_mmsi"]+=1;continue
                        receipt=datetime.now(timezone.utc);stamp=observed_time(metadata.get("time_utc"))
                        if stamp:
                            age=(receipt-stamp).total_seconds();metadata_ages.append(age)
                            if kind in POSITION_TYPES: positions_ages.append(age)
                        record=records.setdefault(mmsi,{"mmsi":mmsi})
                        merge(record,kind,report,metadata,receipt,key,invalid)
                        if time.monotonic()>=next_progress:
                            print(f"PROGRESS {area}: messages={counts['messages']}; vessels={len(records)}; static={counts['static']}",flush=True)
                            next_progress=time.monotonic()+45
        except TimeoutError:
            if time.monotonic()<deadline-0.1: errors.append("Connection/read timeout")
            else: break
        except Exception as exc:
            code=getattr(getattr(exc,"rcvd",None),"code",None)
            errors.append(type(exc).__name__+(f" (close code {code})" if isinstance(code,int) else ""))
        if time.monotonic()<deadline and not rejected:
            await asyncio.sleep(min(2**(attempts-1)+random.uniform(0,0.25),max(0,deadline-time.monotonic())))
    elapsed=time.monotonic()-start
    available={field:sum(r.get(field) is not None for r in records.values()) for field in FIELDS}
    joined=sum("position_receipt_time" in r and "static_receipt_time" in r for r in records.values())
    summary={"area":area,"box":AREAS[area],"runtime_seconds":round(elapsed,2),"authenticated":accepted,
        "compression":compressed,"total_messages":counts["messages"],"unique_mmsis":len(records),
        "named_vessels":available["name"],"position_messages":counts["position"],"static_voyage_messages":counts["static"],
        "message_types":dict(types),"joined_position_static_vessels":joined,"field_availability":available,
        "availability_percent":{f:round(n/len(records)*100,1) if records else None for f,n in available.items()},
        "unavailable_field_events":dict(invalid),"attempts":attempts,"reconnects":attempts-1,"errors":errors,
        "binary_frames":counts["binary_frames"],"malformed":counts["malformed"],
        "metadata_age_seconds": [round(min(metadata_ages),3),round(max(metadata_ages),3)] if metadata_ages else None,
        "position_metadata_age_seconds": [round(min(positions_ages),3),round(max(positions_ages),3)] if positions_ages else None}
    print("SUMMARY "+json.dumps(summary),flush=True)
    # Prefer informative joined records; no records or frames are written to files.
    selected=sorted(records.values(),key=lambda r:sum(r.get(f) is not None for f in FIELDS),reverse=True)[:8]
    for record in selected:
        printable={k:v for k,v in record.items() if k!="message_types"}
        printable["message_types"]=sorted(record.get("message_types",[]))
        print("VESSEL "+json.dumps(printable,ensure_ascii=True),flush=True)
    print(f"END {area}; in-memory records discarded; no persistence",flush=True)
    return accepted


async def main(areas,seconds):
    load_dotenv(Path(__file__).resolve().parents[1]/".env",override=False)
    key=os.environ.get("AISSTREAM_API_KEY","").strip()
    if not key:
        print("AISSTREAM_API_KEY is not configured; no connection attempted.");return 2
    logging.getLogger("websockets").disabled=True
    successful=True
    for area in areas:
        successful=await run_area(area,seconds,key) and successful
    return 0 if successful else 1


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--area",choices=[*AREAS,"all"],default="all")
    parser.add_argument("--seconds",type=int,choices=range(180,301),default=180)
    args=parser.parse_args()
    raise SystemExit(asyncio.run(main(list(AREAS) if args.area=="all" else [args.area],args.seconds)))
