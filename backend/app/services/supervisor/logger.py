"""JSONL decision logger for supervisor audit trail."""

from __future__ import annotations

import json
from pathlib import Path
from typing import IO

from .models import Decision


class DecisionLogger:
    """Appends supervisor decisions to a JSONL file."""

    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._file: IO[str] | None = None

    def open(self) -> None:
        self._file = self._path.open("a", encoding="utf-8")

    def log(self, decision: Decision) -> None:
        """Serialize and append a decision to the JSONL file."""
        if self._file is None:
            self.open()
        line = json.dumps(decision.model_dump(mode="json"), default=str)
        assert self._file is not None
        self._file.write(line + "\n")
        self._file.flush()

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None

    def __enter__(self) -> DecisionLogger:
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
