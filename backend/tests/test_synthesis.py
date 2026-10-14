import asyncio
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from pydantic import SecretStr
import pytest
from sqlalchemy import delete, select
from app.models.intelligence import IntelligenceDocument as Document, IntelligenceChunk as Chunk, IntelligenceFinding as Finding
from app.models.synthesis import IntelligenceSynthesisRun as Run, IntelligenceSynthesis as Item, IntelligenceSynthesisEvidence as Evidence
from app.services import synthesis as service
from app.schemas.synthesis import SynthesisWindow

END=datetime.now(timezone.utc).date()
START=END-timedelta(days=29)


def add_finding(db,source="Argus",direction="bullish",fact=None,days=1,commodity="Brent",geography="Global",horizon="near-term",signal="Supply",confidence="high",status="completed",report_date=True):
    fact=fact or f"Synthetic {source} {direction} assessment."
    doc=Document(source_organisation=source,title=f"Synthetic {source} {db.query(Document).count()}",report_date=END-timedelta(days=days) if report_date else None,
        filename="synthetic.txt",file_type="TXT",mime_type="text/plain",file_hash=service.digest([source,direction,fact,db.query(Document).count()]),storage_path="fixture.txt",processing_status=status,extraction_limitations=[])
    db.add(doc);db.flush()
    chunk=Chunk(document_id=doc.id,chunk_type="txt",source_locator="TXT lines 1–1",text_content=fact,sequence=0)
    db.add(chunk);db.flush()
    finding=Finding(document_id=doc.id,commodity=commodity,geography=geography,signal_type=signal,direction=direction,time_horizon=horizon,key_fact=fact,relevant_numbers=[],driver="Synthetic driver",risk_implication="Synthetic implication",confidence=confidence,source_chunk_id=chunk.id,source_locator=chunk.source_locator,evidence_excerpt=fact)
    db.add(finding);db.flush()
    return finding,doc


class Provider:
    model="synthetic-test-model"
    def __init__(self):self.calls=0
    async def synthesize_intelligence(self,candidates):
        self.calls+=1
        return {"items":[{"candidate_id":c["candidate_id"],"finding_ids":[r["finding_id"] for r in c["findings"]],"summary":c["findings"][0]["key_fact"]} for c in candidates][:20]}


def proposal_rows(db):
    rows,_=service.load_evidence(db,START,END)
    return service.candidates(rows,END)


def test_agreement_counts_organisations_not_findings(db_session):
    f,d=add_finding(db_session)
    add_finding(db_session,"Argus",fact="Synthetic second Argus view.")
    add_finding(db_session,"Kpler")
    proposals,_=proposal_rows(db_session)
    cross=[p for p in proposals if p["synthesis_type"]=="cross_source"]
    assert len(cross)==1
    assert cross[0]["confidence_basis"]["source_organisation_count"]==2
    assert cross[0]["confidence_basis"]["raw_finding_count"]==3
    assert cross[0]["confidence"]=="Medium"


def test_one_source_and_copied_or_attributed_claims_do_not_inflate_agreement(db_session):
    add_finding(db_session,fact="Synthetic oil supply will tighten.")
    add_finding(db_session,"Kpler",fact="Synthetic oil supply will tighten.")
    add_finding(db_session,"S&P Global",fact="According to Argus, synthetic oil supply will tighten.")
    # All reports use one repeated or explicitly attributed claim origin.
    rows,_=service.load_evidence(db_session,START,END)
    assert service.confidence(rows,"cross_source",END)[0]=="Low"
    # An explicit reprint alone cannot establish two-source agreement.
    proposals,_=service.candidates([r for r in rows if r["source_organisation"]!="Kpler"],END)
    assert not any(p["synthesis_type"]=="cross_source" for p in proposals)


@pytest.mark.parametrize("dimension,value",[("geography","Nigeria"),("horizon","long-term"),("commodity","WTI"),("signal","Demand")])
def test_incompatible_dimensions_not_compared(db_session,dimension,value):
    add_finding(db_session)
    add_finding(db_session,"Kpler","bearish",**{dimension:value})
    proposals,_=proposal_rows(db_session)
    assert not any(p["synthesis_type"]=="divergence" for p in proposals)


