"""Small state machine for the setup-style graphical workflow."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


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

    def begin_check(self) -> int:
        self.check_generation += 1
        return self.check_generation

    def accepts_check(self, generation: int) -> bool:
        return not self.closed and generation == self.check_generation

    def begin_operation(self) -> bool:
        if self.closed or self.operation_running:
            return False
        self.operation_running = True
        return True

    def finish_operation(self) -> bool:
        if self.closed or not self.operation_running:
            return False
        self.operation_running = False
        return True

    def close(self) -> None:
        self.closed = True
        self.operation_running = False
        self.check_generation += 1


@dataclass(slots=True)
class WizardFlow:
    step: WizardStep = WizardStep.GAME

    def advance(self) -> None:
        transitions = {
            WizardStep.GAME: WizardStep.ACTION,
            WizardStep.ACTION: WizardStep.PROGRESS,
        }
        try:
            self.step = transitions[self.step]
        except KeyError as exc:
            raise ValueError(f"cannot advance from {self.step.value}") from exc

    def back(self) -> None:
        if self.step is WizardStep.PROGRESS:
            raise ValueError("cannot go back while an operation is running")
        transitions = {
            WizardStep.ACTION: WizardStep.GAME,
            WizardStep.COMPLETE: WizardStep.ACTION,
        }
        try:
            self.step = transitions[self.step]
        except KeyError as exc:
            raise ValueError(f"cannot go back from {self.step.value}") from exc

    def complete(self) -> None:
        if self.step is not WizardStep.PROGRESS:
            raise ValueError(f"cannot complete from {self.step.value}")
        self.step = WizardStep.COMPLETE

    def restart(self) -> None:
        if self.step is not WizardStep.COMPLETE:
            raise ValueError(f"cannot restart from {self.step.value}")
        self.step = WizardStep.GAME
