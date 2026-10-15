"""Synthetic, isolated evidence only; production-labelled mock metadata never leaves test DB."""
import asyncio
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
import json
import pytest
from sqlalchemy import select,text,delete
from app.services import advisor_intelligence as integration, synthesis
from app.schemas.ai import AIAnalysisOutput
from app.models.synthesis import IntelligenceSynthesisRun as Run, IntelligenceSynthesis as Item
from app.models.ai import AIAnalysis
from backend.tests.test_synthesis import add_finding,Provider,START,END
from backend.tests.test_ai_phase6 import VALID_ANALYSIS


def build_run(db,*,divergent=False,synthetic=False):
    for source,direction in [("Argus","bullish"),("Kpler","bullish")]+([("S&P Global","bearish")] if divergent else []):
        f,d=add_finding(db,source,direction,fact=f"{source} assessment: available supply may {'expand' if direction=='bearish' else 'tighten'} under stated assumptions.")
        if not synthetic:
            d.title=f"{source} supply assessment";d.filename="supply-assessment.txt"
    db.flush()
    return asyncio.run(synthesis.refresh(db,START,END,Provider()))


class Advisor:
    def __init__(self):self.received=None
    async def interpret_risk_advisor_intelligence(self,context):
        self.received=context
        block=context["market_intelligence"];cards=integration.index_cards(block)
        card=next(c for c in cards.values() if c["type"]=="cross_source")
        return {"interpretations":[{"statement":"Source-backed intelligence reinforces monitoring of supply exposure without changing the deterministic assessment.","synthesis_card_ids":[card["synthesis_card_id"]],"relationship":"support"}]}


def test_valid_persisted_context_is_compact_and_preserves_ids_counts(db_session):
    run=build_run(db_session)
    block,audit=integration.select_context(db_session)
    assert block["synthesis_run_id"]==run.id and block["source_organisation_count"]==2
    assert block["report_count"]==2 and block["finding_count"]==2
    assert len(json.dumps(block))<=integration.MAX_CONTEXT_CHARS
    assert not any(key in json.dumps(block) for key in ["evidence_excerpt","source_locator","source_chunks","file_hash"])
    assert all(card["confidence"]=="Medium" for card in integration.index_cards(block).values())


def test_enrichment_changes_only_optional_advisor_interpretations(db_session):
    build_run(db_session);provider=Advisor();analysis=AIAnalysisOutput.model_validate(deepcopy(VALID_ANALYSIS));before=analysis.model_dump()
    context={"market_stats":[]}
    provenance=asyncio.run(integration.enrich(db_session,provider,analysis,context))
    assert provenance["source_organisation_count"]==2 and provenance["evidence_status"]=="current"
    assert provenance["synthesis_card_ids"]==analysis.risk_advisor_view.pulse_interpretations[0].synthesis_card_ids
    after=analysis.model_dump();after["risk_advisor_view"]["pulse_interpretations"]=[]
    assert before==after
    assert "market_intelligence" in provider.received and "market_intelligence" not in context
    assert context["advisor_intelligence"]["used_card_ids"]==provenance["synthesis_card_ids"]


def test_empty_context_keeps_normal_advisor_without_model_call(db_session):
    provider=Advisor();analysis=AIAnalysisOutput.model_validate(VALID_ANALYSIS)
    assert asyncio.run(integration.enrich(db_session,provider,analysis,{})) is None
    assert provider.received is None and not analysis.risk_advisor_view.pulse_interpretations


def test_stale_generation_and_old_window_are_both_labelled(db_session):
    run=build_run(db_session);run.generated_at=datetime.now(timezone.utc)-timedelta(hours=100);db_session.commit()
    block,_=integration.select_context(db_session)
    assert block["stale"]
    cards=integration.index_cards(block);id=next(iter(cards))
    result=integration.validate_interpretations({"interpretations":[{"statement":"Historical evidence adds context to supply monitoring.","synthesis_card_ids":[id],"relationship":"background"}]},block)
    assert result[0].statement.startswith("Stale source-backed background:")
    assert integration.validate_interpretations({"interpretations":[{"statement":"Recent reports confirm the current outlook.","synthesis_card_ids":[id],"relationship":"support"}]},block)==[]
    run.generated_at=datetime.now(timezone.utc);run.window_end=END-timedelta(days=10)
    assert integration.is_stale(run,datetime.now(timezone.utc))


def test_configurable_freshness_limit(db_session,monkeypatch):
    run=build_run(db_session);run.generated_at=datetime.now(timezone.utc)-timedelta(hours=12)
    monkeypatch.setattr(integration,"get_settings",lambda:SimpleNamespace(risk_advisor_pulse_freshness_hours=6))
    assert integration.is_stale(run,datetime.now(timezone.utc))


