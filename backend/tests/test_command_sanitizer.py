
from schedule_commands import RescheduleCommand
from command_sanitizer import sanitize_command


def test_remove_unsupported_reschedule_period():
    instruction = (
        "Pindahkan belajar Python dari hari ini ke besok"
    )

    command = RescheduleCommand.model_validate({
        "action": "reschedule",
        "target": {
            "task_name": "belajar Python",
            "date_reference": "today",
        },
        "new_date_reference": "tomorrow",
        "new_period": "afternoon",
    })

    result = sanitize_command(instruction, command)

    assert result.new_period is None
    assert result.new_date_reference == "tomorrow"
    assert result.target.date_reference == "today"


def test_do_not_remove_supported_period():
    instruction = (
        "Pindahkan belajar Python "
        "dari hari ini ke besok sore"
    )

    command = RescheduleCommand.model_validate({
        "action": "reschedule",
        "target": {
            "task_name": "belajar Python",
            "date_reference": "today",
        },
        "new_date_reference": "tomorrow",
        "new_period": "afternoon",
    })

    result = sanitize_command(instruction, command)

    assert result.new_period == "afternoon"


def test_do_not_repair_wrong_target_date():
    instruction = (
        "Pindahkan belajar Python besok ke pagi"
    )

    command = RescheduleCommand.model_validate({
        "action": "reschedule",
        "target": {
            "task_name": "belajar Python",
            "date_reference": "today",
        },
        "new_date_reference": "tomorrow",
        "new_period": "morning",
    })

    result = sanitize_command(instruction, command)

    assert result.target.date_reference == "today"
    assert result.new_period == "morning"
