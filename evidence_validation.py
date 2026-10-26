
import re
from dataclasses import dataclass, field

from experiments.archives.schedule_commands import ScheduleCommand


PERIOD_TERMS = {
    "morning": {"pagi"},
    "afternoon": {"siang", "sore"},
    "evening": {"malam"},
}

DATE_TERMS = {
    "today": {"hari ini", "nanti"},
    "tomorrow": {"besok"},
}

STOP_WORDS = {
    "jadwal", "aktivitas", "agenda",
}


def normalize(text: str) -> str:
    text = text.casefold().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def contains_term(text: str, term: str) -> bool:
    pattern = (
        r"(?<!\w)"
        + re.escape(term)
        + r"(?!\w)"
    )
    return re.search(pattern, text) is not None


def has_evidence(text: str, terms: set[str]) -> bool:
    return any(contains_term(text, t) for t in terms)


def task_supported(name: str, instruction: str) -> bool:
    name_words = [
        w for w in normalize(name).split()
        if w not in STOP_WORDS
    ]

    if not name_words:
        return False

    normalized_input = normalize(instruction)

    return all(
        contains_term(normalized_input, word)
        for word in name_words
    )


@dataclass
class EvidenceResult:
    valid: bool = True
    issues: list[str] = field(default_factory=list)

    def reject(self, reason: str):
        self.valid = False
        self.issues.append(reason)


def validate_evidence(
    instruction: str,
    command: ScheduleCommand,
) -> EvidenceResult:

    result = EvidenceResult()
    text = normalize(instruction)

    if command.action == "clarify":
        return result

    if command.action == "create":
        name = command.task_name
        date = command.date_reference
        period = command.preferred_period

    else:
        name = command.target.task_name
        date = command.target.date_reference
        period = None

    if not task_supported(name, instruction):
        result.reject(
            f"Nama aktivitas '{name}' tidak didukung input"
        )

    # Evidence tanggal target / pembuatan
    if date is not None:
        if not has_evidence(text, DATE_TERMS[date]):
            result.reject(
                f"Tanggal '{date}' tidak memiliki bukti"
            )

    # Evidence periode pembuatan
    if period is not None:
        if not has_evidence(
            text, PERIOD_TERMS[period]
        ):
            result.reject(
                f"Periode '{period}' tidak memiliki bukti"
            )

    if command.action == "reschedule":
        new_date = command.new_date_reference
        new_period = command.new_period

        if new_date is not None:
            if not has_evidence(
                text, DATE_TERMS[new_date]
            ):
                result.reject(
                    f"Tanggal baru '{new_date}' tidak didukung"
                )

        if new_period is not None:
            if not has_evidence(
                text, PERIOD_TERMS[new_period]
            ):
                result.reject(
                    f"Periode baru '{new_period}' tidak didukung"
                )

    if command.action == "update":
        changed_period = command.changes.preferred_period

        if changed_period is not None:
            if not has_evidence(
                text, PERIOD_TERMS[changed_period]
            ):
                result.reject(
                    "Perubahan periode tidak didukung input"
                )

    return result
