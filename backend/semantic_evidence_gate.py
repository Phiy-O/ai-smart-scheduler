
from dataclasses import dataclass
from enum import Enum
import re
import unicodedata


class EvidenceStatus(str, Enum):
    ACCEPTED = "accepted"
    NEEDS_REVIEW = "needs_review"
    NEEDS_CLARIFICATION = "needs_clarification"


@dataclass(frozen=True)
class EvidenceIssue:
    field: str
    reason: str


@dataclass(frozen=True)
class EvidenceResult:
    status: EvidenceStatus
    issues: list[EvidenceIssue]

    @property
    def can_proceed(self) -> bool:
        return self.status == EvidenceStatus.ACCEPTED


DATE_PATTERNS = {
    "today": r"\b(?:hari\s+ini|pagi\s+ini|siang\s+ini|sore\s+ini|malam\s+ini|nanti\s+(?:pagi|siang|sore|malam))\b",
    "tomorrow": r"\b(?:besok|esok)\b",
}

PERIOD_PATTERNS = {
    "morning": r"\bpagi\b",
    "afternoon": r"\b(?:siang|sore)\b",
    "evening": r"\bmalam\b",
}

NUMBER_WORDS = {
    "satu": 1,
    "dua": 2,
    "tiga": 3,
    "empat": 4,
}


def normalize_instruction(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    return " ".join(value.casefold().split())


def mentioned_dates(instruction: str) -> set[str]:
    return {
        label
        for label, pattern in DATE_PATTERNS.items()
        if re.search(pattern, instruction)
    }


def mentioned_periods(instruction: str) -> set[str]:
    return {
        label
        for label, pattern in PERIOD_PATTERNS.items()
        if re.search(pattern, instruction)
    }


def mentioned_durations(instruction: str) -> set[int]:
    values = set()

    # Keep the combined value as evidence for expressions such as
    # "1 jam 30 menit"; the individual components are also retained.
    for hours, minutes in re.findall(
        r"\b(\d+)\s*jam\s+(\d+)\s*menit\b",
        instruction,
    ):
        values.add(int(hours) * 60 + int(minutes))

    for hours, minutes in re.findall(
        rf"\b({'|'.join(NUMBER_WORDS)})\s+jam\s+(\d+)\s*menit\b",
        instruction,
    ):
        values.add(NUMBER_WORDS[hours] * 60 + int(minutes))

    for number in re.findall(
        r"\b(\d+)\s*menit\b", instruction
    ):
        values.add(int(number))

    for number in re.findall(
        r"\b(\d+)\s*jam\b", instruction
    ):
        values.add(int(number) * 60)

    for word, number in NUMBER_WORDS.items():
        if re.search(
            rf"\b{word}\s+setengah\s+jam\b",
            instruction,
        ):
            values.add(number * 60 + 30)

        if re.search(
            rf"\b{word}\s+jam\b",
            instruction,
        ):
            values.add(number * 60)

    if re.search(r"\bsetengah\s+jam\b", instruction):
        values.add(30)

    if re.search(r"\bseperempat\s+jam\b", instruction):
        values.add(15)

    return values


def _read(data: dict, path: str):
    current = data

    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)

    return current

