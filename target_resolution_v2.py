
from dataclasses import dataclass
from datetime import date
from enum import Enum
import re
import unicodedata

from target_resolution import ScheduleEvent


class ResolutionStatus(str, Enum):
    MATCHED = "matched"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True)
class TargetQuery:
    title: str | None = None
    event_date: date | None = None
    start_time: str | None = None
    period: str | None = None


@dataclass
class ResolutionResult:
    status: ResolutionStatus
    candidates: list[ScheduleEvent]
    reason: str


PERIOD_RANGES = {
    "morning": (5 * 60, 12 * 60),
    "afternoon": (12 * 60, 17 * 60),
    "evening": (17 * 60, 24 * 60),
}


def normalize_title(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = value.casefold()
    value = re.sub(r"[^\w\s]", " ", value)
    return " ".join(value.split())


def title_matches(query: str, event_title: str) -> bool:
    query_words = normalize_title(query).split()
    title_words = normalize_title(event_title).split()

    if not query_words:
        return False

    # Require the query to appear as a contiguous
    # sequence of complete words.
    size = len(query_words)

    return any(
        title_words[i:i + size] == query_words
        for i in range(len(title_words) - size + 1)
    )


def time_to_minutes(value: str) -> int:
    hour, minute = map(int, value.split(":"))

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("Invalid time")

    return hour * 60 + minute


class TargetResolverV2:
    def resolve(
        self,
        query: TargetQuery,
        events: list[ScheduleEvent],
    ) -> ResolutionResult:

        if (
            not query.title
            or not normalize_title(query.title)
        ):
            return ResolutionResult(
                status=ResolutionStatus.INSUFFICIENT_EVIDENCE,
                candidates=[],
                reason="Target title is required",
            )

        if query.period is not None:
            if query.period not in PERIOD_RANGES:
                return ResolutionResult(
                    status=ResolutionStatus.INSUFFICIENT_EVIDENCE,
                    candidates=[],
                    reason="Unknown time period",
                )

        if query.start_time is not None:
            try:
                time_to_minutes(query.start_time)
            except (ValueError, AttributeError):
                return ResolutionResult(
                    status=ResolutionStatus.INSUFFICIENT_EVIDENCE,
                    candidates=[],
                    reason="Invalid target start time",
                )

        candidates = []

        for event in events:
            if (
                query.event_date is not None
                and event.event_date != query.event_date
            ):
                continue

            if not title_matches(query.title, event.title):
                continue

            if (
                query.start_time is not None
                and event.start_time != query.start_time
            ):
                continue

            if query.period is not None:
                start, end = PERIOD_RANGES[query.period]
                event_minutes = time_to_minutes(
                    event.start_time
                )

                if not start <= event_minutes < end:
                    continue

            candidates.append(event)

        candidates.sort(
            key=lambda event: (
                event.event_date,
                event.start_time,
                event.id,
            )
        )

        if not candidates:
            return ResolutionResult(
                status=ResolutionStatus.NOT_FOUND,
                candidates=[],
                reason="No matching schedule found",
            )

        if len(candidates) > 1:
            return ResolutionResult(
                status=ResolutionStatus.AMBIGUOUS,
                candidates=candidates,
                reason="Multiple schedules match",
            )

        return ResolutionResult(
            status=ResolutionStatus.MATCHED,
            candidates=candidates,
            reason="Exactly one schedule matched",
        )
