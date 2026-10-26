"""Qt-independent presentation data for the graphical client."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from pytrtt.gui_discovery import InstallationCandidate
from pytrtt.gui_support import InstallationInspection, InstallationStatus, inspect_installation
from pytrtt.packages.translation import TranslationDocument


class OperationItem(TypedDict):
    id: str
    available: bool
    reason: str


class OperationPayload(TypedDict):
    status: str
    detail: str
    credits: list[dict[str, str | list[str]]]
    operations: list[OperationItem]


def translation_credits_payload(
    document: TranslationDocument | None,
) -> list[dict[str, str | list[str]]]:
    """Return safe contributor data embedded in a translation document."""
    if document is None:
        return []
    return [{"role": credit.role, "names": list(credit.names)} for credit in document.credits]


def installation_payload(
    candidates: tuple[InstallationCandidate, ...], game_id: str, *, project_root: Path
) -> list[dict[str, str | bool]]:
    """Build safe serializable installation cards for one selected game."""
    payload = []
    for candidate in candidates:
        if candidate.game.game_id != game_id:
            continue
        inspection = inspect_installation(candidate, project_root=project_root)
        payload.append(
            {
                "path": str(candidate.path),
                "source": candidate.source,
                "build": candidate.build_id,
                "status": inspection.status.value,
                "selectable": inspection.status is InstallationStatus.READY,
                "launchable": candidate.source == "Steam" or bool(candidate.launch_uri),
            }
        )
    return payload


def operation_payload(inspection: InstallationInspection) -> OperationPayload:
    """Build operation availability from a completed backend inspection."""
    installable = inspection.status is InstallationStatus.CHANGES_AVAILABLE
    restorable = (
        inspection.status
        in {InstallationStatus.ALREADY_TRANSLATED, InstallationStatus.RECOVERY_AVAILABLE}
        and inspection.restore_path is not None
    )
    return {
        "status": inspection.status.value,
        "detail": inspection.detail,
        "credits": translation_credits_payload(
            inspection.prepared.document if inspection.prepared is not None else None
        ),
        "operations": [
            {"id": "check", "available": True, "reason": "Validate without changing files."},
            {
                "id": "install",
                "available": installable,
                "reason": (
                    "Translation changes are ready to install."
                    if installable
                    else "No safe installation change is currently available."
                ),
            },
            {
                "id": "restore",
                "available": restorable,
                "reason": (
                    "A verified recovery transaction is available."
                    if restorable
                    else "No verified recovery transaction is available."
                ),
            },
        ],
    }
