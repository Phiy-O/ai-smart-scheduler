
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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

class PreferencesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day_start: str = Field(pattern=r"^\d{2}:\d{2}$")
    day_end: str = Field(pattern=r"^\d{2}:\d{2}$")

    productive_periods: list[
        Literal["morning", "afternoon", "evening"]
    ]

    avoid_periods: list[
        Literal["morning", "afternoon", "evening"]
    ]

    min_break_minutes: int = Field(ge=0, le=120)
    max_focus_minutes: int = Field(ge=15, le=480)

    @field_validator("day_start", "day_end")
    @classmethod
    def validate_clock(cls, value):
        hour, minute = map(int, value.split(":"))

        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("Invalid clock time")

        return value

    @model_validator(mode="after")
    def validate_preferences(self):
        from scheduling_engine import to_minutes

        if to_minutes(self.day_start) >= to_minutes(self.day_end):
            raise ValueError(
                "day_end must be later than day_start"
            )

        if len(set(self.productive_periods)) != len(
            self.productive_periods
        ):
            raise ValueError(
                "Duplicate productive periods"
            )

        if len(set(self.avoid_periods)) != len(
            self.avoid_periods
        ):
            raise ValueError(
                "Duplicate avoided periods"
            )

        if set(self.productive_periods) & set(self.avoid_periods):
            raise ValueError(
                "Productive and avoided periods cannot overlap"
            )

        return self
