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
