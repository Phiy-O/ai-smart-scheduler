
from dataclasses import dataclass, field
from datetime import date

from target_resolution import ScheduleEvent


def to_minutes(value: str) -> int:
    hour, minute = map(int, value.split(":"))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("Invalid time")
    return hour * 60 + minute


def to_time(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


PERIODS = {
    "morning": (8 * 60, 12 * 60),
    "afternoon": (12 * 60, 17 * 60),
    "evening": (17 * 60, 20 * 60),
}


@dataclass
class UserPreferences:
    day_start: str = "08:00"
    day_end: str = "20:00"
    productive_periods: list[str] = field(
        default_factory=lambda: ["morning", "afternoon"]
    )
    avoid_periods: list[str] = field(
        default_factory=lambda: ["evening"]
    )
    min_break_minutes: int = 15
    max_focus_minutes: int = 120


@dataclass
class ScheduleRequest:
    title: str
    event_date: date
    duration_minutes: int
    preferred_period: str | None = None


@dataclass
class ScheduleSuggestion:
    title: str
    date: str
    start: str
    end: str
    score: float
    reasons: list[str]


class SchedulingEngine:
    def __init__(self, preferences: UserPreferences):
        self.preferences = preferences

    def get_period(self, minute: int) -> str:
        for name, (start, end) in PERIODS.items():
            if start <= minute < end:
                return name
        return "other"

    def is_allowed(self, start: int, end: int) -> bool:
        # A slot cannot overlap a disallowed period.
        for name in self.preferences.avoid_periods:
            blocked_start, blocked_end = PERIODS[name]
            if start < blocked_end and end > blocked_start:
                return False
        return True

    def has_conflict(
        self,
        start: int,
        end: int,
        events: list[ScheduleEvent],
    ) -> bool:
        gap = self.preferences.min_break_minutes

        for event in events:
            busy_start = to_minutes(event.start_time)
            busy_end = to_minutes(event.end_time)

            # Break tetap merupakan waktu yang tidak boleh ditimpa.
            # Tetapi tidak memerlukan buffer tambahan.
            event_gap = 0 if event.category == "break" else gap

            if (
                start < busy_end + event_gap
                and end > busy_start - event_gap
            ):
                return True

        return False

    def score_slot(
        self,
        start: int,
        end: int,
        request: ScheduleRequest,
    ) -> tuple[float, list[str]]:
        score = 0.0
        reasons = []

        midpoint = (start + end) // 2
        period = self.get_period(midpoint)

        if period in self.preferences.productive_periods:
            score += 30
            reasons.append("Sesuai waktu produktif pengguna")

        if request.preferred_period == period:
            score += 50
            reasons.append("Sesuai preferensi waktu aktivitas")

        # Small tie-breaker: prefer earlier times.
        day_start = to_minutes(self.preferences.day_start)
        score += max(0, (1200 - (start - day_start)) / 120)

        return round(score, 2), reasons

    def recommend(
        self,
        request: ScheduleRequest,
        events: list[ScheduleEvent],
        limit: int = 3,
    ) -> list[ScheduleSuggestion]:

        prefs = self.preferences

        if request.duration_minutes <= 0:
            raise ValueError("Duration must be positive")

        if request.duration_minutes > prefs.max_focus_minutes:
            return []

        start_day = to_minutes(prefs.day_start)
        end_day = to_minutes(prefs.day_end)

        if end_day <= start_day:
            raise ValueError("Day end must follow day start")

        if prefs.min_break_minutes < 0:
            raise ValueError("Break duration cannot be negative")

        if request.preferred_period is not None:
            if request.preferred_period not in PERIODS:
                raise ValueError("Invalid preferred period")

        for period in (
            prefs.productive_periods + prefs.avoid_periods
        ):
            if period not in PERIODS:
                raise ValueError("Unknown period")

        today_events = [
            event for event in events
            if event.event_date == request.event_date
        ]

        candidates = []

        # Every 15 minutes is a possible start time.
        for start in range(
            start_day,
            end_day - request.duration_minutes + 1,
            15,
        ):
            end = start + request.duration_minutes

            if not self.is_allowed(start, end):
                continue

            if self.has_conflict(start, end, today_events):
                continue

            score, reasons = self.score_slot(
                start, end, request
            )

            candidates.append(
                ScheduleSuggestion(
                    title=request.title,
                    date=request.event_date.isoformat(),
                    start=to_time(start),
                    end=to_time(end),
                    score=score,
                    reasons=reasons,
                )
            )

        candidates.sort(
            key=lambda item: (
                -item.score,
                item.start,
            )
        )

        # Alternatives may overlap, but should have
        # sufficiently different starting times.
        min_separation = 45

        selected = []

        for candidate in candidates:
            start = to_minutes(candidate.start)

            if all(
                abs(start - to_minutes(item.start)) >= min_separation
                for item in selected
            ):
                selected.append(candidate)

            if len(selected) >= limit:
                break

        return selected
