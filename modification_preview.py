
from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class ModificationAction(str, Enum):
    UPDATE = "update"
    RESCHEDULE = "reschedule"
    DELETE = "delete"


@dataclass(frozen=True)
class ModificationRequest:
    action: ModificationAction

    # Identitas jadwal lama yang ingin diubah.
    target_title: str
    target_date: date | None = None
    target_start_time: str | None = None
    target_period: str | None = None

    # Nilai baru, tidak digunakan untuk pencarian target.
    new_title: str | None = None
    new_date: date | None = None
    new_start_time: str | None = None
    
    new_duration_minutes: int | None = None
    new_period: str | None = None


@dataclass
class ModificationPreview:
    status: str
    action: str
    target_id: int | None = None

    before: dict | None = None
    after: dict | None = None

    candidates: list[dict] = field(default_factory=list)
    reason: str | None = None
