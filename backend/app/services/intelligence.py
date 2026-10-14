import asyncio
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import re
from sqlalchemy import select, delete, update, or_, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.config import get_settings
from app.models.intelligence import IntelligenceDocument as Document, IntelligenceChunk as Chunk, IntelligenceFinding as Finding
from app.schemas.intelligence import IntelligenceFindingOutput
from app.services.intelligence_extraction import validate_file, extract, ExtractionError
from app.providers.ai.gemini import GeminiProvider


class ProcessingConflict(ValueError): pass


def now(): return datetime.now(timezone.utc)


def storage_root():
    configured=get_settings().intelligence_storage_dir
    root=Path(configured).expanduser().resolve() if configured else Path(__file__).resolve().parents[2]/"storage"/"intelligence"
    public=Path(__file__).resolve().parents[3]/"public"
    if root==public or public in root.parents: raise ValueError("Document storage must be outside the public asset directory.")
    return root


def original_path(document):
    root=storage_root().resolve();path=(root/document.storage_path).resolve()
    if path.parent!=root or path.name!=document.file_hash+'.'+document.file_type.lower():
        raise ValueError("Invalid private document reference.")
    return path


def upload(db,content,filename,mime,source,title,report_date):
    settings=get_settings();filename,kind,mime=validate_file(filename,content,mime,settings.intelligence_max_upload_mb*1024*1024)
    digest=sha256(content).hexdigest()
    existing=db.scalar(select(Document).where(Document.file_hash==digest))
    if existing: return existing,True
    root=storage_root();root.mkdir(parents=True,exist_ok=True)
    relative=digest+'.'+kind.lower();path=root/relative
    try:
        with path.open("xb") as f: f.write(content)
    except FileExistsError:
        if sha256(path.read_bytes()).hexdigest()!=digest: raise ValueError("Original document integrity check failed.")
    document=Document(source_organisation=source,title=title.strip() or filename,report_date=report_date,
        filename=filename,file_type=kind,mime_type=mime,file_hash=digest,storage_path=relative,processing_status="uploaded",extraction_limitations=[])
    db.add(document)
    try: db.commit();db.refresh(document)
    except IntegrityError:
        db.rollback();existing=db.scalar(select(Document).where(Document.file_hash==digest))
        if existing: return existing,True
        raise
    return document,False


def document_dict(db,document):
    return {"id":document.id,"source_organisation":document.source_organisation,"title":document.title,
        "report_date":str(document.report_date) if document.report_date else None,"filename":document.filename,
        "file_type":document.file_type,"mime_type":document.mime_type,"file_hash":document.file_hash,
        "processing_status":document.processing_status,"uploaded_at":document.uploaded_at.isoformat(),
        "processed_at":document.processed_at.isoformat() if document.processed_at else None,"error_message":document.error_message,
        "extraction_limitations":document.extraction_limitations,"summary":document.summary,"findings_rejected":document.findings_rejected,
        "chunk_count":db.scalar(select(func.count()).select_from(Chunk).where(Chunk.document_id==document.id)),
        "finding_count":db.scalar(select(func.count()).select_from(Finding).where(Finding.document_id==document.id)),
        "original_url":f"/api/intelligence/documents/{document.id}/original"}


def chunks_for(db,id): return db.scalars(select(Chunk).where(Chunk.document_id==id).order_by(Chunk.sequence)).all()


def validate_findings(output,document,chunks):
    indexed={c.id:c for c in chunks};accepted=[];rejected=0;seen=set()
    for raw in output.get("findings",[]):
        try:
            f=IntelligenceFindingOutput.model_validate(raw)
            chunk=indexed.get(f.source_chunk_id)
            if not chunk or f.source_locator!=chunk.source_locator: raise ValueError("Invented source location")
            if f.source_organisation!=document.source_organisation or f.document_title!=document.title or f.report_date!=(str(document.report_date) if document.report_date else None): raise ValueError("Changed document metadata")
            if f.evidence_excerpt not in chunk.text_content or f.key_fact not in f.evidence_excerpt: raise ValueError("Unsupported source quotation")
            if any(n not in f.evidence_excerpt for n in f.relevant_numbers): raise ValueError("Unsupported numeric context")
            available=set(re.findall(r"[+-]?\d+(?:,\d{3})*(?:\.\d+)?%?",f.evidence_excerpt))
            for text in [f.key_fact,*f.relevant_numbers,f.driver,f.risk_implication,f.time_horizon]:
                if not set(re.findall(r"[+-]?\d+(?:,\d{3})*(?:\.\d+)?%?",text)).issubset(available): raise ValueError("Unsupported numbers")
            fingerprint=(f.source_chunk_id,f.key_fact,f.signal_type,f.direction)
            if fingerprint in seen: raise ValueError("Duplicate finding")
            seen.add(fingerprint);accepted.append(f)
        except (ValueError,TypeError): rejected+=1
    return accepted,rejected


