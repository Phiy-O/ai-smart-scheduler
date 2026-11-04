
from semantic_evidence_gate import (
    EvidenceStatus,
    validate_semantic_evidence,
)


def test_missing_create_date():
    result = validate_semantic_evidence(
        "Besok aku ingin mengerjakan soal statistika selama 70 menit",
        {
            "action": "create",
            "task_name": "soal statistika",
            "date_reference": None,
            "duration_minutes": 70,
            "preferred_period": None,
        },
    )

    assert result.status == EvidenceStatus.NEEDS_REVIEW
    assert any(
        issue.field == "date_reference"
        for issue in result.issues
    )


def test_missing_delete_target_date():
    result = validate_semantic_evidence(
        "Aku batal latihan Git hari ini, hapus kegiatannya",
        {
            "action": "delete",
            "target": {
                "task_name": "latihan Git",
                "date_reference": None,
            },
        },
    )

    assert result.status == EvidenceStatus.NEEDS_REVIEW
    assert any(
        issue.field == "target.date_reference"
        for issue in result.issues
    )


def test_missing_reschedule_destination():
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


def test_valid_delete_without_date():
    result = validate_semantic_evidence(
        "Hapus agenda latihan Git",
        {
            "action": "delete",
            "target": {
                "task_name": "latihan Git",
                "date_reference": None,
            },
        },
    )

    assert result.status == EvidenceStatus.ACCEPTED


def test_missing_update_duration():
    result = validate_semantic_evidence(
        "Ubah durasi latihan Git menjadi 45 menit",
        {
            "action": "update",
            "target": {
                "task_name": "latihan Git",
                "date_reference": None,
            },
            "changes": {
                "duration_minutes": None,
                "preferred_period": None,
            },
        },
    )

    assert result.status == EvidenceStatus.NEEDS_REVIEW
    assert any(
        issue.field == "changes.duration_minutes"
        for issue in result.issues
    )