def test_divergence_and_mixed_are_distinct(db_session):
    add_finding(db_session)
    f,_=add_finding(db_session,"Kpler","bearish")
    proposals,_=proposal_rows(db_session)
    assert next(p for p in proposals if p["synthesis_type"]=="divergence")["direction"]=="Divergent"
    f.direction="neutral";db_session.flush()
    proposals,_=proposal_rows(db_session)
    assert next(p for p in proposals if p["synthesis_type"]=="divergence")["direction"]=="Mixed"


def test_changes_require_earlier_comparable_dated_evidence_and_not_repeats(db_session):
    add_finding(db_session,"Argus","bearish",days=8)
    f,_=add_finding(db_session,"Argus","bullish",days=1)
    proposals,_=proposal_rows(db_session)
    changed=next(p for p in proposals if p["synthesis_type"]=="what_changed")
    assert len(changed["findings"])==2 and "earlier cohort: bearish" in changed["description"]
    f.direction="bearish";db_session.flush()
    proposals,omitted=proposal_rows(db_session)
    assert not any(p["synthesis_type"]=="what_changed" for p in proposals)
    assert omitted["repeated_or_no_direction_change"]==1


def test_unknown_dimensions_are_not_compared_and_low_confidence_can_create_watch(db_session):
    add_finding(db_session,geography="unspecified",confidence="low")
    add_finding(db_session,"Kpler","bearish",geography="unspecified")
    proposals,omitted=proposal_rows(db_session)
    assert not any(p["synthesis_type"]=="divergence" for p in proposals)
    assert any(p["synthesis_type"]=="watch_next" and p["confidence"]=="Low" for p in proposals)
    assert omitted["insufficient_comparability"]==2


def test_confidence_rules_recency_agreement_and_phase1_quality(db_session):
    for source in ("Argus","Kpler","S&P Global"):add_finding(db_session,source)
    rows,_=service.load_evidence(db_session,START,END)
    assert service.confidence(rows,"cross_source",END)[0]=="High"
    rows[0]["confidence"]="low"
    assert service.confidence(rows,"cross_source",END)[0]=="Low"
    rows[0]["confidence"]="medium"
    assert service.confidence(rows,"cross_source",END)[0]=="Medium"
    for r in rows:r["scope_date"]=(END-timedelta(days=40)).isoformat()
    assert service.confidence(rows,"cross_source",END)[0]=="Low"


def test_quantitative_and_nonquantitative_inventions_and_orphan_ids_rejected(db_session):
    add_finding(db_session);add_finding(db_session,"Kpler")
    proposals,_=proposal_rows(db_session);candidate=proposals[0]
    valid={"candidate_id":candidate["candidate_id"],"finding_ids":[r["finding_id"] for r in candidate["findings"]],"summary":candidate["findings"][0]["key_fact"]}
    invalid=[{**valid,"summary":"Price will rise to 999 USD/bbl."},{**valid,"summary":"An invented refinery closed."},{**valid,"finding_ids":[99999]},{**valid,"candidate_id":"invented"}]
    accepted,rejected=service.validate_selections({"items":invalid+[valid]},proposals)
    assert len(accepted)==1 and rejected==4


def test_duplicate_selection_and_evidence_ids_rejected(db_session):
    add_finding(db_session);add_finding(db_session,"Kpler")
    proposals,_=proposal_rows(db_session);c=proposals[0]
    value={"candidate_id":c["candidate_id"],"finding_ids":[r["finding_id"] for r in c["findings"]],"summary":c["findings"][0]["key_fact"]}
    accepted,rejected=service.validate_selections({"items":[value,value,{**value,"finding_ids":value["finding_ids"]*2}]},proposals)
    assert len(accepted)==1 and rejected==2


