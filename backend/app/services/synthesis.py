"""Bounded, evidence-first cross-document synthesis. No raw documents enter Gemini."""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
import re
from time import monotonic
from sqlalchemy import Date, cast, delete, func, select
from app.models.intelligence import IntelligenceDocument as Document, IntelligenceFinding as Finding
from app.models.synthesis import IntelligenceSynthesisRun as Run, IntelligenceSynthesis as Item, IntelligenceSynthesisEvidence as Evidence
from app.schemas.synthesis import SynthesisSelection
from app.providers.ai.gemini import GeminiProvider
from app.config import get_settings

TYPES = ("what_changed", "cross_source", "divergence", "watch_next")
MAX_FINDINGS = 240
MAX_CANDIDATES = 32
MAX_ITEMS_PER_TYPE = 5


def canonical(value):
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def normalize(value, dimension):
    value = canonical(value)
    aliases = {
        "commodity": {"crude":"crude oil", "crude oils":"crude oil", "brent crude":"brent", "wti crude":"wti", "jet":"jet fuel"},
        "geography": {"worldwide":"global", "world":"global", "nigerian":"nigeria", "us":"usa", "u.s.":"usa", "united states":"usa"},
        "time_horizon": {"near term":"near-term", "short term":"near-term", "short-term":"near-term", "medium term":"medium-term", "long term":"long-term"},
    }
    return aliases.get(dimension, {}).get(value, value)


def finding_record(f, d):
    return {"finding_id":f.id,"document_id":d.id,"source_organisation":d.source_organisation,
        "document_title":d.title,"report_date":d.report_date.isoformat() if d.report_date else None,
        "scope_date":(d.report_date or d.uploaded_at.date()).isoformat(),
        "date_basis":"report_date" if d.report_date else "upload_date",
        **{key:getattr(f,key) for key in ("commodity","geography","signal_type","direction","time_horizon","key_fact","relevant_numbers","confidence","source_locator","evidence_excerpt")}}


def digest(value):
    return sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()


def load_evidence(db, start, end):
    scope_date=func.coalesce(Document.report_date,cast(Document.uploaded_at,Date))
    # SQLite DATE casting differs from PostgreSQL; ISO date() has equivalent filtering semantics.
    if db.get_bind().dialect.name=="sqlite": scope_date=func.coalesce(Document.report_date,func.date(Document.uploaded_at))
    base=select(Finding,Document).join(Document,Finding.document_id==Document.id).where(
        Document.processing_status=="completed",scope_date>=start,scope_date<=end)
    total=db.scalar(select(func.count()).select_from(base.subquery()))
    records=db.execute(base.order_by(scope_date.desc(),Finding.id.desc()).limit(MAX_FINDINGS)).all()
    return [finding_record(f,d) for f,d in records],total


def group_key(row):
    dimensions = tuple(normalize(row[key],key) for key in ("commodity","geography","signal_type","time_horizon"))
    # Unknown dimensions cannot establish cross-report comparability.
    unknown = any(value in {"", "unknown", "unspecified", "other", "unclear"} for value in dimensions)
    return dimensions + ((str(row["document_id"]) if unknown else "comparable"),)


def independence_key(row):
    excerpt=canonical(row["key_fact"]+" "+row["evidence_excerpt"])
    for organisation in ("Argus","S&P Global","Kpler","CSCS"):
        publisher=re.escape(organisation.casefold())
        if re.search(r"(?:according to|citing|reported by|via)\s+"+publisher,excerpt):
            return organisation
    return row["source_organisation"] if row["source_organisation"]!="Other" else None


def independent_count(rows):
    # Collapse publishers connected by an identical claim or explicit attribution.
    parent={key:key for key in (independence_key(row) for row in rows) if key}
    def root(key):
        while parent[key]!=key: key=parent[key]
        return key
    by_claim={}
    for row in rows:
        key=independence_key(row)
        if not key: continue
        claim=canonical(row["key_fact"])
        if claim in by_claim:
            parent[root(key)]=root(by_claim[claim])
        else: by_claim[claim]=key
    return len({root(key) for key in parent})


