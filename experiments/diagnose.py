
import json
from pathlib import Path

from experiments.archives.schedule_commands import (
    CommandParser,
    IntentResult,
    COMMAND_MODELS,
    INTENT_PROMPT,
    EXTRACTION_PROMPT,
)

CASES = [
    ("Tambahkan belajar Python selama 2 jam besok pagi.", "create"),
    ("Ubah durasi belajar Python menjadi 90 menit.", "update"),
    ("Pindahkan jadwal olahraga besok ke sore hari.", "reschedule"),
    ("Hapus jadwal meeting besok.", "delete"),
    ("Tolong atur jadwalku.", "clarify"),
]


def main():
    parser = CommandParser()
    results = []

    for i, (instruction, expected_action) in enumerate(CASES, 1):
        print(f"\nTEST {i}: {instruction}", flush=True)

        record = {
            "test": i,
            "input": instruction,
            "expected_action": expected_action,
        }

        try:
            # Stage 1: classification
            intent = parser._generate(
                INTENT_PROMPT,
                instruction,
                IntentResult,
            )

            record["predicted_action"] = intent.action
            record["intent_correct"] = (
                intent.action == expected_action
            )

            # Stage 2: gunakan action BENAR dari ground truth
            # untuk mengisolasi kesalahan extraction.
            command_model = COMMAND_MODELS[expected_action]

            extraction = parser._generate(
                EXTRACTION_PROMPT
                + f"\nOperasi wajib: {expected_action}.",
                instruction,
                command_model,
            )

            record["oracle_extraction"] = (
                extraction.model_dump()
            )

            print("Predicted:", intent.action)
            print("Expected :", expected_action)
            print("Extraction:", json.dumps(
                record["oracle_extraction"],
                ensure_ascii=False
            ))

        except Exception as error:
            record["error"] = str(error)
            print("ERROR:", error)

        results.append(record)

    Path("diagnosis_results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\nSaved: diagnosis_results.json")


if __name__ == "__main__":
    main()