def test_persistence_regeneration_and_failure_preserves_previous(db_session):
    add_finding(db_session);add_finding(db_session,"Kpler")
    provider=Provider()
    first=asyncio.run(service.refresh(db_session,START,END,provider))
    second=asyncio.run(service.refresh(db_session,START,END,provider))
    assert first.id!=second.id and provider.calls==2
    result=service.serialize(db_session,second)
    assert result["items"] and result["metrics"]["finding_count_used"]==2
    assert result["metrics"]["duration_seconds"]>=0
    for item in result["items"]:
        assert set(item["finding_ids"])=={r["finding_id"] for r in item["evidence"]}
        assert all(r["source_locator"] for r in item["evidence"])
    class Broken(Provider):
        async def synthesize_intelligence(self,candidates):raise RuntimeError("never expose a provider payload")
    failed=asyncio.run(service.refresh(db_session,START,END,Broken()))
    assert failed.status=="failed" and "provider payload" not in failed.error_message
    latest=service.latest(db_session,START,END)
    assert latest["data"]["id"]==second.id and latest["last_attempt"]["status"]=="failed"


def test_no_evidence_and_single_source_weak_states_without_gemini(db_session):
    provider=Provider()
    run=asyncio.run(service.refresh(db_session,START,END,provider))
    assert provider.calls==0 and service.serialize(db_session,run)["items"]==[]
    add_finding(db_session)
    run=asyncio.run(service.refresh(db_session,START,END,provider))
    assert provider.calls==0 and run.metrics["single_source"] is True


def test_only_completed_in_window_and_undated_fallback_disclosed(db_session):
    add_finding(db_session,status="failed")
    add_finding(db_session,"Kpler",days=90)
    add_finding(db_session,"S&P Global",report_date=False)
    rows,total=service.load_evidence(db_session,START,END)
    assert total==1 and rows[0]["date_basis"]=="upload_date"
    assert service.confidence(rows,"cross_source",END)[0]=="Low"


def test_changed_or_deleted_evidence_never_displays_orphan_synthesis(db_session):
    first,_=add_finding(db_session);second,_=add_finding(db_session,"Kpler")
    run=asyncio.run(service.refresh(db_session,START,END,Provider()))
    assert service.serialize(db_session,run)["items"]
    second.key_fact="Changed accepted fact";db_session.commit()
    result=service.serialize(db_session,run)
    assert result["stale"] and result["items"]==[]
    db_session.execute(delete(Finding).where(Finding.id==first.id));db_session.commit()
    assert service.serialize(db_session,run)["items"]==[]


def test_auth_refresh_window_validation_and_get_routes(client,db_session,monkeypatch):
    import app.api.intelligence as api
    monkeypatch.setattr(api,"get_settings",lambda:SimpleNamespace(shipping_admin_token=SecretStr("test-private")))
    payload={"window_start":str(START),"window_end":str(END)}
    assert client.post("/api/intelligence/synthesis/refresh",json=payload).status_code==403
    assert client.post("/api/intelligence/synthesis/refresh",json=payload,headers={"x-intelligence-admin-token":"wrong"}).status_code==403
    good=client.post("/api/intelligence/synthesis/refresh",json=payload,headers={"x-intelligence-admin-token":"test-private"})
    assert good.status_code==200 and good.json()["items"]==[]
    assert client.get("/api/intelligence/synthesis",params=payload).json()["available"]
    assert client.get("/api/intelligence/synthesis/"+str(good.json()["id"])).status_code==200
    assert client.get("/api/intelligence/synthesis/999999").status_code==404
    assert client.get("/api/intelligence/synthesis?window_start=2026-10-10&window_end=2026-10-01").status_code==422
    assert client.post("/api/intelligence/synthesis/refresh",json={**payload,"window_start":"2000-01-01"},headers={"x-intelligence-admin-token":"test-private"}).status_code==422


def test_one_report_many_findings_is_not_cross_source(db_session):
    from copy import copy
    f,d=add_finding(db_session)
    for index in range(4):
        values={key:getattr(f,key) for key in ("document_id","commodity","geography","signal_type","direction","time_horizon","relevant_numbers","driver","risk_implication","confidence","source_chunk_id","source_locator","evidence_excerpt")}
        db_session.add(Finding(**values,key_fact=f"Synthetic same report finding {index}"))
    db_session.flush();rows,_=service.load_evidence(db_session,START,END)
    assert service.confidence(rows,"cross_source",END)[1]["report_count"]==1
    proposals,_=service.candidates(rows,END)
    assert not any(p["synthesis_type"]=="cross_source" for p in proposals)