def test_divergence_cannot_be_silently_reconciled(db_session):
    build_run(db_session,divergent=True);analysis=AIAnalysisOutput.model_validate(VALID_ANALYSIS)
    context={};provenance=asyncio.run(integration.enrich(db_session,Advisor(),analysis,context))
    assert provenance and provenance["source_organisation_count"]==3
    statements=analysis.risk_advisor_view.pulse_interpretations
    assert statements and all(item.relationship=="uncertainty" for item in statements)
    assert "uncertainty" in statements[0].statement
    assert all(integration.index_cards(context["advisor_intelligence"]["supplied"])[id]["type"]=="divergence" for id in provenance["synthesis_card_ids"])


def test_low_confidence_excluded(db_session):
    run=build_run(db_session)
    for item in db_session.scalars(select(Item).where(Item.run_id==run.id)):item.confidence="Low"
    db_session.commit()
    assert integration.select_context(db_session)==(None,None)


def test_synthetic_fixture_documents_excluded_in_every_environment(db_session,monkeypatch):
    build_run(db_session,synthetic=True)
    assert integration.select_context(db_session)==(None,None)
    assert integration.select_context(db_session,_controlled_test=True)[0]


def test_card_containing_one_synthetic_document_is_excluded_whole(db_session):
    run=build_run(db_session)
    from app.models.intelligence import IntelligenceDocument as Document
    doc=db_session.scalar(select(Document).where(Document.source_organisation=="Argus"))
    doc.filename="synthetic-fixture.txt";db_session.commit()
    # Evidence fingerprint includes title, so retain title and test filename classification alone.
    assert integration.select_context(db_session)==(None,None)


def test_invalidated_cards_omitted_and_saved_provenance_marked_historical(db_session):
    run=build_run(db_session);analysis=AIAnalysisOutput.model_validate(VALID_ANALYSIS);context={}
    provenance=asyncio.run(integration.enrich(db_session,Advisor(),analysis,context))
    assert provenance
    db_session.execute(delete(Item).where(Item.id.in_(provenance["synthesis_card_ids"])));db_session.commit()
    fresh=integration.provenance(db_session,context["advisor_intelligence"])
    assert fresh["evidence_status"]=="historical_or_invalidated"
    assert analysis.risk_advisor_view.pulse_interpretations


def test_synthesis_sql_failure_does_not_poison_main_session(db_session,monkeypatch):
    build_run(db_session)
    def broken(*args):db_session.execute(text("select * from intentionally_missing_synthesis_table"))
    monkeypatch.setattr(synthesis,"serialize",broken)
    assert integration.select_context(db_session)==(None,None)
    assert db_session.scalar(text("select 1"))==1


def test_optional_model_failure_does_not_erase_base_analysis(db_session):
    build_run(db_session)
    class Broken(Advisor):
        async def interpret_risk_advisor_intelligence(self,context):raise RuntimeError("never expose provider detail")
    analysis=AIAnalysisOutput.model_validate(VALID_ANALYSIS);context={}
    assert asyncio.run(integration.enrich(db_session,Broken(),analysis,context)) is None
    assert analysis.model_dump()==VALID_ANALYSIS and "advisor_intelligence" not in context


def test_invented_ids_numbers_and_confidence_upgrades_are_rejected(db_session):
    build_run(db_session);block,_=integration.select_context(db_session);id=next(iter(integration.index_cards(block)))
    def output(statement,ids=None):return {"interpretations":[{"statement":statement,"synthesis_card_ids":ids or [id],"relationship":"context"}]}
    assert integration.validate_interpretations(output("Invented supply volume 999."),block)==[]
    assert integration.validate_interpretations(output("High confidence outlook."),block)==[]
    assert integration.validate_interpretations(output("A claim.",[999999]),block)==[]


def test_read_default_window_preferred_and_future_runs_ignored(db_session):
    old=build_run(db_session)
    newer=Run(window_start=END-timedelta(days=6),window_end=END,status="completed",model_version="fixture",input_hash=old.input_hash,metrics=old.metrics)
    db_session.add(newer);db_session.flush()
    for item in list(db_session.scalars(select(Item).where(Item.run_id==old.id))):item.run_id=newer.id
    db_session.commit()
    assert integration.select_context(db_session)[0]["synthesis_run_id"]==newer.id
    newer.window_end=END+timedelta(days=1);db_session.commit()
    assert integration.select_context(db_session)==(None,None)


