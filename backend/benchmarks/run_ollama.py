
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


def main():
    model = os.getenv("LLM_MODEL", "qwen3:4b")

    print(f"Model configured: {model}")
    print("Initializing CommandParser...")

    parser = CommandParser()

    dataset = load_dataset()

    print(f"Benchmark cases: {len(dataset)}")
    print("Running real LLM inference...\n")

    results = run_benchmark(
        parser.parse,
        dataset,
    )

    summary = summarize(results)

    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%d_%H%M%S")

    output_dir = (
        Path(__file__).parent / "results"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    results_path = (
        output_dir / f"qwen3_results_{timestamp}.jsonl"
    )

    summary_path = (
        output_dir / f"qwen3_summary_{timestamp}.json"
    )

    save_results(results, results_path)

    summary_path.write_text(
        json.dumps(
            {
                "model_configured": model,
                **summary,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\n=== AI BENCHMARK RESULTS ===")
    print(f"Total cases : {summary['total']}")
    print(f"Correct     : {summary['correct']}")
    print(
        f"Accuracy    : "
        f"{summary['intent_accuracy']:.2%}"
    )
    print(
        f"Errors      : "
        f"{summary['execution_errors']}"
    )
    print(
        f"Avg latency : "
        f"{summary['average_latency_seconds']}s"
    )
    print(
        f"P95 latency : "
        f"{summary['p95_latency_seconds']}s"
    )

    print("\nPer-action accuracy:")

    for action, data in summary["by_action"].items():
        accuracy = (
            data["correct"] / data["total"]
        )

        print(
            f"  {action}: "
            f"{data['correct']}/{data['total']} "
            f"({accuracy:.1%})"
        )

    print(f"\nResults: {results_path}")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
