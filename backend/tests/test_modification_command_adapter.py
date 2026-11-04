
from datetime import date
import pytest
from pydantic import ValidationError
from modification_preview import ModificationAction

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



def test_reschedule_period_creates_modification_request():
    command = RescheduleCommand.model_validate({
        "action": "reschedule",
        "target": {
            "task_name": "Meeting Proyek",
        },
        "new_period": "afternoon",
    })

    result = adapt_modification_command(command, TODAY)

    assert result.status == "ready"
    assert result.request is not None

    assert result.request.action == ModificationAction.RESCHEDULE
    assert result.request.target_title == "Meeting Proyek"
    assert result.request.target_date is None

    # Periode diteruskan untuk diproses Scheduling Engine.
    assert result.request.new_period == "afternoon"

    # Tidak boleh mengarang tanggal atau jam tujuan.
    assert result.request.new_date is None
    assert result.request.new_start_time is None



def test_update_duration_creates_modification_request():
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

    assert result.status == "ready"
    assert result.request is not None

    assert result.request.action == ModificationAction.UPDATE
    assert result.request.target_title == "Belajar Python"
    assert result.request.target_date is None
    assert result.request.new_duration_minutes == 90


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
