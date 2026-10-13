from datetime import datetime, timedelta, timezone
from sqlalchemy import select, delete, func
from sqlalchemy.orm import Session
from app.config import get_settings
from app.models.shipping import ShippingVessel as Vessel, ShippingPosition as Position, ShippingWatchlist as Watch, ShippingEvent as Event, ShippingCollectorState as State
from app.services.shipping_normalization import utc

LABELS={"watched_vessel_seen":"Watched vessel observed","no_recent_observation":"No recent AIS observation",
    "stationary_observation":"Stationary observation","reported_anchor":"Reported at anchor",
    "reported_moored":"Reported moored","reported_not_under_command":"Reported not under command"}
REGIONS={"niger_delta":"Niger Delta","lagos":"Lagos","gulf_of_guinea":"Wider Gulf of Guinea"}


def now(): return datetime.now(timezone.utc)


def age(timestamp,at=None): return max(0,(utc(at or now())-utc(timestamp)).total_seconds()) if timestamp else None


def latest_positions(db):
    # One latest stored position per MMSI, regardless of message count.
    ranked=select(Position.id,func.row_number().over(partition_by=Position.mmsi,order_by=(Position.received_at.desc(),Position.id.desc())).label("rn")).subquery()
    return {p.mmsi:p for p in db.scalars(select(Position).join(ranked,Position.id==ranked.c.id).where(ranked.c.rn==1)).all()}


def event(db,mmsi,kind,at,evidence,region,value=None,threshold=None,severity="info"):
    row=db.scalar(select(Event).where(Event.mmsi==mmsi,Event.event_type==kind))
    if row is None:
        row=Event(mmsi=mmsi,event_type=kind,severity=severity,observed_at=at,evidence=evidence,region=region)
        db.add(row)
    row.active=True;row.observed_at=at;row.evidence=evidence;row.region=region
    row.observed_value=value;row.threshold=threshold;row.severity=severity;row.updated_at=at
    return row


def resolve(db,mmsi,kinds,at):
    for row in db.scalars(select(Event).where(Event.mmsi==mmsi,Event.event_type.in_(kinds),Event.active.is_(True))):
        row.active=False;row.updated_at=at


def apply_position_rules(db,p,at=None):
    at=utc(at or p.received_at);settings=get_settings()
    evidence={"mmsi":p.mmsi,"latitude":p.latitude,"longitude":p.longitude,"received_at":utc(p.received_at).isoformat(),
        "region":p.region,"source":"AIS-reported position/navigation status"}
    watch=db.scalar(select(Watch).where(Watch.mmsi==p.mmsi,Watch.active.is_(True)))
    if watch: event(db,p.mmsi,"watched_vessel_seen",at,evidence,p.region)
    resolve(db,p.mmsi,["no_recent_observation"],at)
    if p.sog is not None and p.sog<=settings.shipping_stationary_knots:
        event(db,p.mmsi,"stationary_observation",at,evidence,p.region,p.sog,settings.shipping_stationary_knots)
    else: resolve(db,p.mmsi,["stationary_observation"],at)
    statuses={1:"reported_anchor",5:"reported_moored",2:"reported_not_under_command"}
    kind=statuses.get(p.navigation_status)
    resolve(db,p.mmsi,[k for k in statuses.values() if k!=kind],at)
    if kind: event(db,p.mmsi,kind,at,evidence,p.region,p.navigation_status)


def sweep_rules(db,at=None):
    at=utc(at or now());settings=get_settings();positions=latest_positions(db)
    watched={w.mmsi for w in db.scalars(select(Watch).where(Watch.active.is_(True)))}
    # Without a watch, require at least two stored position observations before monitoring gaps.
    repeats=set(db.scalars(select(Position.mmsi).group_by(Position.mmsi).having(func.count(Position.id)>=2)))
    for mmsi,p in positions.items():
        elapsed=age(p.received_at,at)
        if elapsed>settings.shipping_stale_minutes*60:
            resolve(db,mmsi,["stationary_observation","reported_anchor","reported_moored","reported_not_under_command","watched_vessel_seen"],at)
            if mmsi in watched or mmsi in repeats:
                event(db,mmsi,"no_recent_observation",at,{"mmsi":mmsi,"last_received_at":utc(p.received_at).isoformat(),
                    "reason":"Feed or geographic coverage gaps may also explain the absence of observations."},p.region,elapsed/60,settings.shipping_stale_minutes,"watch")


def persist_messages(db,items):
    counts={"positions_stored":0,"static_updates":0,"duplicates":0,"normalized_records":0}
    for item in items:
        v=db.get(Vessel,item["mmsi"])
        if v is None:
            v=Vessel(mmsi=item["mmsi"],latest_received_at=item["received_at"]);db.add(v);db.flush()
        if utc(item["received_at"])>=utc(v.latest_received_at):
            v.latest_received_at=item["received_at"]
            for key,value in item["identity"].items(): setattr(v,key,value)
            if item["static"]: v.latest_static_received_at=item["received_at"];counts["static_updates"]+=1
        p=item["position"]
        if p and p["region"]!="outside_pilot":
            if db.scalar(select(Position.id).where(Position.dedupe_key==p["dedupe_key"])) is None:
                row=Position(**p);db.add(row);db.flush();apply_position_rules(db,row)
                counts["positions_stored"]+=1
            else: counts["duplicates"]+=1
        counts["normalized_records"]+=1
    return counts