def test_scope_and_payload_bounds_are_disclosed(db_session):
    for i in range(5):add_finding(db_session,"Argus",geography=f"Synthetic area {i}",confidence="low")
    original=service.MAX_FINDINGS
    try:
        service.MAX_FINDINGS=3
        rows,total=service.load_evidence(db_session,START,END)
        assert len(rows)==3 and total==5
    finally:service.MAX_FINDINGS=original
    for row in rows:row["key_fact"]="Synthetic uncertainty "*6000
    proposals,omitted=service.candidates(rows,END)
    assert proposals==[] and omitted["payload_character_bound"]==3


def test_gemini_synthesis_uses_configured_key_structured_findings_and_closes_client(monkeypatch,caplog):
    import json
    from google import genai
    from app.providers.ai.gemini import GeminiProvider
    captured={}
    class Models:
        async def generate_content(self,**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(text=json.dumps({"items":[]}))
    async def close():captured["closed"]=True
    monkeypatch.setattr(genai,"Client",lambda **kwargs:SimpleNamespace(aio=SimpleNamespace(models=Models(),aclose=close)))
    output=asyncio.run(GeminiProvider(api_key="test-private-key",model="synthetic-model").synthesize_intelligence([]))
    assert output=={"items":[]} and captured["closed"]
    assert 'candidates' in captured["contents"] and 'raw_files' not in captured["contents"]
    assert 'additionalProperties' not in str(captured["config"].response_schema)
    assert 'test-private-key' not in caplog.text


def test_refresh_resolves_existing_gemini_configuration(db_session,monkeypatch):
    add_finding(db_session);add_finding(db_session,"Kpler")
    captured={}
    def factory(**kwargs):captured.update(kwargs);return Provider()
    monkeypatch.setattr(service,"get_settings",lambda:SimpleNamespace(gemini_api_key="synthetic-private-key"))
    monkeypatch.setattr(service,"GeminiProvider",factory)
    run=asyncio.run(service.refresh(db_session,START,END))
    assert run.status=="completed" and captured["api_key"]=="synthetic-private-key"


@pytest.mark.parametrize("url,expected",[("postgresql+psycopg://fixture:synthetic@aws-0-test.pooler.supabase.com:6543/postgres",{"prepare_threshold":None}),("postgresql+psycopg://fixture:synthetic@db.example.com:5432/postgres",{}),("postgresql+psycopg://fixture:synthetic@aws-0-test.pooler.supabase.com:5432/postgres",{})])
def test_transaction_pooler_disables_prepared_statements_only_when_required(monkeypatch,url,expected):
    import app.db.session as session
    captured={}
    monkeypatch.setattr(session,"_engine",None);monkeypatch.setattr(session,"_engine_url",None)
    monkeypatch.setattr(session,"_session_factory",None)
    monkeypatch.setattr(session,"get_settings",lambda:SimpleNamespace(sqlalchemy_database_url=url))
    class Engine:pass
    def create(*args,**kwargs):captured.update(kwargs);return Engine()
    monkeypatch.setattr(session,"create_engine",create)
    monkeypatch.setattr(session,"sessionmaker",lambda **kwargs:object())
    session.get_engine()
    assert captured["connect_args"]==expected


def test_document_replacement_invalidation_removes_cards_and_links(db_session):
    _,d=add_finding(db_session);add_finding(db_session,"Kpler")
    run=asyncio.run(service.refresh(db_session,START,END,Provider()))
    assert db_session.scalar(select(Item.id)) is not None
    service.invalidate_document(db_session,d.id);db_session.flush()
    assert list(db_session.scalars(select(Item)))==[]
    assert list(db_session.scalars(select(Evidence)))==[]
    assert db_session.get(Run,run.id) is not None
