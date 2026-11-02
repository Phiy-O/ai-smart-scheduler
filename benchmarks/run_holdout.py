
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from schedule_commands import CommandParser
from benchmarks.evaluate import (
    load_dataset,
    run_benchmark,
    summarize,
    save_results,
)


ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "intent_holdout_v1.jsonl"
OUTPUT_DIR = ROOT / "results"


def main():
    model = os.getenv("LLM_MODEL", "qwen3:4b")

    cases = load_dataset(DATASET)
    parser = CommandParser()

    print(f"Model: {model}")
    print(f"Holdout cases: {len(cases)}")
    print("Running unseen evaluation...\n")

    results = run_benchmark(parser.parse, cases)
    summary = summarize(results)

    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%d_%H%M%S")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results_path = (
        OUTPUT_DIR / f"holdout_results_{timestamp}.jsonl"
    )
    summary_path = (
        OUTPUT_DIR / f"holdout_summary_{timestamp}.json"
    )

    save_results(results, results_path)

    summary_path.write_text(
        json.dumps(
            {
                "model_configured": model,
                "dataset": DATASET.name,
                "prompt_version": "v2",
                **summary,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("=== HOLDOUT BENCHMARK ===")
    print(f"Total: {summary['total']}")
    print(f"Correct: {summary['correct']}")
    print(f"Accuracy: {summary['intent_accuracy']:.2%}")
    print(f"Execution errors: {summary['execution_errors']}")
    print(
        "Average latency:",
        summary["average_latency_seconds"],
    )
    print(
        "P95 latency:",
        summary["p95_latency_seconds"],
    )

    print("\nPer-action results:")
    for action, info in summary["by_action"].items():
        print(
            f"  {action}: "
            f"{info['correct']}/{info['total']}"
        )

    print("\nIncorrect predictions:")
    incorrect = [row for row in results if not row["correct"]]

    if not incorrect:
        print("  None")
    else:
        for row in incorrect:
            print(
                f"  {row['id']} | "
                f"expected={row['expected']} | "
                f"predicted={row['predicted']}"
            )
            print(f"    {row['instruction']}")
            if row["error"]:
                print(f"    error={row['error']}")

    print(f"\nResults saved: {results_path}")
    print(f"Summary saved: {summary_path}")


if __name__ == "__main__":
    main()
