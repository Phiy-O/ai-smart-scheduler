
from types import SimpleNamespace

from ai_modification import AIModification


class FakeParser:
    def __init__(self, command):
        self.command = command

    def parse(self, instruction):
        return self.command


def make_service(command):
    service = AIModification.__new__(AIModification)
    service.parser = FakeParser(command)
    service.modification_service = None
    return service


def test_create_is_not_modification():
    service = make_service(
        SimpleNamespace(action="create")
    )

    result = service.process(
        "Tambahkan belajar Python besok"
    )

    assert result["status"] == "unsupported_action"


def test_clarification_is_forwarded():
    service = make_service(
        SimpleNamespace(
            action="clarify",
            clarification_question="Jadwal yang mana?",
        )
    )

    result = service.process("Hapus yang itu")

    assert result["status"] == "needs_clarification"
    assert result["question"] == "Jadwal yang mana?"
