from datetime import datetime, timezone
from decimal import Decimal
import io

import pytest
from openpyxl import Workbook
from sqlalchemy import select

from app.models.macro import MacroIndicator
from app.providers.macro.base import MacroDataProvider
from app.providers.macro.international import (
    SPECS, observation, parse_bls, parse_fred, parse_bea, parse_eia_stocks,
    parse_imf, parse_china, parse_world_bank, parse_steo,
)
from app.services.macro_ingestion import (
    CANONICAL_MACRO_CONFIG, determine_freshness, get_latest_macro_indicators,
    get_macro_history, run_macro_refresh, upsert_macro_observation, validate_macro_observation,
)
from app.services.ai_context import build_dashboard_ai_context

UTC = timezone.utc


def workbook(sheet, rows):
    book = Workbook(); book.active.title = sheet
    for row in rows: book.active.append(row)
    stream = io.BytesIO(); book.save(stream); book.close()
    return stream.getvalue()


@pytest.mark.parametrize("key,series", [("usa_headline_inflation", "CUUR0000SA0"), ("usa_core_inflation", "CUUR0000SA0L1E")])
def test_bls_yoy_matched_months_missing_and_annual_average(key, series):
    payload = {"status":"REQUEST_SUCCEEDED", "Results":{"series":[{"seriesID":series,"data":[
        {"year":"2026","period":"M08","value":"103.1"},
        {"year":"2025","period":"M08","value":"100"},
        {"year":"2026","period":"M07","value":"105"},
        {"year":"2025","period":"M07","value":"-"},
        {"year":"2026","period":"M13","value":"500"}]}]}}
    rows = parse_bls(payload,key,"https://api.bls.gov/")
    assert len(rows) == 1
    assert rows[0].value == Decimal("3.100")
    assert rows[0].unit == "%" and rows[0].reporting_period == "Aug 2026"
    assert rows[0].metadata_json["year_earlier_index"] == "100"
    payload["Results"]["series"][0]["seriesID"] = "unrelated"
    with pytest.raises(ValueError): parse_bls(payload,key,"url")


def test_unemployment_and_fred_units_dates_and_missing_markers():
    payload={"status":"REQUEST_SUCCEEDED","Results":{"series":[{"seriesID":"LNS14000000","data":[{"year":"2026","period":"M09","value":"4.2"}]}]}}
    assert parse_bls(payload,"usa_unemployment_rate","url")[0].value == Decimal("4.2")
    rows=parse_fred("observation_date,EFFR\n2026-10-01,3.88\n2026-10-02,.\n2026-10-03,\n", "usa_policy_rate", "url")
    assert len(rows)==1 and rows[0].reporting_period=="2026-10-01" and rows[0].unit=="%"
    usd=parse_fred("observation_date,DTWEXBGS\n2026-10-02,121.3848\n","broad_usd_index","url")
    assert usd[0].unit=="index" and usd[0].metadata_json["index_base"]=="January 2006=100"
    with pytest.raises(ValueError):parse_fred("date,other\n2026-10-01,1", "broad_usd_index","url")


def test_bea_quarterly_annual_rate_and_identified_comparison_history():
    rows=[["September 30, 2026"],["2026Q2 Percent Change in Real Gross Domestic Product"],
        ["[Percent] Seasonally adjusted at annual rates"],[],[],
        ["Gross domestic product (GDP)",2.2,"2023Q2",2.2,"2026Q1",2.5,"2025Q4",0.2]]
    result=parse_bea(workbook("GDPhistQ",rows),"url")
    assert len(result)==4 and result[-1].reporting_period=="Q2 2026"
    assert result[-1].value==Decimal("2.2")
    assert "seasonally adjusted annual rate" in result[-1].metadata_json["definition"]
    rows[2]=["Year-on-year"]
    with pytest.raises(ValueError):parse_bea(workbook("GDPhistQ",rows),"url")


def test_eia_excludes_spr_weekly_thousand_to_million_barrels():
    content="""<html><title>Weekly U.S. Ending Stocks excluding SPR of Crude Oil (Thousand Barrels)</title>
    <table><tr><td class="B6">2026-Sep</td><td class="B5">09/25</td><td class="B3">427,320</td>
    <td class="B5">09/18</td><td class="B3">NA</td></tr></table>Release Date: 9/30/2026</html>"""
    result=parse_eia_stocks(content,"url")
    assert len(result)==1 and result[0].value==Decimal("427.32")
    assert result[0].unit=="million barrels" and result[0].reporting_period=="2026-09-25"
    with pytest.raises(ValueError):parse_eia_stocks(content.replace("excluding SPR", "including SPR"),"url")


