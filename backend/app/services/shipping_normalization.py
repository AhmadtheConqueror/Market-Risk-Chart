"""Pure AIS normalization; no receipt-to-transmission timestamp inference."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import re

BOX = [[3.5, 1.5], [6.7, 8.5]]
SUBREGIONS = {"lagos": [[5.9, 3.0], [6.65, 3.7]], "niger_delta": [[4.2, 6.5], [5.1, 7.6]]}
TYPES = ["PositionReport", "ShipStaticData", "StandardClassBPositionReport", "StaticDataReport", "ExtendedClassBPositionReport"]
POSITION_TYPES = {"PositionReport", "StandardClassBPositionReport", "ExtendedClassBPositionReport"}


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def num(value, low, high):
    return float(value) if type(value) in (int,float) and math.isfinite(value) and low<=value<high else None


def clean(value, key=""):
    if not isinstance(value,str): return None
    if key: value=value.replace(key,"[redacted]")
    value=re.sub(r"[\x00-\x1f\x7f]", " ", value).strip(" @")[:120]
    return value if value.upper() not in {"","UNKNOWN","NONE","N/A","NA","NOT AVAILABLE","-","0"} else None


def provider_time(value):
    if not isinstance(value,str): return None
    try: return utc(datetime.fromisoformat(value.removesuffix(" UTC").replace("Z","+00:00")))
    except ValueError: return None


def valid_imo(value):
    s=str(value)
    return value if type(value) is int and len(s)==7 and value>0 and sum(int(s[i])*(7-i) for i in range(6))%10==int(s[6]) else None


def valid_eta(value):
    if not isinstance(value,dict): return None
    parts=[value.get(k) for k in ["Month","Day","Hour","Minute"]]
    if not all(type(v) is int for v in parts): return None
    try: datetime(2024,*parts)
    except ValueError: return None
    return dict(zip(["Month","Day","Hour","Minute"],parts))


def classify(latitude,longitude):
    for region,box in SUBREGIONS.items():
        if box[0][0]<=latitude<=box[1][0] and box[0][1]<=longitude<=box[1][1]: return region
    return "gulf_of_guinea" if BOX[0][0]<=latitude<=BOX[1][0] and BOX[0][1]<=longitude<=BOX[1][1] else "outside_pilot"


def normalize(data, received_at, key=""):
    if not isinstance(data,dict) or data.get("MessageType") not in TYPES: return None
    kind=data["MessageType"];metadata=data.get("MetaData") or {};report=(data.get("Message") or {}).get(kind) or {}
    if not isinstance(report,dict) or not isinstance(metadata,dict) or report.get("Valid") is False: return None
    mmsi=str(report.get("UserID") or metadata.get("MMSI") or "")
    if not re.fullmatch(r"[1-9][0-9]{8}",mmsi): return None
    if metadata.get("MMSI") and str(metadata["MMSI"])!=mmsi: return None
    received_at=utc(received_at)
    identity={}
    name=clean(metadata.get("ShipName"),key)
    if name: identity["vessel_name"]=name
    static=False;position=None
    if kind in POSITION_TYPES:
        latitude=num(report.get("Latitude"),-90,90.000001);longitude=num(report.get("Longitude"),-180,180.000001)
        if latitude is not None and longitude is not None:
            position={"mmsi":mmsi,"received_at":received_at,"provider_timestamp":provider_time(metadata.get("time_utc")),
                "ais_utc_second":int(report["Timestamp"]) if num(report.get("Timestamp"),0,60) is not None else None,
                "latitude":latitude,"longitude":longitude,"sog":num(report.get("Sog"),0,102.3),
                "cog":num(report.get("Cog"),0,360),"heading":num(report.get("TrueHeading"),0,360),
                "navigation_status":int(report["NavigationalStatus"]) if num(report.get("NavigationalStatus"),0,15) is not None else None,
                "region":classify(latitude,longitude),"source":"aisstream","raw_message_type":kind}
            stamp=position["provider_timestamp"] or received_at.replace(microsecond=0)
            fingerprint={k:v for k,v in position.items() if k not in {"received_at","provider_timestamp"}}
            fingerprint["identity_timestamp"]=stamp.isoformat()
            position["dedupe_key"]=sha256(json.dumps(fingerprint,sort_keys=True).encode()).hexdigest()
        if kind=="ExtendedClassBPositionReport":
            identity.update(vessel_name=clean(report.get("Name"),key) or name,vessel_type_code=num(report.get("Type"),20,100))
            static=True
    elif kind=="ShipStaticData":
        identity.update(vessel_name=clean(report.get("Name"),key) or name,imo=valid_imo(report.get("ImoNumber")),
            callsign=clean(report.get("CallSign"),key),vessel_type_code=num(report.get("Type"),20,100),
            destination=clean(report.get("Destination"),key),eta_raw=valid_eta(report.get("Eta")),
            draught=num(report.get("MaximumStaticDraught"),0.000001,25.500001))
        static=True
    elif kind=="StaticDataReport":
        part_a=report.get("ReportA") or {};part_b=report.get("ReportB") or {}
        if part_a.get("Valid") is True: identity["vessel_name"]=clean(part_a.get("Name"),key) or name;static=True
        if part_b.get("Valid") is True:
            identity.update(callsign=clean(part_b.get("CallSign"),key),vessel_type_code=num(part_b.get("ShipType"),20,100));static=True
    return {"mmsi":mmsi,"received_at":received_at,"identity":identity,"static":static,"position":position}
