
from datetime import date
import pytest
from pydantic import ValidationError

from schedule_commands import (
    DeleteCommand,
    UpdateCommand,
    RescheduleCommand,
)
from modification_command_adapter import (
    adapt_modification_command,
    resolve_date_reference,
)


TODAY = date(2026, 10, 26)


def test_today_reference():
    assert resolve_date_reference(
        "today", TODAY
    ) == TODAY


def test_tomorrow_reference():
    assert resolve_date_reference(
        "tomorrow", TODAY
    ) == date(2026, 10, 27)


def test_delete_command_adapter():
    command = DeleteCommand.model_validate({
        "action": "delete",
        "target": {
            "task_name": "Belajar Python",
            "date_reference": "tomorrow",
        },
    })

    result = adapt_modification_command(
        command, TODAY
    )

    assert result.status == "ready"
    assert result.request.target_title == "Belajar Python"
    assert result.request.target_date == date(2026, 10, 27)
    assert result.request.action.value == "delete"


def test_delete_without_date():
    command = DeleteCommand.model_validate({
        "action": "delete",
        "target": {
            "task_name": "Meeting Proyek",
        },
    })

    result = adapt_modification_command(command, TODAY)

    assert result.status == "ready"
    assert result.request.target_date is None


def test_reschedule_to_new_date():
    command = RescheduleCommand.model_validate({
        "action": "reschedule",
        "target": {
            "task_name": "Belajar Python",
            "date_reference": "today",
        },
        "new_date_reference": "tomorrow",
    })

    result = adapt_modification_command(command, TODAY)

    assert result.status == "ready"
    assert result.request.target_date == TODAY
    assert result.request.new_date == date(2026, 10, 27)


def test_reschedule_period_requires_slot_selection():
    command = RescheduleCommand.model_validate({
        "action": "reschedule",
        "target": {
            "task_name": "Meeting Proyek",
        },
        "new_period": "afternoon",
    })

    result = adapt_modification_command(command, TODAY)

    assert result.status == "requires_slot_selection"
    assert result.request is None


def test_update_duration_requires_preview_support():
    command = UpdateCommand.model_validate({
        "action": "update",
        "target": {
            "task_name": "Belajar Python",
        },
        "changes": {
            "duration_minutes": 90,
        },
    })

    result = adapt_modification_command(command, TODAY)

    assert result.status == "unsupported_change"


def test_empty_update_is_rejected():
    with pytest.raises(
        ValidationError,
        match="Tidak ada perubahan yang diberikan",
    ):
        UpdateCommand.model_validate({
            "action": "update",
            "target": {
                "task_name": "Belajar Python",
            },
            "changes": {},
        })

def test_reschedule_without_destination():
    with pytest.raises(
        ValidationError,
        match="Tujuan pemindahan tidak ada",
    ):
        RescheduleCommand.model_validate({
            "action": "reschedule",
            "target": {
                "task_name": "Belajar Python",
            },
        })