@pytest.mark.parametrize("key,series",[("global_real_gdp_growth","NGDP_RPCH"),("global_inflation","PCPIPCH")])
def test_imf_only_world_preserves_edition_reference_year_and_forecasts(key,series):
    payload={"values":{series:{"USA":{"2026":90},"WEOWORLD":{"2025":3.4,"2026":3.1,"2031":3.1,"2024":None}}}}
    metadata={"indicators":{series:{"dataset":"WEO","unit":"Annual percent change","label":"Official world metric","source":"World Economic Outlook (April 2026)","last-modified":"2026-04-08 16:07:34"}}}
    result=parse_imf(payload,metadata,key,"url")
    assert len(result)==3 and result[1].value==Decimal("3.1")
    assert result[1].metadata_json["reference_year"]==2026
    assert result[1].metadata_json["forecast"] is True
    assert result[1].published_at.year==2026
    del payload["values"][series]["WEOWORLD"]
    with pytest.raises(ValueError):parse_imf(payload,metadata,key,"url")


def test_china_official_manufacturing_does_not_select_nonmanufacturing():
    content="2026年9月中国采购经理指数运行情况 非制造业采购经理指数为53.1% 制造业采购经理指数（PMI）为50.1%"
    result=parse_china(content,"https://www.stats.gov.cn/sj/zxfbhjd/202609/t20260930_1965449.html")
    assert result[0].value==Decimal("50.1") and result[0].unit=="index"
    assert result[0].reporting_period=="Sep 2026"
    with pytest.raises(ValueError):parse_china(content.split(" 制造业")[0],"url")


def test_world_bank_energy_column_not_total_price_and_month_history():
    rows=[[],["monthly indices 2010=100"],[],["Updated on October 02, 2026"],[],[None,"Total Index","Energy"],
          ["2026M08",121.9,118.5],["2026M09",142.8,148.9],["2026M10",145,None]]
    result=parse_world_bank(workbook("Monthly Indices",rows),"url")
    assert len(result)==2 and result[-1].value==Decimal("148.9")
    assert result[-1].reporting_period=="Sep 2026" and result[-1].unit=="index"
    assert result[-1].published_at==datetime(2026,10,2,tzinfo=UTC)
    rows[1]=["2015=100"]
    with pytest.raises(ValueError):parse_world_bank(workbook("Monthly Indices",rows),"url")


def test_steo_world_consumption_change_definition_not_prices():
    text="Table 3e. World Petroleum and Other Liquid Fuels Consumption (million barrels per day)\n"
    text+="Q1 Q2 Q3 Q4 "*3+"2025 2026 2027\nWorld total .... " + "100.00 "*12 + "104.28 102.59 104.98\n"
    result=parse_steo(text,"Release Date: September 9, 2026","url")
    assert [(r.reporting_period,r.value) for r in result]==[("2026",Decimal("-1.69")),("2027",Decimal("2.39"))]
    assert result[0].unit=="mbpd"
    assert result[0].metadata_json["previous_consumption_mbpd"]=="104.28"
    with pytest.raises(ValueError):parse_steo(text.replace("World total","US total"),"Release Date: September 9, 2026","url")


@pytest.mark.parametrize("key,period,pub,fresh",[
    ("usa_headline_inflation","Aug 2026",None,"fresh"),
    ("usa_unemployment_rate","May 2026",None,"stale"),
    ("usa_real_gdp_growth","Q2 2026",None,"fresh"),
    ("usa_crude_inventories","2026-09-25",None,"fresh"),
    ("usa_crude_inventories","2026-08-28",None,"stale"),
    ("usa_policy_rate","2026-10-05",None,"fresh"),
    ("broad_usd_index","2026-09-01",None,"stale"),
    ("global_real_gdp_growth","2026",datetime(2026,4,8),"fresh"),
    ("global_inflation","2031",datetime(2025,10,1),"stale"),
    ("global_oil_demand_growth","2026",datetime(2026,9,9,tzinfo=UTC),"fresh"),
    ("global_inflation","2026",None,"stale"),
])
def test_cycle_freshness_is_not_reset_by_retrieval(key,period,pub,fresh):
    assert determine_freshness(key,period,pub,datetime(2026,10,6,tzinfo=UTC))==fresh


