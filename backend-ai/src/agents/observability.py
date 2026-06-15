"""Lightweight workflow observability for agent runs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any


def _slugify(value: str, max_len: int = 60) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip()).strip("_").lower()
    return (cleaned or "query")[:max_len]


@dataclass
class TimedBlock:
    """Measure elapsed time for a code block."""

    start: float

    @classmethod
    def start_now(cls) -> "TimedBlock":
        return cls(start=perf_counter())

    def elapsed_ms(self) -> float:
        return round((perf_counter() - self.start) * 1000, 2)


class WorkflowRunLogger:
    """Filesystem logger that writes run artefacts under a date/query folder."""

    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)
        self.run_dir: Path | None = None
        self._agent_log: Path | None = None
        self._tool_log: Path | None = None

    def start_run(self, user_input: dict[str, Any]) -> str:
        now = datetime.now()
        query = str(
            user_input.get("query")
            or user_input.get("analysis_type")
            or "query"
        )
        folder = f"{now.strftime('%H-%M-%S')}_{_slugify(query)}"
        self.run_dir = self.base_dir / now.strftime("%Y-%m-%d") / folder
        self.run_dir.mkdir(parents=True, exist_ok=True)

        self._agent_log = self.run_dir / "agent_calls.log"
        self._tool_log = self.run_dir / "tool_calls.log"
        self._agent_log.write_text("", encoding="utf-8")
        self._tool_log.write_text("", encoding="utf-8")

        self._write_json("user_input.json", user_input)
        return str(self.run_dir)

    def log_agent_call(
        self,
        agent: str,
        event: str,
        payload: dict[str, Any] | None = None,
        *,
        duration_ms: float | None = None,
        error: str | None = None,
    ) -> None:
        if not self._agent_log:
            return
        row = {
            "ts": datetime.now().isoformat(),
            "agent": agent,
            "event": event,
            "duration_ms": duration_ms,
            "payload": payload or {},
            "error": error,
        }
        with self._agent_log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")

    def log_tool_call(
        self,
        agent: str,
        tool: str,
        status: str,
        tool_input: dict[str, Any] | None = None,
        *,
        tool_output_preview: str | None = None,
        duration_ms: float | None = None,
        error: str | None = None,
    ) -> None:
        if not self._tool_log:
            return
        row = {
            "ts": datetime.now().isoformat(),
            "agent": agent,
            "tool": tool,
            "status": status,
            "duration_ms": duration_ms,
            "input": tool_input or {},
            "output_preview": (tool_output_preview or "")[:800],
            "error": error,
        }
        with self._tool_log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")

    def save_final_output(self, payload: dict[str, Any]) -> None:
        self._write_json("final_output.json", payload)

    def _write_json(self, name: str, payload: Any) -> None:
        if not self.run_dir:
            return
        path = self.run_dir / name
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
