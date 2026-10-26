
from datetime import date

from scheduling_engine import (
    SchedulingEngine,
    ScheduleRequest,
    UserPreferences,
    to_minutes,
)

from target_resolution import ScheduleEvent


TEST_DATE = date(2026, 10, 26)


def make_engine():
    return SchedulingEngine(
        UserPreferences(
            day_start="08:00",
            day_end="20:00",
            productive_periods=["morning", "afternoon"],
            avoid_periods=["evening"],
            min_break_minutes=15,
            max_focus_minutes=120,
        )
    )


def test_no_overlap():
    events = [
        ScheduleEvent(
            1, "Kuliah", TEST_DATE, "08:00", "12:00"
        )
    ]

    request = ScheduleRequest(
        "Belajar Python", TEST_DATE, 120, "afternoon"
    )

    suggestions = make_engine().recommend(
        request, events
    )

    assert suggestions

    for suggestion in suggestions:
        assert to_minutes(suggestion.start) >= 12 * 60 + 15


def test_no_evening():
    request = ScheduleRequest(
        "Belajar Python", TEST_DATE, 120
    )

    suggestions = make_engine().recommend(request, [])

    assert suggestions
    assert all(
        to_minutes(s.end) <= 17 * 60
        for s in suggestions
    )


def test_reject_excessive_focus_duration():
    request = ScheduleRequest(
        "Belajar Python", TEST_DATE, 180
    )

    suggestions = make_engine().recommend(request, [])

    assert suggestions == []


def test_no_available_slots():
    events = [
        ScheduleEvent(
            1, "Full day", TEST_DATE, "08:00", "17:00"
        )
    ]

    request = ScheduleRequest(
        "Belajar Python", TEST_DATE, 60
    )

    suggestions = make_engine().recommend(
        request, events
    )

    assert suggestions == []


def test_date_isolation():
    events = [
        ScheduleEvent(
            1, "Other day", date(2026, 10, 27),
            "08:00", "17:00"
        )
    ]

    request = ScheduleRequest(
        "Belajar Python", TEST_DATE, 60
    )

    assert make_engine().recommend(request, events)

def test_break_does_not_add_extra_buffer():
    events = [
        ScheduleEvent(
            1, "Kuliah", TEST_DATE,
            "08:00", "12:00"
        ),
        ScheduleEvent(
            2, "Istirahat", TEST_DATE,
            "12:00", "13:00",
            category="break"
        ),
    ]

    request = ScheduleRequest(
        "Belajar Python",
        TEST_DATE,
        120,
        "afternoon"
    )

    suggestions = make_engine().recommend(
        request, events
    )

    assert suggestions
    assert suggestions[0].start == "13:00"
    
def test_suggestions_have_minimum_separation():
    request = ScheduleRequest(
        "Belajar Python", TEST_DATE, 60
    )

    suggestions = make_engine().recommend(request, [])

    assert len(suggestions) == 3

    for i, first in enumerate(suggestions):
        for second in suggestions[i + 1:]:
            start_difference = abs(
                to_minutes(first.start)
                - to_minutes(second.start)
            )

            assert start_difference >= 45
            
def test_suggestions_do_not_conflict_with_events():
    events = [
        ScheduleEvent(
            1, "Kuliah", TEST_DATE,
            "08:00", "12:00"
        ),
        ScheduleEvent(
            2, "Istirahat", TEST_DATE,
            "12:00", "13:00",
            category="break"
        ),
    ]

    request = ScheduleRequest(
        "Belajar Python", TEST_DATE, 60
    )

    engine = make_engine()
    suggestions = engine.recommend(request, events)

    assert suggestions

    for suggestion in suggestions:
        start = to_minutes(suggestion.start)
        end = to_minutes(suggestion.end)

        # Semua alternatif harus memenuhi
        # aturan konflik terhadap existing events.
        assert not engine.has_conflict(
            start, end, events
        )