def test_full_endpoint_persists_used_context_and_loads_saved_record(client,db_session,seed_test_data,monkeypatch):
    build_run(db_session)
    class Full(Advisor):
        async def analyse_dashboard(self,context):
            assert "market_intelligence" not in context and "advisor_intelligence" not in context
            return {"status":"completed","configured":True,"provider":"gemini","model":"synthetic","analysis":deepcopy(VALID_ANALYSIS)}
    monkeypatch.setattr("app.api.ai.get_ai_provider",lambda:Full())
    response=client.post("/api/ai/analyse",json={"context":{"advisor_intelligence":{"controlled_test":True}}})
    assert response.status_code==200
    result=response.json();assert result["pulse_provenance"]["synthesis_card_ids"]
    record=db_session.scalar(select(AIAnalysis).order_by(AIAnalysis.id.desc()))
    assert record.input_context_json["advisor_intelligence"]["used_card_ids"]==result["pulse_provenance"]["synthesis_card_ids"]
    assert client.get("/api/ai/latest").json()["pulse_provenance"]["synthesis_card_ids"]==result["pulse_provenance"]["synthesis_card_ids"]


def test_snapshot_risk_inputs_unchanged_by_bullish_and_bearish_context(db_session,seed_test_data):
    from app.api.dashboard import get_dashboard_snapshot
    before=get_dashboard_snapshot(db_session).model_dump(mode="json")
    build_run(db_session,divergent=True)
    assert integration.select_context(db_session)[0]
    after=get_dashboard_snapshot(db_session).model_dump(mode="json")
    for payload in [before,after]:payload.pop("generated_at")
    assert before==after



def test_evidence_invalidated_during_model_call_cannot_be_used(db_session):
    build_run(db_session)
    class Invalidating(Advisor):
        async def interpret_risk_advisor_intelligence(self,context):
            output=await super().interpret_risk_advisor_intelligence(context)
            db_session.execute(delete(Item));db_session.flush()
            return output
    analysis=AIAnalysisOutput.model_validate(VALID_ANALYSIS);context={}
    assert asyncio.run(integration.enrich(db_session,Invalidating(),analysis,context)) is None
    assert not analysis.risk_advisor_view.pulse_interpretations and "advisor_intelligence" not in context


def test_post_model_read_failure_is_also_transaction_isolated(db_session,monkeypatch):
    build_run(db_session);original=integration.valid_cards;calls=[0]
    def broken(db,*args):
        calls[0]+=1
        if calls[0]==2:db.execute(text("select * from intentionally_missing_advisor_table"))
        return original(db,*args)
    monkeypatch.setattr(integration,"valid_cards",broken)
    analysis=AIAnalysisOutput.model_validate(VALID_ANALYSIS)
    assert asyncio.run(integration.enrich(db_session,Advisor(),analysis,{})) is None
    assert db_session.scalar(text("select 1"))==1


def test_no_pulse_or_low_confidence_can_never_forge_a_base_provider_citation(client,db_session,seed_test_data,monkeypatch):
    class Forged:
        async def analyse_dashboard(self,context):
            analysis=deepcopy(VALID_ANALYSIS)
            analysis["risk_advisor_view"]["pulse_interpretations"]=[{"statement":"Invented linkage","synthesis_card_ids":[999999],"relationship":"support"}]
            return {"status":"completed","configured":True,"analysis":analysis}
    monkeypatch.setattr("app.api.ai.get_ai_provider",lambda:Forged())
    response=client.post("/api/ai/analyse",json={}).json()
    assert response["pulse_provenance"] is None and response["analysis"]["risk_advisor_view"]["pulse_interpretations"]==[]


def test_advisor_sdk_uses_strict_citation_schema_and_closes_client(monkeypatch):
    from google import genai
    from app.providers.ai.gemini import GeminiProvider
    captured={}
    class Models:
        async def generate_content(self,**kwargs):captured.update(kwargs);return SimpleNamespace(text='{"interpretations":[]}')
    async def close():captured["closed"]=True
    monkeypatch.setattr(genai,"Client",lambda **kwargs:SimpleNamespace(aio=SimpleNamespace(models=Models(),aclose=close)))
    output=asyncio.run(GeminiProvider(api_key="test-private-key",model="fixture-model").interpret_risk_advisor_intelligence({"market_intelligence":{}}))
    assert output=={"interpretations":[]} and captured["closed"]
    assert "synthesis_card_ids" in str(captured["config"].response_schema)
    assert "test-private-key" not in captured["contents"]


@pytest.mark.parametrize("audit",[None,"old metadata",{"used_card_ids":[1]}, {"used_card_ids":"not-a-list","supplied":{},"cards":{}}])
def test_missing_or_malformed_optional_saved_metadata_does_not_break_old_advice(db_session,audit):
    assert integration.provenance(db_session,audit) is None
