"""Small state machine for the setup-style graphical workflow."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

type EventDetails = dict[str, str | int | bool]
type EventRecorder = Callable[[str, EventDetails], None]


@dataclass(frozen=True, slots=True)
class GuiEvent:
    """One deterministic GUI event suitable for tests and diagnostic logs."""

    name: str
    details: EventDetails


@dataclass(slots=True)
class GuiEventJournal:
    """In-memory event sink that can emit a temporary JSON Lines trace."""

    events: list[GuiEvent] = field(default_factory=list)

    def record(self, name: str, details: EventDetails) -> None:
        self.events.append(GuiEvent(name, dict(details)))

    def write_jsonl(self, path: Path) -> None:
        with path.open("w", encoding="utf-8", newline="\n") as stream:
            for event in self.events:
                stream.write(
                    json.dumps(
                        {"name": event.name, "details": event.details},
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    + "\n"
                )


class WizardStep(Enum):
    GAME = "game"
    ACTION = "action"
    PROGRESS = "progress"
    COMPLETE = "complete"


@dataclass(slots=True)
class AsyncOperationState:
    """Headless ownership state for GUI checks and modifying operations."""

    check_generation: int = 0
    operation_running: bool = False
    closed: bool = False
    record_event: EventRecorder | None = field(default=None, repr=False, compare=False)

    def _record(self, name: str, **details: str | int | bool) -> None:
        if self.record_event is not None:
            self.record_event(name, details)

    def begin_check(self) -> int:
        self.check_generation += 1
        self._record("check.started", generation=self.check_generation)
        return self.check_generation

    def accepts_check(self, generation: int) -> bool:
        accepted = not self.closed and generation == self.check_generation
        self._record("check.accepted" if accepted else "check.rejected", generation=generation)
        return accepted

    def begin_operation(self) -> bool:
        if self.closed or self.operation_running:
            self._record("operation.rejected")
            return False
        self.operation_running = True
        self._record("operation.started")
        return True

    def finish_operation(self) -> bool:
        if self.closed or not self.operation_running:
            self._record("operation.finish_rejected")
            return False
        self.operation_running = False
        self._record("operation.finished")
        return True

    def close(self) -> None:
        self.closed = True
        self.operation_running = False
        self.check_generation += 1
        self._record("session.closed", generation=self.check_generation)


@dataclass(slots=True)
class WizardFlow:
    step: WizardStep = WizardStep.GAME
    record_event: EventRecorder | None = field(default=None, repr=False, compare=False)

    def _transition(self, name: str, target: WizardStep) -> None:
        previous = self.step
        self.step = target
        if self.record_event is not None:
            self.record_event(name, {"from": previous.value, "to": target.value})

    def advance(self) -> None:
        transitions = {
            WizardStep.GAME: WizardStep.ACTION,
            WizardStep.ACTION: WizardStep.PROGRESS,
        }
        try:
            target = transitions[self.step]
        except KeyError as exc:
            raise ValueError(f"cannot advance from {self.step.value}") from exc
        self._transition("wizard.advanced", target)

    def back(self) -> None:
        if self.step is WizardStep.PROGRESS:
            raise ValueError("cannot go back while an operation is running")
        transitions = {
            WizardStep.ACTION: WizardStep.GAME,
            WizardStep.COMPLETE: WizardStep.ACTION,
        }
        try:
            target = transitions[self.step]
        except KeyError as exc:
            raise ValueError(f"cannot go back from {self.step.value}") from exc
        self._transition("wizard.back", target)

    def complete(self) -> None:
        if self.step is not WizardStep.PROGRESS:
            raise ValueError(f"cannot complete from {self.step.value}")
        self._transition("wizard.completed", WizardStep.COMPLETE)

    def restart(self) -> None:
        if self.step is not WizardStep.COMPLETE:
            raise ValueError(f"cannot restart from {self.step.value}")
        self._transition("wizard.restarted", WizardStep.GAME)
