
from dataclasses import asdict, is_dataclass
from datetime import date

from schedule_commands import CommandParser
from semantic_evidence_gate import validate_semantic_evidence
from command_sanitizer import sanitize_command
from modification_command_adapter import (
    adapt_modification_command,
)
from modification_approval_service import (
    ModificationApprovalService,
)
from modification_service import ModificationService


class AIModification:
    def __init__(self, engine, parser=None):
        self.parser = parser if parser is not None else CommandParser()
        self.modification_service = ModificationService(engine)
        self.approval_service = ModificationApprovalService(engine)

    def process(self, instruction: str):
        command = self.parser.parse(instruction)
        command = sanitize_command(instruction, command)

        if command.action == "clarify":
            return {
                "status": "needs_clarification",
                "question": command.clarification_question,
            }

        if command.action not in {
            "update", "reschedule", "delete"
        }:
            return {
                "status": "unsupported_action",
                "action": command.action,
            }

        # Semantic evidence validation
        semantic = validate_semantic_evidence(
            instruction,
            command,
        )

        if not semantic.can_proceed:
            return {
                "status": "evidence_rejected",
                "issues": [
                    {
                        "field": issue.field,
                        "reason": issue.reason,
                    }
                    for issue in semantic.issues
                ],
            }

        # Convert LLM command into modification request
        adaptation = adapt_modification_command(
            command,
            reference_date=date.today(),
        )

        if adaptation.status != "ready":
            return {
                "status": adaptation.status,
                "reason": adaptation.reason,
            }

        
        from dataclasses import replace
        import re

        request = adaptation.request

        if (
            command.action == "reschedule"
            and request.new_period == "afternoon"
        ):
            text = instruction.casefold()

            if re.search(r"\bsore\b", text):
                request = replace(
                    request,
                    time_hint="sore",
                )
            elif re.search(r"\bsiang\b", text):
                request = replace(
                    request,
                    time_hint="siang",
                )

        # Read database and resolve target. This operation does not mutate it.
        preview = self.modification_service.preview(request)
        
        if preview.status == "preview_ready":
            return self.approval_service.create_proposal(preview)

        if is_dataclass(preview):
            return asdict(preview)

        if hasattr(preview, "model_dump"):
            return preview.model_dump(mode="json")

        raise TypeError("Unsupported modification preview result")
