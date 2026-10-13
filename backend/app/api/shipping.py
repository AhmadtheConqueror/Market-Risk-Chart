from typing import Annotated, Literal
from hmac import compare_digest
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import get_settings
from app.db.session import get_db
from app.models.shipping import ShippingWatchlist as Watch
from app.services import shipping as service

router=APIRouter(prefix="/shipping",tags=["shipping"])
DB=Annotated[Session,Depends(get_db)]


def require_shipping_admin(x_shipping_admin_token: str | None = Header(None)):
    secret=get_settings().shipping_admin_token
    if not secret or not x_shipping_admin_token or not compare_digest(secret.get_secret_value(),x_shipping_admin_token):
        raise HTTPException(403,"Watchlist administration requires an authenticated server-side administrator.")


class WatchInput(BaseModel):
    mmsi: str = Field(pattern=r"^[1-9][0-9]{8}$")
    vessel_name: str | None = Field(None,max_length=120)
    reason: str | None = Field(None,max_length=400)
    priority: Literal["normal","high"] = "normal"
    active: bool = True


def watch_dict(w):
    return {"id":w.id,"mmsi":w.mmsi,"vessel_name":w.vessel_name,"reason":w.reason,"priority":w.priority,"active":w.active}


@router.get("/status")
def status(db: DB):
    result=service.collector_status(db)
    recent=service.vessels(db)
    count=len(recent)
    result.update(vessels_observed_recently=count,static_voyage_vessels=sum(v["latest_static_received_at"] is not None for v in recent),
        destination_vessels=sum(v["destination"] is not None for v in recent),eta_vessels=sum(v["eta_raw"] is not None for v in recent),
        type_vessels=sum(v["vessel_type_code"] is not None for v in recent),watchlist_alerts=sum(e["event_type"] in {"watched_vessel_seen","no_recent_observation"} for e in service.events(db)))
    return result


@router.get("/vessels")
def vessels(db: DB,minutes: int=Query(60,ge=1,le=1440),region: Literal["lagos","niger_delta","gulf_of_guinea"] | None=None,type_code: int | None=Query(None,ge=20,le=99)):
    return service.vessels(db,minutes,region,type_code)


@router.get("/events")
def events(db: DB,active: bool=True,limit: int=Query(100,ge=1,le=200)):
    return service.events(db,active,limit)


@router.get("/regions")
def regions(db: DB,minutes: int=Query(60,ge=1,le=1440)):
    return service.regions(db,minutes)


@router.get("/watchlist")
def watchlist(db: DB):
    return [watch_dict(w) for w in db.scalars(select(Watch).order_by(Watch.priority.asc(),Watch.id).limit(500))]


@router.post("/watchlist",dependencies=[Depends(require_shipping_admin)],status_code=201)
def add_watch(data: WatchInput,db: DB):
    if db.scalar(select(Watch.id).where(Watch.mmsi==data.mmsi)):
        raise HTTPException(409,"This MMSI is already on the watchlist.")
    row=Watch(**data.model_dump());db.add(row);db.commit();db.refresh(row)
    return watch_dict(row)


@router.put("/watchlist/{watch_id}",dependencies=[Depends(require_shipping_admin)])
def update_watch(watch_id: int,data: WatchInput,db: DB):
    row=db.get(Watch,watch_id)
    if not row: raise HTTPException(404,"Watchlist entry not found.")
    other=db.scalar(select(Watch.id).where(Watch.mmsi==data.mmsi,Watch.id!=watch_id))
    if other: raise HTTPException(409,"This MMSI is already on the watchlist.")
    previous=row.mmsi
    for key,value in data.model_dump().items(): setattr(row,key,value)
    if not data.active or previous!=data.mmsi:
        service.resolve(db,previous,["watched_vessel_seen","no_recent_observation"],service.now())
    db.commit();db.refresh(row);return watch_dict(row)


@router.delete("/watchlist/{watch_id}",dependencies=[Depends(require_shipping_admin)])
def delete_watch(watch_id: int,db: DB):
    row=db.get(Watch,watch_id)
    if not row: raise HTTPException(404,"Watchlist entry not found.")
    service.resolve(db,row.mmsi,["watched_vessel_seen","no_recent_observation"],service.now())
    db.delete(row);db.commit();return {"deleted":watch_id}