def test_international_history_order_revision_idempotence_and_current_forecast_selection(db_session):
    current=str(datetime.now(UTC).year)
    for period,value in [("Sep 2026",3.4),("Aug 2026",3.1)]:
        upsert_macro_observation(db_session,observation("usa_headline_inflation",Decimal(str(value)),period,"url"))
    latest={r.indicator_key:r for r in get_latest_macro_indicators(db_session)}
    assert latest["usa_headline_inflation"].reporting_period=="Sep 2026"
    item=observation("usa_headline_inflation",Decimal("3.2"),"Aug 2026","url")
    assert upsert_macro_observation(db_session,item)[1]=="updated"
    assert upsert_macro_observation(db_session,item)[1]=="unchanged"
    history=get_macro_history(db_session,"usa_headline_inflation")
    assert len(history)==2 and history[0].reporting_period=="Sep 2026"
    assert history[1].metadata_json["revision_history"][0]["previous_value"]==3.1
    for year in [current,str(int(current)+5)]:
        upsert_macro_observation(db_session,observation("global_real_gdp_growth",Decimal("3.1"),year,"url",datetime.now(UTC)))
    latest={r.indicator_key:r for r in get_latest_macro_indicators(db_session)}
    assert latest["global_real_gdp_growth"].reporting_period==current
    assert len(get_macro_history(db_session,"global_real_gdp_growth"))==2


@pytest.mark.anyio
async def test_partial_failures_preserve_last_verified_and_store_other_indicators(db_session):
    prior=observation("usa_policy_rate",Decimal("3.88"),"2026-10-05","url")
    upsert_macro_observation(db_session,prior)
    class Broken(MacroDataProvider):
        provider_name="broken policy rate"
        async def fetch_latest(self):raise ValueError("publisher inaccessible")
    class Good(MacroDataProvider):
        provider_name="BLS"
        async def fetch_latest(self):return [
            observation("usa_unemployment_rate",None,"Sep 2026","url"),
            observation("usa_headline_inflation",Decimal("3.1"),"Aug 2026","url")]
    result=await run_macro_refresh(db_session,[Broken(),Good()])
    assert result.failed==2 and result.stored==1
    latest={r.indicator_key:r for r in get_latest_macro_indicators(db_session)}
    assert latest["usa_policy_rate"].value==3.88
    assert latest["usa_headline_inflation"].value==3.1
    assert latest["usa_unemployment_rate"].value is None
    assert latest["usa_unemployment_rate"].freshness_status=="unavailable"


@pytest.mark.parametrize("value",[None,Decimal("NaN"),float("inf")])
def test_invalid_values_never_become_zero(value):
    with pytest.raises(ValueError):validate_macro_observation(observation("usa_headline_inflation",value,"Aug 2026","url"))


def test_gemini_geography_context_is_verified_and_preserves_missing(db_session):
    upsert_macro_observation(db_session,observation("usa_headline_inflation",Decimal("3.1"),"Aug 2026","https://api.bls.gov/"))
    context=build_dashboard_ai_context(db_session)
    assert set(context["macro"])=={"nigeria","usa","global"}
    assert all(len(items)==6 for items in context["macro"].values())
    usa={r["indicator"]:r for r in context["macro"]["usa"]}
    assert usa["usa_headline_inflation"]["geography"]=="usa"
    assert usa["usa_headline_inflation"]["value"]==3.1
    assert usa["usa_core_inflation"]["value"] is None
    assert usa["usa_core_inflation"]["freshness"]=="unavailable"
    assert context["analysis_rules"]["macro_values_are_verified_backend_observations"]
    assert len(CANONICAL_MACRO_CONFIG)==18


def test_china_monthly_history_and_source_direction():
    content="""2026年9月中国采购经理指数运行情况 制造业采购经理指数（PMI）为50.1%
    <table><tr><td></td><td>PMI</td></tr><tr><td>2026年8月</td><td>49.8</td></tr>
    <tr><td>2026年9月</td><td>50.1</td></tr></table>"""
    rows=parse_china(content,"https://www.stats.gov.cn/sj/zxfbhjd/202609/t20260930_1965449.html")
    assert len(rows)==2 and rows[0].reporting_period=="Aug 2026"
    assert rows[-1].metadata_json["change"]==0.3
    assert rows[-1].metadata_json["direction"]=="up"