def confidence(rows, kind, end):
    organisations = {row["source_organisation"] for row in rows}
    reports = {row["document_id"] for row in rows}
    # Identical claims, even under different publishers, do not establish independence.
    claims = {canonical(row["key_fact"]) for row in rows}
    independent = min(independent_count(rows), len(claims))
    reference=max(end,datetime.now(timezone.utc).date())
    age = max((reference-date.fromisoformat(row["scope_date"])).days for row in rows)
    phase1 = [row["confidence"] for row in rows]
    directions = {row["direction"] for row in rows}
    level = "Low"
    if independent >= 2 and len(reports)>=2 and age<=30 and "low" not in phase1:
        level = "Medium"
    if independent>=3 and len(reports)>=3 and age<=7 and all(c=="high" for c in phase1) and len(directions)==1:
        level = "High"
    if kind=="divergence" and level=="High": level="Medium"
    if any(row["date_basis"]=="upload_date" for row in rows): level="Low"
    return level,{"source_organisation_count":len(organisations),"report_count":len(reports),
        "raw_finding_count":len(rows),"independent_claim_count":independent,"oldest_evidence_age_days":age,
        "phase1_confidences":sorted(set(phase1)),"directions":sorted(directions),
        "rules_version":"evidence-v1", "recency_as_of":str(reference), "date_basis":"includes upload-date fallback" if any(r["date_basis"]=="upload_date" for r in rows) else "report dates"}


def candidates(rows, end):
    grouped=defaultdict(list)
    for row in rows: grouped[group_key(row)].append(row)
    result=[];omitted=defaultdict(int)
    def add(kind, evidence, direction, title, description):
        # Each proposal remains bounded and cites whole deterministic groups.
        if len(evidence)>60:
            omitted["oversize_evidence_group"]+=1
            return
        evidence=sorted(evidence,key=lambda row:row["finding_id"])
        first=evidence[0];level,basis=confidence(evidence,kind,end)
        result.append({"candidate_id":f"c{len(result)+1}","synthesis_type":kind,
            "title":title,"description":description,"direction":direction,
            "commodity":normalize(first["commodity"],"commodity"),"geography":normalize(first["geography"],"geography"),
            "signal_type":first["signal_type"],"time_horizon":normalize(first["time_horizon"],"time_horizon"),
            "confidence":level,"confidence_basis":basis,"findings":evidence})
    for key, group in sorted(grouped.items()):
        comparable=key[-1]=="comparable"
        if not comparable: omitted["insufficient_comparability"]+=1
        # Do not conflate a rolling horizon across distant report dates.
        dates=[date.fromisoformat(r["scope_date"]) for r in group]
        if key[3]=="near-term" and (max(dates)-min(dates)).days>30:
            comparable=False;omitted["non_overlapping_near_term"]+=1
        title=" / ".join(key[:3])
        by_direction=defaultdict(list)
        for row in group: by_direction[row["direction"]].append(row)
        for direction,evidence in sorted(by_direction.items()):
            orgs={independence_key(r) for r in evidence}-{None}
            claims={canonical(r["key_fact"]) for r in evidence}
            if comparable and direction in {"bullish","bearish","neutral"} and independent_count(evidence)>=2 and len(claims)>=2:
                add("cross_source",evidence,direction,title,f"Aligned {direction} assessments across contributing publishers; independence is not externally verified.")
            elif len(evidence)>1 and (len(orgs)<2 or len(claims)<2): omitted["not_independent"]+=1
        orgs={independence_key(r) for r in group}-{None}
        directions={r["direction"] for r in group}
        if comparable and independent_count(group)>=2:
            opposite=any(a["direction"]=="bullish" and b["direction"]=="bearish" and a["source_organisation"]!=b["source_organisation"] for a in group for b in group)
            if opposite:
                add("divergence",group,"Divergent",title,"Comparable contributing publishers contain opposing bullish and bearish assessments; contradictions remain unresolved.")
            elif "mixed" in directions or len(directions & {"bullish","bearish","neutral"})>1:
                add("divergence",group,"Mixed",title,"Comparable assessments differ or include mixed direction; this does not establish opposing forecasts.")
        # Compare latest dated cohort with earlier dated reports; repeat claims are not change.
        dated=[r for r in group if r["report_date"]]
        if comparable and len({r["report_date"] for r in dated})>=2:
            latest=max(r["report_date"] for r in dated)
            recent=[r for r in dated if r["report_date"]==latest]
            earlier=[r for r in dated if r["report_date"]<latest]
            old={r["direction"] for r in earlier};new={r["direction"] for r in recent}
            if old!=new and not (old|new)&{"unclear","mixed"} and {canonical(r["key_fact"]) for r in recent}-{canonical(r["key_fact"]) for r in earlier}:
                add("what_changed",earlier+recent,"mixed" if len(new)>1 else next(iter(new)),title,
                    f"Direction in the latest report-date cohort: {', '.join(sorted(new))}; earlier cohort: {', '.join(sorted(old))}. This describes reported assessments, not a measured market change.")
            else: omitted["repeated_or_no_direction_change"]+=1
        # A watch is a review of source-supported uncertainty, never a fabricated event/date.
        uncertainty=[r for r in group if r["confidence"]=="low" or r["direction"] in {"mixed","unclear"} or re.search(r"\b(uncertain|pending|expected|forecast|outlook|restart|may|could)\b", canonical(r["key_fact"]))]
        if uncertainty:
            add("watch_next",uncertainty,"unclear",f"Review {title}","Review subsequent reporting on the cited forward-looking or low-confidence assessment. Why it matters: its future outcome is not established by these findings; no event date is inferred.")
    # Deterministic balanced bound: weak groups cannot crowd out another section.
    bounded=[]
    for kind in TYPES:
        subset=sorted((c for c in result if c["synthesis_type"]==kind),key=lambda c:(-c["confidence_basis"]["source_organisation_count"],-max(int(r["scope_date"].replace("-","")) for r in c["findings"]),c["candidate_id"]))
        bounded.extend(subset[:8]);omitted["candidate_bound"]+=max(0,len(subset)-8)
    payload=[];size=0
    for candidate in bounded[:MAX_CANDIDATES]:
        cost=len(json.dumps(candidate,ensure_ascii=False))
        if size+cost>90000:
            omitted["payload_character_bound"]+=1
            continue
        payload.append(candidate);size+=cost
    return payload,dict(omitted)


