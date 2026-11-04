
from types import SimpleNamespace

from benchmarks.evaluate import (
    load_dataset,
    run_benchmark,
    summarize,
)


def test_benchmark_dataset_loads():
    cases = load_dataset()

    assert len(cases) == 25
    assert len({case["id"] for case in cases}) == 25


def test_benchmark_scores_correct_predictions():
    dataset = [
        {
            "id": "T1",
            "instruction": "Buat jadwal",
            "expected_action": "create",
            "category": "test",
        },
        {
            "id": "T2",
            "instruction": "Hapus jadwal",
            "expected_action": "delete",
            "category": "test",
        },
    ]

    def fake_parser(instruction):
        return SimpleNamespace(
            action="create"
        )

    results = run_benchmark(fake_parser, dataset)
    summary = summarize(results)

    assert summary["total"] == 2
    assert summary["correct"] == 1
    assert summary["intent_accuracy"] == 0.5


def test_parser_failure_is_recorded():
    dataset = [{
        "id": "T1",
        "instruction": "test",
        "expected_action": "create",
        "category": "test",
    }]

    def failing_parser(instruction):
        raise RuntimeError("LLM unavailable")

    results = run_benchmark(failing_parser, dataset)

    assert results[0]["correct"] is False
    assert results[0]["predicted"] is None
    assert "RuntimeError" in results[0]["error"]
