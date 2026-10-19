"""Setup-style GUI workflow state transitions."""

import pytest

from pytrtt.gui_flow import AsyncOperationState, WizardFlow, WizardStep


def assert_step(flow: WizardFlow, expected: WizardStep) -> None:
    assert flow.step is expected


def test_wizard_advances_and_returns_between_selection_steps() -> None:
    flow = WizardFlow()
    assert_step(flow, WizardStep.GAME)
    flow.advance()
    assert_step(flow, WizardStep.ACTION)
    flow.back()
    assert_step(flow, WizardStep.GAME)


def test_progress_cannot_be_left_until_operation_finishes() -> None:
    flow = WizardFlow(WizardStep.ACTION)
    flow.advance()
    assert_step(flow, WizardStep.PROGRESS)
    with pytest.raises(ValueError, match="operation is running"):
        flow.back()
    flow.complete()
    assert_step(flow, WizardStep.COMPLETE)


def test_completed_wizard_can_start_over() -> None:
    flow = WizardFlow(WizardStep.COMPLETE)
    flow.restart()
    assert_step(flow, WizardStep.GAME)


@pytest.mark.parametrize("step", [WizardStep.GAME, WizardStep.ACTION])
def test_invalid_completion_is_rejected(step: WizardStep) -> None:
    flow = WizardFlow(step)
    with pytest.raises(ValueError, match="cannot complete"):
        flow.complete()


def test_async_state_rejects_stale_checks_for_the_same_installation() -> None:
    state = AsyncOperationState()
    first = state.begin_check()
    second = state.begin_check()

    assert not state.accepts_check(first)
    assert state.accepts_check(second)


def test_async_state_prevents_double_operation_start() -> None:
    state = AsyncOperationState()

    assert state.begin_operation()
    assert not state.begin_operation()
    assert state.finish_operation()
    assert not state.finish_operation()
    assert state.begin_operation()


def test_closed_async_state_rejects_workers_and_invalidates_checks() -> None:
    state = AsyncOperationState()
    generation = state.begin_check()
    assert state.begin_operation()

    state.close()

    assert not state.accepts_check(generation)
    assert not state.begin_operation()
    assert not state.finish_operation()
