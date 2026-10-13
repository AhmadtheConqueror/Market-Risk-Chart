import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import json
import pytest
from pydantic import SecretStr
from sqlalchemy import select, func
from app.models.shipping import ShippingVessel as Vessel, ShippingPosition as Position, ShippingWatchlist as Watch, ShippingEvent as Event, ShippingCollectorState as State
from app.services.shipping_normalization import normalize, classify, valid_eta
from app.services import shipping as service
from app.services import shipping_collector as worker

AT=datetime(2026,10,13,12,0,tzinfo=timezone.utc)


def message(kind="PositionReport",mmsi=657106100,**fields):
    report={"UserID":mmsi,"Valid":True,"Latitude":4.69,"Longitude":7.16,"Sog":0,"Cog":0,"TrueHeading":0,"NavigationalStatus":5,"Timestamp":0}
    report.update(fields)
    return {"MessageType":kind,"MetaData":{"MMSI":mmsi,"ShipName":"VESSEL","time_utc":AT.isoformat()},"Message":{kind:report}}


@pytest.mark.parametrize("kind",["PositionReport","StandardClassBPositionReport","ExtendedClassBPositionReport"])
def test_position_normalization_preserves_zero_and_time(kind):
    item=normalize(message(kind),AT)
    p=item["position"]
    assert p["sog"]==0 and p["cog"]==0 and p["heading"]==0 and p["ais_utc_second"]==0
    assert p["received_at"]==AT and p["provider_timestamp"]==AT
    assert p["region"]=="niger_delta"


def test_sentinels_invalid_and_missing_values():
    p=normalize(message(Sog=102.3,Cog=360,TrueHeading=511,NavigationalStatus=15,Timestamp=60),AT)["position"]
    assert all(p[k] is None for k in ["sog","cog","heading","navigation_status","ais_utc_second"])
    assert normalize(message(Latitude=91,Longitude=181),AT)["position"] is None
    assert normalize(message(Valid=False),AT) is None
    assert normalize(message(mmsi=0),AT) is None
    assert normalize({"MessageType":"PositionReport","Message":{"PositionReport":{"Valid":True}}},AT) is None


@pytest.mark.parametrize("lat,lon,expected",[(6.4,3.4,"lagos"),(4.7,7.2,"niger_delta"),(4,3,"gulf_of_guinea"),(40,-80,"outside_pilot")])
def test_region_classification(lat,lon,expected):
    assert classify(lat,lon)==expected


def test_static_position_join_eta_and_secret_redaction(db_session):
    static=message("ShipStaticData",Name="VESSEL diagnostic-secret",ImoNumber=1234567,CallSign="CALL",Type=80,Destination="ONNE",MaximumStaticDraught=2.1,Eta={"Month":10,"Day":13,"Hour":0,"Minute":0})
    service.persist_messages(db_session,[normalize(message(),AT),normalize(static,AT+timedelta(seconds=2),"diagnostic-secret")])
    db_session.flush()
    v=db_session.get(Vessel,"657106100")
    assert v.imo==1234567 and v.destination=="ONNE" and "diagnostic-secret" not in v.vessel_name
    assert v.eta_raw=={"Month":10,"Day":13,"Hour":0,"Minute":0} and "Year" not in v.eta_raw
    p=service.latest_positions(db_session)[v.mmsi]
    assert service.age(p.received_at,AT+timedelta(seconds=2))==2
    assert service.utc(v.latest_static_received_at)==AT+timedelta(seconds=2)


def test_sparse_static_and_invalid_eta_do_not_create_placeholders(db_session):
    service.persist_messages(db_session,[normalize(message(),AT)])
    v=db_session.get(Vessel,"657106100")
    assert v.imo is None and v.destination is None and v.eta_raw is None and v.vessel_type_code is None
    assert valid_eta({"Month":0,"Day":0,"Hour":24,"Minute":60}) is None
    assert valid_eta({"Month":2,"Day":30,"Hour":0,"Minute":0}) is None