def find_missing_evidence(
    instruction: str,
    data: dict,
) -> list[EvidenceIssue]:
    """
    Detect explicit date/period/duration information
    omitted by the model.

    Conservative checks only. This function does not
    infer dates or modify the command.
    """
    text = normalize_instruction(instruction)
    action = data.get("action")
    issues = []

    dates = mentioned_dates(text)
    periods = mentioned_periods(text)
    durations = mentioned_durations(text)

    if action == "create":
        if len(dates) == 1 and _read(data, "date_reference") is None:
            issues.append(EvidenceIssue(
                "date_reference",
                "Explicit date was not extracted",
            ))

        if len(periods) == 1 and _read(data, "preferred_period") is None:
            issues.append(EvidenceIssue(
                "preferred_period",
                "Explicit period was not extracted",
            ))

        if len(durations) == 1 and _read(data, "duration_minutes") is None:
            issues.append(EvidenceIssue(
                "duration_minutes",
                "Explicit duration was not extracted",
            ))

    elif action == "delete":
        if len(dates) == 1 and _read(data, "target.date_reference") is None:
            issues.append(EvidenceIssue(
                "target.date_reference",
                "Explicit target date was not extracted",
            ))

    elif action == "update":
        if len(dates) == 1 and _read(data, "target.date_reference") is None:
            issues.append(EvidenceIssue(
                "target.date_reference",
                "Explicit target date was not extracted",
            ))

        if len(durations) == 1 and _read(
            data, "changes.duration_minutes"
        ) is None:
            issues.append(EvidenceIssue(
                "changes.duration_minutes",
                "Explicit new duration was not extracted",
            ))

        if len(periods) == 1 and _read(
            data, "changes.preferred_period"
        ) is None:
            issues.append(EvidenceIssue(
                "changes.preferred_period",
                "Explicit period preference was not extracted",
            ))

    elif action == "reschedule":
        # A deliberately limited rule for explicit
        # 'from <date> to <date>' expressions.
        transfer = re.search(
            r"\bdari\s+hari\s+ini\s+ke\s+besok\b"
            r"|\bdari\s+besok\s+ke\s+hari\s+ini\b",
            text,
        )

        if transfer:
            if _read(data, "target.date_reference") is None:
                issues.append(EvidenceIssue(
                    "target.date_reference",
                    "Explicit source date was not extracted",
                ))

            if _read(data, "new_date_reference") is None:
                issues.append(EvidenceIssue(
                    "new_date_reference",
                    "Explicit destination date was not extracted",
                ))

        # The destination period can be checked when
        # the sentence contains only one period.
        if len(periods) == 1 and _read(data, "new_period") is None:
            issues.append(EvidenceIssue(
                "new_period",
                "Explicit destination period may be missing",
            ))

    return issues

def validate_semantic_evidence(
    instruction: str,
    command,
) -> EvidenceResult:
    text = normalize_instruction(instruction)

    data = (
        command.model_dump(mode="python")
        if hasattr(command, "model_dump")
        else command
    )

    if not isinstance(data, dict):
        raise TypeError("Command must be a dictionary or Pydantic model")

    action = data.get("action")

    if action == "clarify":
        return EvidenceResult(
            EvidenceStatus.NEEDS_CLARIFICATION,
            [],
        )

    if action not in {
        "create", "update", "delete", "reschedule"
    }:
        return EvidenceResult(
            EvidenceStatus.NEEDS_REVIEW,
            [EvidenceIssue("action", "Unknown action")],
        )

    issues = []

    dates = mentioned_dates(text)
    periods = mentioned_periods(text)
    durations = mentioned_durations(text)

    date_fields = (
        ["date_reference"]
        if action == "create"
        else ["target.date_reference"]
    )

    if action == "reschedule":
        date_fields.append("new_date_reference")

    for field in date_fields:
        value = _read(data, field)

        if value is not None and value not in dates:
            issues.append(EvidenceIssue(
                field,
                f"Date {value!r} is not supported by instruction",
            ))

    period_fields = {
        "create": ["preferred_period"],
        "update": ["changes.preferred_period"],
        "reschedule": ["new_period"],
        "delete": [],
    }[action]

    for field in period_fields:
        value = _read(data, field)

        if value is not None and value not in periods:
            issues.append(EvidenceIssue(
                field,
                f"Period {value!r} is not supported by instruction",
            ))

    duration_fields = {
        "create": ["duration_minutes"],
        "update": ["changes.duration_minutes"],
        "reschedule": [],
        "delete": [],
    }[action]

    for field in duration_fields:
        value = _read(data, field)

        if value is not None and value not in durations:
            issues.append(EvidenceIssue(
                field,
                f"Duration {value!r} is not verified",
            ))

    # Detect a common reschedule failure:
    # a single date reference is copied into both
    # the old target date and the new destination.
    if action == "reschedule":
        old_date = _read(data, "target.date_reference")
        new_date = _read(data, "new_date_reference")

        if old_date is not None and old_date == new_date:
            issues.append(EvidenceIssue(
                "new_date_reference",
                "Old and new dates are identical; verify date roles",
            ))

        # A missing destination date is suspicious
        # when a clear 'from X to Y' structure exists.
        explicit_transfer = re.search(
            r"\bdari\b.+?\bke\b",
            text,
        )

        if explicit_transfer and new_date is None:
            issues.append(EvidenceIssue(
                "new_date_reference",
                "Explicit transfer may contain an unextracted destination",
            ))
    issues.extend(find_missing_evidence(text, data))

    status = (
        EvidenceStatus.NEEDS_REVIEW
        if issues else EvidenceStatus.ACCEPTED
    )

    return EvidenceResult(status, issues)
