
from dataclasses import asdict
from datetime import date, timedelta
import json

from scheduling_engine import (
    SchedulingEngine,
    ScheduleRequest,
    UserPreferences,
)

from target_resolution import ScheduleEvent


def main():
    tomorrow = date.today() + timedelta(days=1)

    events = [
        ScheduleEvent(
            1, "Kuliah",
            tomorrow, "08:00", "12:00"
        ),
        ScheduleEvent(
            2, "Istirahat siang",
            tomorrow, "12:00", "13:00",
            category="break"
        ),
        ScheduleEvent(
            3, "Pekerjaan rumah",
            tomorrow, "17:00", "18:00"
        ),
    ]

    preferences = UserPreferences(
        day_start="08:00",
        day_end="20:00",
        productive_periods=["morning", "afternoon"],
        avoid_periods=["evening"],
        min_break_minutes=15,
        max_focus_minutes=120,
    )

    request = ScheduleRequest(
        title="Belajar Python",
        event_date=tomorrow,
        duration_minutes=120,
        preferred_period="afternoon",
    )

    engine = SchedulingEngine(preferences)

    recommendations = engine.recommend(
        request=request,
        events=events,
        limit=3,
    )

    print("CURRENT EVENTS")
    for event in events:
        print(
            f"{event.start_time}-{event.end_time}: "
            f"{event.title}"
        )

    print("\nRECOMMENDATIONS")

    if not recommendations:
        print("No valid slots found")

    for index, suggestion in enumerate(
        recommendations, 1
    ):
        print(
            f"{index}. {suggestion.start}-"
            f"{suggestion.end} "
            f"(score={suggestion.score})"
        )
        print("   Reasons:", suggestion.reasons)

    with open(
        "scheduler_results.json", "w", encoding="utf-8"
    ) as file:
        json.dump(
            [asdict(item) for item in recommendations],
            file,
            indent=2,
            ensure_ascii=False,
        )


if __name__ == "__main__":
    main()