def test_class_b_multipart_identity_join(db_session):
    a=message("StaticDataReport",ReportA={"Valid":True,"Name":"PART A"},ReportB={"Valid":False})
    b=message("StaticDataReport",ReportA={"Valid":False},ReportB={"Valid":True,"ShipType":52,"CallSign":"TUG"})
    # Metadata in a part B report may be unnamed; it must not erase part A.
    b["MetaData"]["ShipName"]=""
    service.persist_messages(db_session,[normalize(a,AT),normalize(b,AT+timedelta(seconds=1))])
    v=db_session.get(Vessel,"657106100")
    assert v.vessel_name=="PART A" and v.callsign=="TUG" and v.vessel_type_code==52


def test_position_deduplication_and_distinct_mmsi_aggregates(db_session):
    first=normalize(message(),AT)
    duplicate=normalize(message(),AT+timedelta(seconds=1))
    counts=service.persist_messages(db_session,[first,duplicate])
    assert counts["positions_stored"]==1 and counts["duplicates"]==1
    regions=service.regions(db_session,60,AT+timedelta(seconds=2))
    assert next(r for r in regions if r["region"]=="niger_delta")["vessels_observed"]==1
    lagos=next(r for r in regions if r["region"]=="lagos")
    assert lagos["coverage"]=="No recent feed activity observed"
    assert next(r for r in regions if r["region"]=="gulf_of_guinea")["vessels_observed"]==1


@pytest.mark.parametrize("status,kind",[(1,"reported_anchor"),(5,"reported_moored"),(2,"reported_not_under_command")])
def test_stationary_watchlist_and_navigation_events(db_session,status,kind):
    db_session.add(Watch(mmsi="657106100",priority="normal",active=True));db_session.flush()
    service.persist_messages(db_session,[normalize(message(NavigationalStatus=status),AT)])
    db_session.flush()
    events=service.events(db_session,at=AT)
    types={e["event_type"] for e in events}
    assert types=={"watched_vessel_seen","stationary_observation",kind}
    stationary=next(e for e in events if e["event_type"]=="stationary_observation")
    assert stationary["observed_value"]==0
    watched=next(e for e in events if e["event_type"]=="watched_vessel_seen")
    assert all(k in watched["evidence"] for k in ["mmsi","latitude","longitude","received_at","region"])


def test_stale_rule_wording_watchlist_and_resolution(db_session):
    db_session.add(Watch(mmsi="657106100",active=True,priority="normal"));db_session.flush()
    service.persist_messages(db_session,[normalize(message(),AT)])
    service.sweep_rules(db_session,AT+timedelta(minutes=20));db_session.flush()
    e=service.events(db_session,at=AT+timedelta(minutes=20))
    assert [v["label"] for v in e]==["No recent AIS observation"]
    assert "coverage" in e[0]["evidence"]["reason"]
    newer=message();newer["MetaData"]["time_utc"]=(AT+timedelta(minutes=21)).isoformat()
    service.persist_messages(db_session,[normalize(newer,AT+timedelta(minutes=21))]);db_session.flush()
    assert not any(e["event_type"]=="no_recent_observation" for e in service.events(db_session,at=AT+timedelta(minutes=21)))


def test_single_unwatched_observation_does_not_trigger_stale(db_session):
    service.persist_messages(db_session,[normalize(message(),AT)])
    service.sweep_rules(db_session,AT+timedelta(hours=1));db_session.flush()
    assert not service.events(db_session,at=AT+timedelta(hours=1))


def test_repeated_unwatched_vessel_is_monitored_and_moving_resolves_stationary(db_session):
    service.persist_messages(db_session,[normalize(message(),AT)])
    second=message(Sog=6);second["MetaData"]["time_utc"]=(AT+timedelta(minutes=1)).isoformat()
    service.persist_messages(db_session,[normalize(second,AT+timedelta(minutes=1))]);db_session.flush()
    assert not any(e["event_type"]=="stationary_observation" for e in service.events(db_session,at=AT+timedelta(minutes=1)))
    service.sweep_rules(db_session,AT+timedelta(hours=1));db_session.flush()
    assert any(e["event_type"]=="no_recent_observation" for e in service.events(db_session,at=AT+timedelta(hours=1)))


