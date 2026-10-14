from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class SynthesisWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    window_start: date
    window_end: date

    @model_validator(mode="after")
    def valid_window(self):
        if self.window_start > self.window_end:
            raise ValueError("Start must be on or before end.")
        if (self.window_end - self.window_start).days > 365:
            raise ValueError("Synthesis windows are limited to 366 inclusive days.")
        return self


class SynthesisSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_id: str = Field(max_length=40)
    finding_ids: list[int] = Field(min_length=1, max_length=60)
    # Extractive summary only: local validation requires an exact contributing key_fact.
    summary: str = Field(min_length=1, max_length=1500)


class SynthesisOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[SynthesisSelection] = Field(max_length=20)
