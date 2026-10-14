from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

SOURCES=["Argus","S&P Global","Kpler","CSCS","Other"]
SIGNALS=["Price","Supply","Demand","Refining","Inventory","Shipping/flows","OPEC+","Sanctions","Geopolitics","FX","Macro","Forecast","Maintenance/outage","Other"]
DIRECTIONS=["bullish","bearish","neutral","mixed","unclear"]


class IntelligenceFindingOutput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    source_organisation: Literal["Argus","S&P Global","Kpler","CSCS","Other"]
    document_title: str = Field(min_length=1,max_length=255)
    report_date: str | None
    commodity: str = Field(min_length=1,max_length=120)
    geography: str = Field(min_length=1,max_length=120)
    signal_type: Literal["Price","Supply","Demand","Refining","Inventory","Shipping/flows","OPEC+","Sanctions","Geopolitics","FX","Macro","Forecast","Maintenance/outage","Other"]
    direction: Literal["bullish","bearish","neutral","mixed","unclear"]
    time_horizon: str = Field(min_length=1,max_length=120)
    key_fact: str = Field(min_length=1,max_length=1500)
    relevant_numbers: list[str] = Field(max_length=20)
    driver: str = Field(max_length=1500)
    risk_implication: str = Field(max_length=1500)
    confidence: Literal["low","medium","high"]
    source_chunk_id: int
    source_locator: str = Field(min_length=1,max_length=500)
    evidence_excerpt: str = Field(min_length=1,max_length=3000)

    @field_validator("direction","confidence",mode="before")
    @classmethod
    def lower(cls,value): return value.strip().lower() if isinstance(value,str) else value

    @field_validator("signal_type",mode="before")
    @classmethod
    def signal(cls,value):
        if isinstance(value,str):
            for canonical in SIGNALS:
                if value.replace(" ","").casefold()==canonical.replace(" ","").casefold(): return canonical
        return value


class IntelligenceResponse(BaseModel):
    model_config=ConfigDict(extra="forbid")
    findings: list[IntelligenceFindingOutput] = Field(max_length=40)
