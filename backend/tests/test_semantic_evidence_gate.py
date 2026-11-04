
from semantic_evidence_gate import (
    EvidenceStatus,
    mentioned_durations,
    validate_semantic_evidence,
)


def test_accept_valid_create():
    result = validate_semantic_evidence(
        "Tambahkan belajar Python besok pagi selama 90 menit",
        {
            "action": "create",
            "task_name": "belajar Python",
            "date_reference": "tomorrow",
            "preferred_period": "morning",
            "duration_minutes": 90,
        },
    )

    assert result.status == EvidenceStatus.ACCEPTED
    assert result.can_proceed


def test_reject_hallucinated_date():
    result = validate_semantic_evidence(
        "Hapus agenda latihan presentasi",
        {
            "action": "delete",
            "target": {
                "task_name": "latihan presentasi",
                "date_reference": "today",
            },
        },
    )

    assert result.status == EvidenceStatus.NEEDS_REVIEW
    assert not result.can_proceed
    assert result.issues[0].field == "target.date_reference"


def test_reject_unsupported_period():
    result = validate_semantic_evidence(
        "Tambahkan riset referensi siang ini 15 menit",
        {
            "action": "create",
            "date_reference": "today",
            "preferred_period": "morning",
            "duration_minutes": 15,
        },
    )

    assert result.status == EvidenceStatus.NEEDS_REVIEW
    assert any(
        issue.field == "preferred_period"
        for issue in result.issues
    )


def test_reject_hallucinated_duration():
    result = validate_semantic_evidence(
        "Buat jadwal olahraga besok",
        {
            "action": "create",
            "date_reference": "tomorrow",
            "duration_minutes": 60,
        },
    )

    assert result.status == EvidenceStatus.NEEDS_REVIEW


def test_accept_relative_duration():
    assert 90 in mentioned_durations(
        "Aku ingin belajar satu setengah jam"
    )
    assert 120 in mentioned_durations(
        "Aku mau belajar dua jam"
    )
    assert 15 in mentioned_durations(
        "Belajar seperempat jam"
    )


def test_accept_combined_numeric_duration():
    assert 90 in mentioned_durations(
        "Belajar selama 1 jam 30 menit"
    )


def test_accept_combined_word_duration():
    assert 150 in mentioned_durations(
        "Belajar selama dua jam 30 menit"
    )


def test_reject_wrong_target_date():
    result = validate_semantic_evidence(
        "Jadwal belajar Python besok digeser ke pagi",
        {
            "action": "reschedule",
            "target": {
                "task_name": "belajar Python",
                "date_reference": "today",
            },
            "new_date_reference": "tomorrow",
            "new_period": "morning",
        },
    )

    assert result.status == EvidenceStatus.NEEDS_REVIEW
    assert any(
        issue.field == "target.date_reference"
        for issue in result.issues
    )


def test_accept_explicit_date_transfer():
    result = validate_semantic_evidence(
        "Pindahkan meeting dari hari ini ke besok sore",
        {
            "action": "reschedule",
            "target": {
                "task_name": "meeting",
                "date_reference": "today",
            },
            "new_date_reference": "tomorrow",
            "new_period": "afternoon",
        },
    )

    assert result.status == EvidenceStatus.ACCEPTED


def test_detect_missing_destination_in_transfer():
    result = validate_semantic_evidence(
        "Geser meeting dari hari ini ke besok sore",
        {
            "action": "reschedule",
            "target": {
                "task_name": "meeting",
                "date_reference": "today",
            },
            "new_date_reference": None,
            "new_period": "afternoon",
        },
    )

    assert result.status == EvidenceStatus.NEEDS_REVIEW


def test_clarify_stays_clarification():
    result = validate_semantic_evidence(
        "Pindahkan jadwal itu",
        {"action": "clarify"},
    )

    assert result.status == EvidenceStatus.NEEDS_CLARIFICATION
    assert not result.can_proceed
