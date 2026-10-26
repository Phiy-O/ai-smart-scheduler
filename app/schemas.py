
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ScheduleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    event_date: date
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    category: Literal["fixed", "focus", "break"] = "fixed"


class ScheduleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    event_date: date | None = None
    start_time: str | None = Field(
        default=None,
        pattern=r"^\d{2}:\d{2}$",
    )
    end_time: str | None = Field(
        default=None,
        pattern=r"^\d{2}:\d{2}$",
    )
    category: Literal["fixed", "focus", "break"] | None = None


class AIInstruction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instruction: str = Field(
        min_length=1,
        max_length=1000,
    )


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    option_id: int = Field(gt=0)