def validate_selections(output, proposals):
    lookup={c["candidate_id"]:c for c in proposals};accepted=[];rejected=0;seen=set();counts=defaultdict(int)
    if not isinstance(output,dict) or set(output)!={"items"} or not isinstance(output["items"],list) or len(output["items"])>20:
        raise ValueError("Malformed synthesis response.")
    for raw in output["items"]:
        try:
            selection=SynthesisSelection.model_validate(raw);candidate=lookup[selection.candidate_id]
            ids={r["finding_id"] for r in candidate["findings"]}
            if set(selection.finding_ids)!=ids or len(selection.finding_ids)!=len(ids): raise ValueError("Changed evidence set")
            if selection.summary not in {r["key_fact"] for r in candidate["findings"]}: raise ValueError("Unsupported factual claim")
            if selection.candidate_id in seen or counts[candidate["synthesis_type"]]>=MAX_ITEMS_PER_TYPE: raise ValueError("Duplicate or excess item")
            accepted.append((candidate,selection.summary));seen.add(selection.candidate_id);counts[candidate["synthesis_type"]]+=1
        except (ValueError,TypeError,KeyError): rejected+=1
    return accepted,rejected


async def refresh(db, start, end, provider=None):
    started=monotonic();rows,total=load_evidence(db,start,end);proposals,omitted=candidates(rows,end)
    provider=provider or GeminiProvider(api_key=get_settings().gemini_api_key)
    metrics={"document_count":len({r["document_id"] for r in rows}),"source_organisation_count":len({r["source_organisation"] for r in rows}),
        "finding_count":len(rows),"eligible_finding_count":total,"truncated_findings":max(0,total-len(rows)),
        "candidate_count":len(proposals),"omitted_candidates":omitted,"rejected_items":0,
        "single_source":len({r["source_organisation"] for r in rows})==1,
        "unknown_date_findings":sum(r["date_basis"]=="upload_date" for r in rows)}
    run=Run(window_start=start,window_end=end,status="completed",model_version=getattr(provider,"model","unknown"),input_hash=digest(rows),metrics=metrics)
    nested=None
    try:
        accepted=[]
        if proposals:
            output=await provider.synthesize_intelligence(proposals)
            accepted,rejected=validate_selections(output,proposals);metrics["rejected_items"]=rejected
            metrics["unselected_candidates"]=len(proposals)-len(accepted)
            if not accepted and rejected: raise ValueError("No evidence-supported synthesis returned.")
        used={r["finding_id"]:r for proposal,_ in accepted for r in proposal["findings"]}
        metrics["finding_count_used"]=len(used)
        metrics["document_count_used"]=len({r["document_id"] for r in used.values()})
        # A source could be reprocessed/deleted while Gemini was running.
        db.expire_all();current,_=load_evidence(db,start,end)
        if digest(current)!=run.input_hash: raise ValueError("Evidence changed during processing.")
        connection=db.connection()
        if connection.dialect.name=="sqlite" and not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN")
        nested=db.begin_nested()
        db.add(run);db.flush()
        for proposal,summary in accepted:
            item=Item(run_id=run.id,synthesis_type=proposal["synthesis_type"],title=proposal["title"][:255],
                summary=proposal["description"]+" Source assessment: "+summary,
                **{key:proposal[key] for key in ("commodity","geography","signal_type","direction","time_horizon","confidence","confidence_basis")},
                evidence_count=len(proposal["findings"]))
            db.add(item);db.flush()
            for row in proposal["findings"]: db.add(Evidence(synthesis_id=item.id,finding_id=row["finding_id"],evidence_hash=digest(row)))
        nested.commit()
    except Exception:
        if nested is not None: nested.rollback()
        run=Run(window_start=start,window_end=end,status="failed",model_version=getattr(provider,"model","unknown"),input_hash=digest(rows),metrics=metrics,
            error_message="Synthesis failed validation, evidence changed, or AI is unavailable. Previous supported synthesis is retained; retry refresh.")
        db.add(run)
    run.metrics={**metrics,"duration_seconds":round(monotonic()-started,3)}
    db.commit();db.refresh(run)
    return run


