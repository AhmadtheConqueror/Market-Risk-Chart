"""Optional qualitative intelligence for Risk Advisor only; never a risk-score input."""
from datetime import datetime, timedelta, timezone
import json
import re
from sqlalchemy import case, select
from app.config import get_settings
from app.models.intelligence import IntelligenceDocument as Document
from app.models.synthesis import IntelligenceSynthesisRun as Run
from app.schemas.ai import PulseInterpretation, PulseInterpretationOutput
from app.services import synthesis

MAX_CARDS=8
MAX_CONTEXT_CHARS=12000
SECTIONS={"what_changed":"what_changed","cross_source":"cross_source_signals","divergence":"divergences","watch_next":"watch_next"}


def utc(value):
    if isinstance(value,str): value=datetime.fromisoformat(value.replace("Z","+00:00"))
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def synthetic_document(document):
    # Existing labelled fixture metadata is sufficient; no browser/API override.
    return bool(re.search(r"(?i)(?:^|[\W_])(synthetic|fixture|test)(?:$|[\W_])",document.title+" "+document.filename))


def is_stale(run, now):
    hours=get_settings().risk_advisor_pulse_freshness_hours
    age=max((now-utc(run.generated_at)).total_seconds()/3600,(now.date()-run.window_end).days*24)
    return age>hours


def valid_cards(db,run,allow_synthetic=False):
    saved=synthesis.serialize(db,run)
    ids={id for item in saved["items"] for id in item["document_ids"]}
    documents={d.id:d for d in db.scalars(select(Document).where(Document.id.in_(ids)))} if ids else {}
    cards=[]
    for item in saved["items"]:
        if any(id not in documents for id in item["document_ids"]):continue
        if not allow_synthetic and (any(synthetic_document(documents[id]) for id in item["document_ids"]) or
            any(re.match(r"(?i)^\s*(synthetic|test fixture)\b",row["key_fact"]) for row in item["evidence"])):continue
        if item["confidence"] not in {"High","Medium"}:continue
        cards.append(item)
    return saved,cards


def select_context(db, *, now=None, _controlled_test=False):
    """Production callers cannot opt into fixtures through any endpoint/config."""
    now=now or datetime.now(timezone.utc)
    try:
        connection=db.connection()
        if connection.dialect.name=="sqlite" and not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN")
        with db.begin_nested():
            today=now.date()
            preferred=case(((Run.window_end==today)&(Run.window_start==today-timedelta(days=6)),0),
                ((Run.window_end==today)&(Run.window_start==today-timedelta(days=29)),1),else_=2)
            runs=list(db.scalars(select(Run).where(Run.status=="completed",Run.window_end<=today,
                Run.window_end>=today-timedelta(days=90)).order_by(preferred,Run.window_end.desc(),Run.generated_at.desc(),Run.id.desc()).limit(12)))
            for run in runs:
                saved,items=valid_cards(db,run,_controlled_test)
                if not items:continue
                items.sort(key=lambda item:(item["synthesis_type"]!="divergence",item["confidence"]!="High",item["id"]))
                block={"synthesis_run_id":run.id,"generated_at":utc(run.generated_at).isoformat(),"window_start":str(run.window_start),"window_end":str(run.window_end),
                    "stale":is_stale(run,now) or saved["stale"],"freshness_limit_hours":get_settings().risk_advisor_pulse_freshness_hours,
                    "report_count":0,"source_organisation_count":0,"finding_count":0,**{name:[] for name in SECTIONS.values()}}
                chosen=[]
                divergence_count=0
                for item in items:
                    if len(chosen)>=MAX_CARDS:break
                    if item["synthesis_type"]=="divergence" and divergence_count>=3:continue
                    compact={"synthesis_card_id":item["id"],"type":item["synthesis_type"],"title":item["title"],"summary":item["summary"],
                        "commodity":item["commodity"],"geography":item["geography"],"signal_type":item["signal_type"],"time_horizon":item["time_horizon"],
                        "direction":item["direction"],"confidence":item["confidence"],"contributing_source_count":len(item["source_organisations"])}
                    if len(compact["summary"])>2200:continue # Omit whole cards, never cut supporting meaning.
                    section=SECTIONS.get(item["synthesis_type"])
                    if not section:continue
                    block[section].append(compact)
                    if len(json.dumps(block,ensure_ascii=False))>MAX_CONTEXT_CHARS-200:
                        block[section].pop();continue
                    chosen.append(item)
                    divergence_count+=item["synthesis_type"]=="divergence"
                if not chosen:continue
                block["report_count"]=len({id for item in chosen for id in item["document_ids"]})
                block["source_organisation_count"]=len({s for item in chosen for s in item["source_organisations"]})
                block["finding_count"]=len({id for item in chosen for id in item["finding_ids"]})
                # Internal counts/evidence stay outside the provider prompt.
                audit={"controlled_test":_controlled_test,"supplied":block,"cards":{str(item["id"]):{"source_organisations":item["source_organisations"],"document_ids":item["document_ids"],"finding_ids":item["finding_ids"]} for item in chosen}}
                return block,audit
    except Exception:
        # Savepoint rollback isolates unavailable synthesis tables/queries.
        return None,None
    return None,None


def index_cards(block):
    return {item["synthesis_card_id"]:item for section in SECTIONS.values() for item in block.get(section,[])}