async def process(db: Session,id,reprocess=False,extract_only=False,provider=None):
    document=db.get(Document,id)
    if not document: raise KeyError(id)
    if document.processing_status=="completed" and not reprocess: return document
    started=now();expires=started-timedelta(minutes=10)
    conditions=[Document.id==id,or_(Document.processing_status.not_in(["extracting","analysing"]),Document.processing_started_at<expires)]
    locked=db.execute(update(Document).where(*conditions).execution_options(synchronize_session=False).values(processing_status="extracting",processing_started_at=started,error_message=None))
    if not locked.rowcount: db.commit();raise ProcessingConflict("This report is already processing. Retry after its processing lease expires.")
    db.commit();db.refresh(document)
    try:
        content=original_path(document).read_bytes()
        if sha256(content).hexdigest()!=document.file_hash: raise ExtractionError("Original document integrity check failed.")
        existing=chunks_for(db,id)
        # Original deterministic extraction is retained across retries; no AI failure removes it.
        if not existing:
            settings=get_settings()
            extracted,limitations=await asyncio.to_thread(extract,content,document.file_type,settings.intelligence_max_chunks,settings.intelligence_max_extracted_chars)
            for chunk in extracted: db.add(Chunk(document_id=id,**chunk))
            document.extraction_limitations=limitations
            db.flush();existing=chunks_for(db,id)
        document.processing_status="extracted";db.commit()
        if extract_only: return document
        document.processing_status="analysing";db.commit()
        ai=provider or GeminiProvider(api_key=get_settings().gemini_api_key)
        metadata={"source_organisation":document.source_organisation,"document_title":document.title,"report_date":str(document.report_date) if document.report_date else None}
        payload=[{"source_chunk_id":c.id,"source_locator":c.source_locator,"text_content":c.text_content} for c in existing]
        output=await ai.analyse_intelligence(metadata,payload)
        if not isinstance(output,dict) or set(output)!={"findings"} or not isinstance(output["findings"],list) or len(output["findings"])>40: raise ValueError("Gemini returned malformed structured findings.")
        accepted,rejected=validate_findings(output,document,existing)
        # Replace findings only after successful validated analysis, in one transaction.
        for previous in db.scalars(select(Finding).where(Finding.document_id==id)):
            db.delete(previous)
        db.flush()
        for f in accepted:
            values=f.model_dump(exclude={"source_organisation","document_title","report_date"})
            db.add(Finding(document_id=id,**values))
        signals=sorted({f.signal_type for f in accepted})
        document.summary=f"{len(accepted)} evidence-linked AI findings"+(" covering "+", ".join(signals) if signals else "")+". Interpretations require analyst review."
        document.findings_rejected=rejected;document.processing_status="completed";document.processed_at=now();document.error_message=None
        db.commit();db.refresh(document);return document
    except Exception as exc:
        if not db.is_active: db.rollback()
        else: db.expire_all()
        document=db.get(Document,id)
        document.processing_status="failed"
        if isinstance(exc,ExtractionError) and exc.limitations: document.extraction_limitations=exc.limitations
        document.error_message=str(exc) if isinstance(exc,ExtractionError) else "Analysis failed or is unavailable; original and extracted text are retained. Retry processing."
        document.processed_at=now();db.commit();db.refresh(document);return document


def delete_document(db,id):
    document=db.get(Document,id)
    if not document: raise KeyError(id)
    if document.processing_status in {"extracting","analysing"}:
        started=document.processing_started_at
        if started and (now()-(started.replace(tzinfo=timezone.utc) if started.tzinfo is None else started)).total_seconds()<600: raise ProcessingConflict("Cannot delete a report while processing.")
    path=original_path(document)
    db.execute(delete(Finding).where(Finding.document_id==id));db.execute(delete(Chunk).where(Chunk.document_id==id))
    db.delete(document);db.commit()
    # Originals are immutable until an analyst explicitly deletes the whole document.
    if path.exists(): path.unlink()
