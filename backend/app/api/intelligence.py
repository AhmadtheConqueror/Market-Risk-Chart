from datetime import date
from hmac import compare_digest
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import get_settings
from app.db.session import get_db
from app.models.intelligence import IntelligenceDocument as Document, IntelligenceFinding as Finding
from app.services import intelligence as service
from app.services.intelligence_extraction import ExtractionError

router=APIRouter(prefix="/intelligence",tags=["intelligence"])
DB=Annotated[Session,Depends(get_db)]
Source=Literal["Argus","S&P Global","Kpler","CSCS","Other"]


def require_admin(x_intelligence_admin_token: str | None=Header(None)):
    secret=get_settings().shipping_admin_token  # Existing private proxy credential; no new browser secret.
    if not secret or not x_intelligence_admin_token or not compare_digest(secret.get_secret_value(),x_intelligence_admin_token):
        raise HTTPException(403,"Administrator authentication is required for document changes and original downloads.")


def get_document(db,id):
    document=db.get(Document,id)
    if not document: raise HTTPException(404,"Report not found.")
    return document


@router.post("/documents",dependencies=[Depends(require_admin)])
async def upload_document(db: DB,report: UploadFile=File(...),source_organisation: Source=Form(...),title: str=Form(...,min_length=1,max_length=255),report_date: date | None=Form(None)):
    limit=get_settings().intelligence_max_upload_mb*1024*1024
    parts=[];size=0
    while part:=await report.read(1024*1024):
        size+=len(part)
        if size>limit: raise HTTPException(413,"Upload exceeds the configured file-size limit.")
        parts.append(part)
    try: document,duplicate=service.upload(db,b"".join(parts),report.filename,report.content_type,source_organisation,title,report_date)
    except (ExtractionError,ValueError): raise HTTPException(400,"Upload rejected: verify format, MIME type, filename and file-size limits.")
    return {"document":service.document_dict(db,document),"duplicate":duplicate}


@router.get("/documents")
def documents(db: DB,source: Source | None=None,start_date: date | None=None,end_date: date | None=None,limit: int=Query(50,ge=1,le=100)):
    query=select(Document)
    if source: query=query.where(Document.source_organisation==source)
    if start_date: query=query.where(Document.report_date>=start_date)
    if end_date: query=query.where(Document.report_date<=end_date)
    return [service.document_dict(db,d) for d in db.scalars(query.order_by(Document.uploaded_at.desc()).limit(limit))]


@router.get("/documents/{id}")
def document(id: int,db: DB):
    d=get_document(db,id);result=service.document_dict(db,d)
    result["chunks"]=[{"id":c.id,"chunk_type":c.chunk_type,"page_number":c.page_number,"sheet_name":c.sheet_name,"section_name":c.section_name,
        "source_locator":c.source_locator,"text_content":c.text_content,"structured_data":c.structured_data,"sequence":c.sequence} for c in service.chunks_for(db,id)]
    return result


@router.get("/documents/{id}/original",dependencies=[Depends(require_admin)])
def original(id: int,db: DB):
    d=get_document(db,id)
    try: path=service.original_path(d)
    except ValueError: raise HTTPException(404,"Original file is unavailable.")
    if not path.is_file(): raise HTTPException(404,"Original file is unavailable.")
    return FileResponse(path,media_type="application/octet-stream",filename=d.filename,headers={"X-Content-Type-Options":"nosniff","Cache-Control":"private, no-store"})


@router.post("/documents/{id}/process",dependencies=[Depends(require_admin)])
async def process(id: int,db: DB,reprocess: bool=False,extract_only: bool=False):
    get_document(db,id)
    try: d=await service.process(db,id,reprocess,extract_only)
    except service.ProcessingConflict as exc: raise HTTPException(409,str(exc))
    return service.document_dict(db,d)


@router.get("/documents/{id}/findings")
def findings(id: int,db: DB,commodity: str | None=None,geography: str | None=None,signal_type: str | None=None,direction: str | None=None):
    d=get_document(db,id);query=select(Finding).where(Finding.document_id==id)
    for name,value in [("commodity",commodity),("geography",geography),("signal_type",signal_type),("direction",direction)]:
        if value: query=query.where(getattr(Finding,name)==value)
    rows=db.scalars(query.order_by(Finding.id).limit(200)).all()
    return [{"id":f.id,"document_id":id,"source_organisation":d.source_organisation,"document_title":d.title,"report_date":str(d.report_date) if d.report_date else None,
        **{k:getattr(f,k) for k in ["commodity","geography","signal_type","direction","time_horizon","key_fact","relevant_numbers","driver","risk_implication","confidence","source_chunk_id","source_locator","evidence_excerpt"]},"created_at":f.created_at.isoformat(),"evidence_status":"source excerpt matched; AI interpretation requires review"} for f in rows]


@router.delete("/documents/{id}",dependencies=[Depends(require_admin)])
def remove(id: int,db: DB):
    get_document(db,id)
    try: service.delete_document(db,id)
    except service.ProcessingConflict as exc: raise HTTPException(409,str(exc))
    return {"deleted":id}