def validate_interpretations(raw,block):
    output=PulseInterpretationOutput.model_validate(raw)
    cards=index_cards(block);accepted=[];seen=set()
    divergent=[card for card in cards.values() if card["type"]=="divergence"]
    for item in output.interpretations:
        ids=set(item.synthesis_card_ids)
        if not ids or not ids<=cards.keys() or len(ids)!=len(item.synthesis_card_ids):continue
        linked=[cards[id] for id in ids]
        topics={(card["commodity"],card["geography"],card["signal_type"],card["time_horizon"]) for card in linked}
        conflicts=[card for card in divergent if (card["commodity"],card["geography"],card["signal_type"],card["time_horizon"]) in topics]
        if conflicts and (item.relationship!="uncertainty" or not {c["synthesis_card_id"] for c in conflicts}<=ids):continue
        text=item.statement
        numbers=set(re.findall(r"[+-]?\d+(?:,\d{3})*(?:\.\d+)?%?",text))
        available=set(re.findall(r"[+-]?\d+(?:,\d{3})*(?:\.\d+)?%?"," ".join(c["summary"] for c in linked)))
        if not numbers<=available:continue
        if any(c["confidence"]!="High" for c in linked) and re.search(r"(?i)\b(high confidence|certain|proven|guaranteed)\b",text):continue
        if re.search(r"(?i)\b(overall risk|risk score|primary driver)\b.*\b(because|due to|raised|lowered|increased|decreased)\b",text):continue
        if block["stale"]:
            if re.search(r"(?i)\b(current|fresh|recent|today|latest)\b",text):continue
            item=item.model_copy(update={"statement":"Stale source-backed background: "+text})
        fingerprint=(tuple(sorted(ids)),item.relationship)
        if fingerprint in seen:continue
        seen.add(fingerprint);accepted.append(item)
    # Always carry supplied disagreement, even if Gemini omitted it or chose a side.
    for card in divergent:
        id=card["synthesis_card_id"]
        if any(id in item.synthesis_card_ids for item in accepted):continue
        statement=f"Source-backed views differ on {card['commodity']} / {card['geography']} / {card['signal_type']}; preserve uncertainty rather than choosing a direction."
        if block["stale"]:statement="Stale source-backed background: "+statement
        accepted.append(PulseInterpretation(statement=statement,synthesis_card_ids=[id],relationship="uncertainty"))
    divergent_ids={card["synthesis_card_id"] for card in divergent}
    accepted.sort(key=lambda item:not bool(set(item.synthesis_card_ids)&divergent_ids))
    return accepted[:4]


async def enrich(db,provider,analysis,context,*,_controlled_test=False):
    """Only the optional advisor field changes; base interpretation stays intact."""
    block,audit=select_context(db,_controlled_test=_controlled_test)
    if not block:return None
    try:
        compact={"risk_advisor":analysis.risk_advisor_view.model_dump(exclude={"pulse_interpretations"}),
            "deterministic_market_facts":[{key:row.get(key) for key in ("instrument_id","current_value","z_score","provider_symbol","freshness_status")} for row in context.get("market_stats",[])],
            "market_intelligence":block}
        raw=await provider.interpret_risk_advisor_intelligence(compact)
        statements=validate_interpretations(raw,block)
        if not statements:return None
        # Revalidate after the model call: evidence may have changed meanwhile.
        db.expire_all()
        with db.begin_nested():
            run=db.get(Run,block["synthesis_run_id"])
            if not run or run.status!="completed":return None
            _,current=valid_cards(db,run,_controlled_test);valid={item["id"] for item in current}
            if any(not set(item.synthesis_card_ids)<=valid for item in statements):return None
        analysis.risk_advisor_view.pulse_interpretations=statements[:4]
        used=sorted({id for item in statements[:4] for id in item.synthesis_card_ids})
        audit["used_card_ids"]=used
        context["advisor_intelligence"]=audit
        return provenance(db,audit)
    except Exception:
        # Model/retrieval/validation errors cannot erase the normal Risk Advisor.
        return None


def provenance(db,audit,*,now=None):
    if not isinstance(audit,dict) or not audit.get("used_card_ids"):return None
    block=audit.get("supplied");used=audit["used_card_ids"];records=audit.get("cards")
    if not isinstance(block,dict) or not isinstance(records,dict) or not isinstance(used,list):return None
    if not all(isinstance(id,int) for id in used) or not {"synthesis_run_id","generated_at","window_start","window_end","stale"}<=block.keys():return None
    organisations=sorted({s for id in used for s in records.get(str(id),{}).get("source_organisations",[])})
    result={"synthesis_run_id":block["synthesis_run_id"],"synthesis_card_ids":used,"generated_at":block["generated_at"],
        "window_start":block["window_start"],"window_end":block["window_end"],"source_organisation_count":len(organisations),
        "source_organisations":organisations,"signal_count":len(used),"stale":block["stale"],"evidence_status":"unavailable","test_material":bool(audit.get("controlled_test")),
        "card_confidences":{str(id):index_cards(block)[id]["confidence"] for id in used if id in index_cards(block)}}
    try:
        connection=db.connection()
        if connection.dialect.name=="sqlite" and not connection.connection.driver_connection.in_transaction:connection.exec_driver_sql("BEGIN")
        with db.begin_nested():
            run=db.get(Run,block["synthesis_run_id"])
            if run:
                saved,cards=valid_cards(db,run,bool(audit.get("controlled_test")))
                valid={item["id"] for item in cards}
                result["evidence_status"]="current" if set(used)<=valid else "historical_or_invalidated"
                result["stale"]=result["stale"] or is_stale(run,now or datetime.now(timezone.utc)) or saved["stale"]
    except Exception:pass
    return result