def prune_positions(db,at=None):
    # Preserve each vessel's latest observation so retention cannot erase current state.
    cutoff=utc(at or now())-timedelta(days=get_settings().shipping_retention_days)
    keep=[p.id for p in latest_positions(db).values()]
    result=db.execute(delete(Position).where(Position.received_at<cutoff,Position.id.not_in(keep)))
    return result.rowcount


def collector_status(db,at=None):
    at=at or now();s=db.get(State,1)
    latest=db.scalar(select(func.max(Vessel.latest_received_at)))
    status=s.status if s and age(s.heartbeat_at,at)<=get_settings().shipping_heartbeat_seconds else "offline"
    return {"provider":"AISStream","collection_status":status,"collecting":status=="connected",
        "latest_message_received":utc(latest).isoformat() if latest else None,"last_seen_age_seconds":age(latest,at),
        "heartbeat_at":utc(s.heartbeat_at).isoformat() if s else None,"compression_enabled":s.compression_enabled if s else False,
        "counters":s.counters if s else {},"last_error":s.last_error if s else None,
        "monitored_regions":list(REGIONS.values()),"future_regions":["Latin America","USA","UK","UAE"],
        "retention_days":get_settings().shipping_retention_days,"stale_minutes":get_settings().shipping_stale_minutes}


def vessels(db,minutes=60,region=None,type_code=None,at=None):
    at=at or now();positions=latest_positions(db);watches={w.mmsi:w for w in db.scalars(select(Watch).where(Watch.active.is_(True)))}
    result=[]
    for v in db.scalars(select(Vessel).where(Vessel.latest_received_at>=utc(at)-timedelta(minutes=minutes)).order_by(Vessel.latest_received_at.desc()).limit(500)):
        p=positions.get(v.mmsi)
        if region and region!="gulf_of_guinea" and (not p or p.region!=region): continue
        if type_code is not None and v.vessel_type_code!=type_code: continue
        elapsed=age(p.received_at,at) if p else None
        result.append({"mmsi":v.mmsi,"vessel_name":v.vessel_name,"imo":v.imo,"callsign":v.callsign,
            "vessel_type_code":v.vessel_type_code,"draught":v.draught,"destination":v.destination,"eta_raw":v.eta_raw,
            "latest_static_received_at":utc(v.latest_static_received_at).isoformat() if v.latest_static_received_at else None,
            "last_seen":utc(v.latest_received_at).isoformat(),"last_seen_age_seconds":age(v.latest_received_at,at),
            "position_last_seen":utc(p.received_at).isoformat() if p else None,"position_age_seconds":elapsed,
            "provider_timestamp":utc(p.provider_timestamp).isoformat() if p and p.provider_timestamp else None,
            "ais_utc_second":p.ais_utc_second if p else None,"latitude":p.latitude if p else None,"longitude":p.longitude if p else None,
            "sog":p.sog if p else None,"cog":p.cog if p else None,"heading":p.heading if p else None,
            "navigation_status":p.navigation_status if p else None,"region":p.region if p else None,
            "watchlisted":v.mmsi in watches,"stale":elapsed is not None and elapsed>get_settings().shipping_stale_minutes*60})
    return result


def regions(db,minutes=60,at=None):
    at=at or now();settings=get_settings();positions=latest_positions(db)
    recent=[p for p in positions.values() if age(p.received_at,at)<=minutes*60]
    watched={w.mmsi for w in db.scalars(select(Watch).where(Watch.active.is_(True)))}
    result=[]
    for region,label in REGIONS.items():
        # Wider Gulf is the inclusive parent; subregion totals are not additive.
        rows=[p for p in recent if region=="gulf_of_guinea" or p.region==region]
        fresh=[p for p in rows if age(p.received_at,at)<=settings.shipping_stale_minutes*60]
        result.append({"region":region,"label":label,"vessels_observed":len(rows),
            "moving":sum(p.sog is not None and p.sog>settings.shipping_stationary_knots for p in fresh),
            "stationary":sum(p.sog is not None and p.sog<=settings.shipping_stationary_knots for p in fresh),
            "reported_anchored":sum(p.navigation_status==1 for p in fresh),"reported_moored":sum(p.navigation_status==5 for p in fresh),
            "stale_watchlist":sum(p.mmsi in watched and age(p.received_at,at)>settings.shipping_stale_minutes*60 for p in positions.values() if region=="gulf_of_guinea" or p.region==region),
            "coverage":"Activity observed" if rows else "No recent feed activity observed"})
    return result


def events(db,active=True,limit=100,at=None):
    at=at or now();result=[]
    rows=db.scalars(select(Event).where(Event.active==active).order_by(Event.observed_at.desc()).limit(limit))
    for e in rows:
        # Read paths never mutate data; suppress outdated positive observations between collector sweeps.
        if active and e.event_type!="no_recent_observation" and age(e.observed_at,at)>get_settings().shipping_stale_minutes*60: continue
        result.append({"id":e.id,"mmsi":e.mmsi,"event_type":e.event_type,"label":LABELS[e.event_type],
            "severity":e.severity,"observed_at":utc(e.observed_at).isoformat(),"evidence":e.evidence,
            "observed_value":e.observed_value,"threshold":e.threshold,"region":e.region,"active":e.active})
    return result