def test_retention_preserves_latest_position_state(db_session):
    for i in [0,1]:
        msg=message();msg["MetaData"]["time_utc"]=(AT+timedelta(days=i)).isoformat()
        service.persist_messages(db_session,[normalize(msg,AT+timedelta(days=i))])
    assert service.prune_positions(db_session,AT+timedelta(days=10))==1
    assert len(service.latest_positions(db_session))==1


def test_api_offline_and_output_no_secret(client,db_session):
    status=client.get("/api/shipping/status")
    assert status.status_code==200 and status.json()["collection_status"]=="offline"
    assert "AISSTREAM_API_KEY" not in status.text
    service.persist_messages(db_session,[normalize(message(),service.now())]);db_session.flush()
    rows=client.get("/api/shipping/vessels").json()
    assert rows[0]["sog"]==0 and rows[0]["eta_raw"] is None
    assert client.get("/api/shipping/regions").status_code==200
    assert client.get("/api/shipping/events").status_code==200
    assert client.get("/api/shipping/vessels?minutes=0").status_code==422


def test_watchlist_crud_requires_backend_admin(client,monkeypatch):
    import app.api.shipping as api
    monkeypatch.setattr(api,"get_settings",lambda:SimpleNamespace(shipping_admin_token=SecretStr("test-only-token")))
    payload={"mmsi":"657106100","reason":"Analyst fixture","priority":"high"}
    assert client.post("/api/shipping/watchlist",json=payload).status_code==403
    headers={"x-shipping-admin-token":"test-only-token"}
    first=client.post("/api/shipping/watchlist",json=payload,headers=headers)
    assert first.status_code==201
    id=first.json()["id"]
    assert client.post("/api/shipping/watchlist",json=payload,headers=headers).status_code==409
    assert client.get("/api/shipping/watchlist").json()[0]["mmsi"]==payload["mmsi"]
    assert client.put(f"/api/shipping/watchlist/{id}",json={**payload,"active":False},headers=headers).json()["active"] is False
    assert client.delete(f"/api/shipping/watchlist/{id}",headers=headers).status_code==200
    assert client.get("/api/shipping/watchlist").json()==[]
    assert client.post("/api/shipping/watchlist",json={**payload,"mmsi":"123"},headers=headers).status_code==422


def test_collector_heartbeat_expiry_and_clock_skew(db_session):
    db_session.add(State(id=1,run_id="fixture",status="connected",heartbeat_at=AT,started_at=AT,compression_enabled=True,counters={}))
    db_session.flush()
    assert service.collector_status(db_session,AT)["collecting"] is True
    assert service.collector_status(db_session,AT+timedelta(minutes=1))["collection_status"]=="offline"
    assert service.age(AT,AT-timedelta(seconds=1))==0


def test_collector_binary_frames_reconnect_and_secret_safe(capsys,monkeypatch):
    async def check():
        stop=asyncio.Event();queue=asyncio.Queue();state={};counts={}
        from collections import Counter
        counts=Counter();attempts=[0]
        class Socket:
            async def send(self,payload):
                data=json.loads(payload);assert data["BoundingBoxes"]==[worker.BOX] and data["APIKey"]=="never-log-me"
            def __aiter__(self):
                async def stream():
                    yield json.dumps({"MessageType":"SubscriptionConfirmation","Message":{"CompressionEnabled":True}}).encode()
                    yield json.dumps(message()).encode()
                    stop.set()
                return stream()
        class Connection:
            async def __aenter__(self):
                attempts[0]+=1
                if attempts[0]==1: raise OSError("never-log-me")
                return Socket()
            async def __aexit__(self,*args): pass
        monkeypatch.setattr(worker,"backoff",lambda _:0)
        await worker.receive(stop,queue,state,counts,"never-log-me",connector=lambda *a,**kw:Connection())
        assert counts["reconnects"]==1 and counts["messages_received"]==1
        assert queue.qsize()==1 and state["compression_enabled"] is True
    asyncio.run(check())
    assert "never-log-me" not in capsys.readouterr().out


def test_singleton_rejects_second_local_collector(db_session):
    engine=db_session.get_bind().engine
    with worker.singleton(engine):
        with pytest.raises(OSError):
            with worker.singleton(engine): pass
