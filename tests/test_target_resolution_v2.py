
from datetime import date

from target_resolution import ScheduleEvent
from target_resolution_v2 import (
    TargetQuery,
    TargetResolverV2,
    ResolutionStatus,
    normalize_title,
)


TEST_DATE = date(2026, 10, 27)
NEXT_DATE = date(2026, 10, 28)


def make_events():
    return [
        ScheduleEvent(
            id=1,
            title="Belajar Python",
            event_date=TEST_DATE,
            start_time="09:00",
            end_time="10:00",
        ),
        ScheduleEvent(
            id=2,
            title="Belajar Python",
            event_date=TEST_DATE,
            start_time="15:00",
            end_time="16:00",
        ),
        ScheduleEvent(
            id=3,
            title="Meeting Proyek",
            event_date=TEST_DATE,
            start_time="13:00",
            end_time="14:00",
        ),
        ScheduleEvent(
            id=4,
            title="Belajar Python",
            event_date=NEXT_DATE,
            start_time="10:00",
            end_time="11:00",
        ),
    ]


def test_match_specific_time():
    result = TargetResolverV2().resolve(
        TargetQuery(
            title="Belajar Python",
            event_date=TEST_DATE,
            start_time="15:00",
        ),
        make_events(),
    )

    assert result.status == ResolutionStatus.MATCHED
    assert result.candidates[0].id == 2


def test_match_afternoon_period():
    result = TargetResolverV2().resolve(
        TargetQuery(
            title="Belajar Python",
            event_date=TEST_DATE,
            period="afternoon",
        ),
        make_events(),
    )

    assert result.status == ResolutionStatus.MATCHED
    assert result.candidates[0].id == 2


def test_ambiguous_without_time():
    result = TargetResolverV2().resolve(
        TargetQuery(
            title="Belajar Python",
            event_date=TEST_DATE,
        ),
        make_events(),
    )

    assert result.status == ResolutionStatus.AMBIGUOUS
    assert [e.id for e in result.candidates] == [1, 2]


def test_not_found():
    result = TargetResolverV2().resolve(
        TargetQuery(
            title="Belajar Java",
            event_date=TEST_DATE,
        ),
        make_events(),
    )

    assert result.status == ResolutionStatus.NOT_FOUND
    assert result.candidates == []


def test_missing_title_requires_clarification():
    result = TargetResolverV2().resolve(
        TargetQuery(event_date=TEST_DATE),
        make_events(),
    )

    assert (
        result.status
        == ResolutionStatus.INSUFFICIENT_EVIDENCE
    )


def test_no_date_keeps_multiple_candidates():
    result = TargetResolverV2().resolve(
        TargetQuery(title="Belajar Python"),
        make_events(),
    )

    assert result.status == ResolutionStatus.AMBIGUOUS
    assert [e.id for e in result.candidates] == [1, 2, 4]


def test_case_insensitive_title():
    result = TargetResolverV2().resolve(
        TargetQuery(
            title="belajar PYTHON",
            event_date=NEXT_DATE,
        ),
        make_events(),
    )

    assert result.status == ResolutionStatus.MATCHED
    assert result.candidates[0].id == 4


def test_partial_title_matches_complete_words():
    result = TargetResolverV2().resolve(
        TargetQuery(
            title="Python",
            event_date=NEXT_DATE,
        ),
        make_events(),
    )

    assert result.status == ResolutionStatus.MATCHED
    assert result.candidates[0].id == 4


def test_normalize_title():
    assert normalize_title("  Belajar, PYTHON! ") == (
        "belajar python"
    )


def test_invalid_period_does_not_fallback():
    result = TargetResolverV2().resolve(
        TargetQuery(
            title="Belajar Python",
            period="midnight",
        ),
        make_events(),
    )

    assert (
        result.status
        == ResolutionStatus.INSUFFICIENT_EVIDENCE
    )
