"""Synthetic news only; no new publisher integration or live polling."""
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import anyio
import httpx
import pytest
from sqlalchemy import select
from app.providers.news.base import classify_region, classify_source_type, news_audit, fetch_text
from app.providers.news.factory import get_news_providers
from app.services import news_ingestion as service
from app.models.news import NewsItem


@pytest.mark.parametrize("source", ["cnn", "bbc", "synthetic_international", "eia"])
@pytest.mark.parametrize("title,snippet,expected", [
    ("Nigeria crude production rises", "", "nigeria"),
    ("Nigerian refinery resumes fuel output", "", "nigeria"),
    ("Nigeria remains Africa's largest oil producer", "", "nigeria"),
    ("CBN updates naira FX policy", "", "nigeria"),
    ("Angola crude output rises", "Comparison with Nigeria", "africa"),
    ("Nigeria and Angola discuss oil production", "", "africa"),
    ("China and Nigeria discuss bilateral energy trade", "", "international"),
    ("Global crude prices rise", "Nigeria mentioned as an example", "international"),
    ("Energy outlook", "", "international"),
    ("Nigeria crude exports to India rise in September", "", "nigeria"),
    ("Dangote refinery begins importing US crude", "", "nigeria"),
    ("Nigeria's naira weakens against the dollar", "", "nigeria"),
    ("Nigeria oil output rises as China demand recovers", "", "nigeria"),
    ("Brent rises as China demand recovers", "", "international"),
    ("Libya oil exports halted by blockade", "", "africa"),
    ("OPEC+ agrees output cut, Nigeria exempted", "", "international"),
    ("OPEC delegates meet as Nigeria output slips", "", "international"),
    ("Nigeria and India sign crude supply deal", "", "international"),
    ("Nigeria versus Russia in European diesel market", "", "international"),
    ("Russia crude flows to Nigeria", "", "international"),
])
def test_subject_geography_independent_of_publisher(source,title,snippet,expected):
    assert classify_region(source,title,snippet)==expected


@pytest.mark.parametrize("source", ["nuprc", "nnpc"])
@pytest.mark.parametrize("title", ["Licensing round opens", "Energy outlook", "Stakeholder forum announced"])
def test_nigerian_institutional_providers_default_to_nigeria(source, title):
    assert classify_region(source, title, "") == "nigeria"


@pytest.mark.parametrize("key,metadata,expected", [
    ("eia",{},"official_institutional_release"),
    ("nuprc",{},"official_institutional_release"),
    ("nnpc",{},"official_company_release"),
    ("african_energy_chamber",{},"industry_organization_release"),
    ("bbc",{},"independent_media_reporting"),
    ("unknown",{},"unclassified"),
    ("eia",{"article_kind":"analysis"},"commentary_analysis"),
])
def test_source_disclosures(key,metadata,expected):
    assert classify_source_type(key,metadata)==expected


def test_existing_provider_allowlist_unchanged():
    assert {p.source_key for p in get_news_providers()}=={"eia","opec","nuprc","nnpc","african_energy_chamber"}


@pytest.mark.anyio
async def test_overlapping_refresh_is_rejected_and_lock_released(db_session,monkeypatch):
    entered=anyio.Event();finish=anyio.Event();results=[]
    class Slow:
        source_key=source_name="eia"
        async def fetch(self):
            entered.set();await finish.wait();return []
    monkeypatch.setattr(service,"get_news_providers",lambda:[Slow()])
    async def first():results.append(await service.refresh_news(db_session))
    async with anyio.create_task_group() as tasks:
        tasks.start_soon(first);await entered.wait()
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as error:await service.refresh_news(db_session)
        assert error.value.status_code==409
        finish.set()
    assert len(results)==1
    assert service._refresh_lock.acquire(blocking=False)
    service._refresh_lock.release()


@pytest.mark.anyio
async def test_irrelevance_is_not_transport_failure_and_timeouts_are_bounded(db_session,monkeypatch):
    class Irrelevant:
        source_key=source_name="eia"
        async def fetch(self):
            news_audit.get()["candidates"]=1
            news_audit.get()["rejections"]["not_energy_relevant"]=1
            return []
    class Slow:
        source_key=source_name="opec"
        async def fetch(self):await anyio.sleep(1)
    monkeypatch.setattr(service,"PROVIDER_BUDGET_SECONDS",0.01)
    monkeypatch.setattr(service,"get_news_providers",lambda:[Irrelevant(),Slow()])
    result=await service.refresh_news(db_session)
    assert result.sources[0].status=="succeeded"
    assert result.sources[0].outcome=="articles_rejected_irrelevant"
    assert result.sources[1].status=="failed" and result.failed==1


def test_source_types_are_read_time_and_do_not_rewrite_provenance(client,db_session):
    now=datetime.now(timezone.utc)
    record=NewsItem(source_key="african_energy_chamber",source_name="Original AEC",title="Synthetic oil report",
        url="https://example.com/synthetic",published_at=now,retrieved_at=now,region="africa",topic="production",
        metadata_json={"original":"preserved"},active=True)
    db_session.add(record);db_session.commit()
    response=client.get("/api/news/latest?region=africa").json()
    assert response["items"][0]["source_type"]=="industry_organization_release"
    assert response["items"][0]["source_name"]=="Original AEC"
    assert response["diagnostics"]["refresh_attempted"] is False
    assert response["diagnostics"]["empty_reason"] is None
    assert response["diagnostics"]["visible_items"] == 1
    assert db_session.scalar(select(NewsItem)).metadata_json=={"original":"preserved"}


def test_scheduler_defaults_to_no_requests_or_database(capsys):
    spec=importlib.util.spec_from_file_location("news_job",Path(__file__).parents[1]/"scripts/refresh_news.py")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert module.main([])==0
    assert '"enabled": false' in capsys.readouterr().out


@pytest.mark.anyio
async def test_retry_policy_is_opt_in_bounded_and_does_not_retry_forbidden(monkeypatch):
    calls=[];responses=[]
    class Client:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def get(self,url,**kwargs):
            calls.append(url);return responses.pop(0)
    monkeypatch.setattr("app.providers.news.base.httpx.AsyncClient",Client)
    request=httpx.Request("GET","https://example.com/feed")
    responses[:]=[httpx.Response(503,request=request),httpx.Response(200,text="feed",request=request)]
    with pytest.raises(httpx.HTTPStatusError):await fetch_text(str(request.url))
    assert len(calls)==1
    calls.clear();responses[:]=[httpx.Response(403,request=request)]
    with pytest.raises(httpx.HTTPStatusError):await fetch_text(str(request.url),retries=1)
    assert len(calls)==1
    calls.clear();responses[:]=[httpx.Response(503,request=request),httpx.Response(200,text="feed",request=request)]
    assert await fetch_text(str(request.url),retries=1)=="feed" and len(calls)==2
