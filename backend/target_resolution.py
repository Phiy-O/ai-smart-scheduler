
from dataclasses import dataclass
from datetime import date, timedelta

from evidence_validation import normalize


@dataclass
class ScheduleEvent:
    id: int
    title: str
    event_date: date
    start_time: str
    end_time: str
    category: str = "fixed"


def sample_events() -> list[ScheduleEvent]:
    today = date.today()
    tomorrow = today + timedelta(days=1)

    return [
        ScheduleEvent(
            101, "Meeting proyek",
            today, "09:00", "10:00"
        ),
        ScheduleEvent(
            102, "Meeting proyek",
            tomorrow, "10:00", "11:00"
        ),
        ScheduleEvent(
            103, "Belajar Python",
            tomorrow, "13:00", "15:00"
        ),
        ScheduleEvent(
            104, "Olahraga",
            tomorrow, "07:00", "08:00"
        ),
        ScheduleEvent(
            105, "Meeting organisasi",
            tomorrow, "15:00", "16:00"
        ),
    ]


def resolve_date(
    reference: str | None,
) -> date | None:

    if reference is None:
        return None

    if reference == "today":
        return date.today()

    if reference == "tomorrow":
        return date.today() + timedelta(days=1)

    raise ValueError("Date reference tidak dikenali")


def resolve_target(
    task_name: str,
    date_reference: str | None,
    events: list[ScheduleEvent],
) -> dict:

    query = normalize(task_name)
    target_date = resolve_date(date_reference)

    if not query:
        return {
            "status": "not_found",
            "candidates": [],
        }

    candidates = []

    for event in events:
        title = normalize(event.title)

        # Token matching sederhana
        query_tokens = set(query.split())
        title_tokens = set(title.split())

        if not query_tokens.issubset(title_tokens):
            continue

        if (
            target_date is not None
            and event.event_date != target_date
        ):
            continue

        candidates.append({
            "id": event.id,
            "title": event.title,
            "date": event.event_date.isoformat(),
            "start": event.start_time,
            "end": event.end_time,
        })

    if len(candidates) == 0:
        status = "not_found"
    elif len(candidates) == 1:
        status = "resolved"
    else:
        status = "ambiguous"

    return {
        "status": status,
        "candidates": candidates,
    }
