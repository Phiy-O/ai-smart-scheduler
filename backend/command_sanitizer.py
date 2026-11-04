
from schedule_commands import RescheduleCommand
from semantic_evidence_gate import (
    validate_semantic_evidence,
)


def sanitize_command(instruction, command):
    if not isinstance(command, RescheduleCommand):
        return command

    evidence = validate_semantic_evidence(
        instruction,
        command,
    )

    issue_fields = {
        issue.field
        for issue in evidence.issues
    }

    # Only repair the one known, unambiguous case.
    if issue_fields != {"new_period"}:
        return command

    if command.new_date_reference is None:
        return command

    repaired = command.model_copy(
        update={"new_period": None}
    )

    # Never return a repaired command that fails validation.
    repaired_evidence = validate_semantic_evidence(
        instruction,
        repaired,
    )

    if not repaired_evidence.can_proceed:
        return command

    return repaired
