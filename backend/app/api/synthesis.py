from datetime import date, datetime, timedelta, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.intelligence import require_admin
from app.models.synthesis import IntelligenceSynthesisRun
from app.schemas.synthesis import SynthesisWindow
from app.services import synthesis as service

router=APIRouter(prefix="/intelligence/synthesis",tags=["intelligence"])
DB=Annotated[Session,Depends(get_db)]


def window(window_start: date | None=Query(None),window_end: date | None=Query(None)):
    end=window_end or datetime.now(timezone.utc).date()
    try: return SynthesisWindow(window_start=window_start or end-timedelta(days=6),window_end=end)
    except ValueError: raise HTTPException(422,"Invalid synthesis window: ordered dates, maximum 366 inclusive days.") from None


@router.post("/refresh",dependencies=[Depends(require_admin)])
async def refresh(data:SynthesisWindow,db:DB):
    run=await service.refresh(db,data.window_start,data.window_end)
    result=service.serialize(db,run)
    if run.status=="failed": raise HTTPException(503,result)
    return result


@router.get("")
def latest(db:DB,scope:Annotated[SynthesisWindow,Depends(window)]):
    return service.latest(db,scope.window_start,scope.window_end)


@router.get("/{id}")
def detail(id:int,db:DB):
    run=db.get(IntelligenceSynthesisRun,id)
    if not run: raise HTTPException(404,"Synthesis not found.")
    return service.serialize(db,run)
