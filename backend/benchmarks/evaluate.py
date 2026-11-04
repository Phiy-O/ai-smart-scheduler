
import json
import time
from collections import Counter
from pathlib import Path


DATASET = Path(__file__).parent / "intent_v1.jsonl"


def load_dataset(path=DATASET):
    with open(path, encoding="utf-8") as file:
        return [
            json.loads(line)
            for line in file
            if line.strip()
        ]


def run_benchmark(parse_instruction, dataset=None):
    cases = dataset if dataset is not None else load_dataset()

    results = []

    for case in cases:
        started = time.perf_counter()

        try:
            command = parse_instruction(
                case["instruction"]
            )

            predicted = command.action
            error = None

        except Exception as exc:
            predicted = None
            error = (
                f"{type(exc).__name__}: {exc}"
            )

        latency = time.perf_counter() - started

        results.append({
            "id": case["id"],
            "instruction": case["instruction"],
            "expected": case["expected_action"],
            "predicted": predicted,
            "correct": predicted == case["expected_action"],
            "latency_seconds": round(latency, 3),
            "error": error,
            "category": case["category"],
        })

    return results


def summarize(results):
    total = len(results)

    if total == 0:
        raise ValueError("Benchmark dataset is empty")

    correct = sum(row["correct"] for row in results)
    errors = sum(row["error"] is not None for row in results)

    latencies = sorted(
        row["latency_seconds"] for row in results
    )

    p95_index = max(
        0, -(-95 * total // 100) - 1
    )

    by_action = {}

    for action in sorted(set(
        row["expected"] for row in results
    )):
        subset = [
            row for row in results
            if row["expected"] == action
        ]

        by_action[action] = {
            "total": len(subset),
            "correct": sum(
                row["correct"] for row in subset
            ),
        }

    return {
        "total": total,
        "correct": correct,
        "intent_accuracy": round(correct / total, 4),
        "execution_errors": errors,
        "average_latency_seconds": round(
            sum(latencies) / total, 3
        ),
        "p95_latency_seconds": latencies[p95_index],
        "by_action": by_action,
    }


def save_results(results, output_path):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        for result in results:
            file.write(
                json.dumps(result, ensure_ascii=False) + "\n"
            )