def serialize(db, run):
    current,_=load_evidence(db,run.window_start,run.window_end)
    result={"id":run.id,"status":run.status,"generated_at":run.generated_at.isoformat(),"window_start":str(run.window_start),"window_end":str(run.window_end),
        "model_version":run.model_version,"metrics":run.metrics,"error_message":run.error_message,"stale":digest(current)!=run.input_hash,"items":[]}
    items=list(db.scalars(select(Item).where(Item.run_id==run.id).order_by(Item.id)))
    linked=defaultdict(list)
    if items:
        for link,f,d in db.execute(select(Evidence,Finding,Document).join(Finding,Evidence.finding_id==Finding.id)
            .join(Document,Finding.document_id==Document.id).where(Evidence.synthesis_id.in_([item.id for item in items]))
            .order_by(Evidence.id)):
            linked[link.synthesis_id].append((link,f,d))
    for item in items:
        links=linked[item.id]
        records=[finding_record(f,d) for _,f,d in links]
        if len(records)!=item.evidence_count or not records or any(d.processing_status!="completed" or digest(record)!=link.evidence_hash for (link,f,d),record in zip(links,records)):
            result["stale"]=True
            continue  # Never display an orphan or evidence changed after synthesis.
        result["items"].append({"id":item.id,**{key:getattr(item,key) for key in ("synthesis_type","title","summary","commodity","geography","signal_type","direction","time_horizon","confidence","confidence_basis")},
            "finding_ids":[r["finding_id"] for r in records],"document_ids":sorted({r["document_id"] for r in records}),
            "source_organisations":sorted({r["source_organisation"] for r in records}),"evidence":records})
    return result


def latest(db,start,end):
    scope=(Run.window_start==start,Run.window_end==end)
    last=db.scalar(select(Run).where(*scope).order_by(Run.id.desc()).limit(1))
    completed=db.scalar(select(Run).where(*scope,Run.status=="completed").order_by(Run.id.desc()).limit(1))
    data=serialize(db,completed) if completed else None
    attempt=data if last and completed and last.id==completed.id else serialize(db,last) if last else None
    return {"available":completed is not None,"data":data,"last_attempt":attempt}


def invalidate_document(db, document_id):
    """Delete dependent cards before Phase-1 replacement/deletion; retain run audit."""
    ids=list(db.scalars(select(Evidence.synthesis_id).join(Finding,Evidence.finding_id==Finding.id)
        .where(Finding.document_id==document_id).distinct()))
    if ids:
        db.execute(delete(Evidence).where(Evidence.synthesis_id.in_(ids)))
        db.execute(delete(Item).where(Item.id.in_(ids)))
