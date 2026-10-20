"""PySide6 and local Qt WebEngine graphical shell for PyTRTT."""

from __future__ import annotations

import json
import os
import sys
import threading
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import (
    QEvent,
    QObject,
    QSettings,
    QStandardPaths,
    Qt,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QCloseEvent, QIcon, QKeyEvent, QWheelEvent
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
)

from pytrtt.application_paths import (
    ensure_game_transaction_root,
    game_transaction_root,
    transaction_root,
    transaction_search_roots,
)
from pytrtt.gui_discovery import (
    GameCatalogEntry,
    InstallationCandidate,
    discover_installations,
    load_game_catalog,
)
from pytrtt.gui_presenter import (
    installation_payload,
    operation_payload,
)
from pytrtt.gui_resources import application_resource_root, gui_resource, is_packaged_file
from pytrtt.gui_support import (
    InstallationInspection,
    check_translation,
    find_interrupted_transactions_in_roots,
    inspect_installation,
    recover_interrupted_transaction,
    run_translation_operation,
)
from pytrtt.i18n import Translator
from pytrtt.version import VERSION

PROJECT_ROOT = application_resource_root()


def user_settings() -> QSettings:
    """Open the per-user INI file without writing beside the application."""
    local_root = os.environ.get("LOCALAPPDATA")
    if local_root:
        settings_dir = Path(local_root) / "PyTRTT"
    else:
        settings_dir = Path(
            QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
        )
    settings_dir.mkdir(parents=True, exist_ok=True)
    return QSettings(str(settings_dir / "settings.ini"), QSettings.Format.IniFormat)


class LocalApplicationPage(QWebEnginePage):
    """Web page that rejects navigation outside the packaged frontend."""

    def acceptNavigationRequest(  # noqa: N802 - Qt virtual method name
        self,
        url: QUrl | str,
        navigation_type: QWebEnginePage.NavigationType,
        is_main_frame: bool,
    ) -> bool:
        del navigation_type, is_main_frame
        return is_packaged_url(QUrl(url))


class FixedZoomWebEngineView(QWebEngineView):
    """Keep the application UI at its designed scale."""

    def __init__(self, parent: QMainWindow) -> None:
        super().__init__(parent)
        application = QApplication.instance()
        if application is not None:
            application.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        del watched
        if (
            event.type() == QEvent.Type.Wheel
            and isinstance(event, QWheelEvent)
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            event.accept()
            return True
        return False

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 - Qt virtual method name
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            event.accept()
            return
        super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt virtual method name
        zoom_keys = {Qt.Key.Key_Plus, Qt.Key.Key_Minus, Qt.Key.Key_Equal, Qt.Key.Key_0}
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.key() in zoom_keys:
            event.accept()
            return
        super().keyPressEvent(event)


class ConfirmationDialog(QDialog):
    """Small pre-laid-out native confirmation dialog with localized buttons."""

    def __init__(
        self,
        parent: QMainWindow,
        *,
        title: str,
        message: str,
        accept_text: str,
        reject_text: str,
        destructive: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(560)

        message_label = QLabel(message, self)
        message_label.setWordWrap(True)
        message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        accept_button = QPushButton(accept_text, self)
        reject_button = QPushButton(reject_text, self)
        accept_button.setDefault(not destructive)
        reject_button.setDefault(destructive)
        accept_button.clicked.connect(self.accept)
        reject_button.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(accept_button)
        buttons.addWidget(reject_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 18)
        layout.setSpacing(20)
        layout.addWidget(message_label)
        layout.addLayout(buttons)
        self.adjustSize()


def is_packaged_url(url: QUrl) -> bool:
    """Return whether a URL resolves inside the packaged GUI resource directory."""
    if not url.isLocalFile():
        return False
    return is_packaged_file(url.toLocalFile())


class GuiBridge(QObject):
    """Narrow typed bridge between the local frontend and GUI services."""

    operationStateReady = Signal(str)
    validationProgress = Signal(str)
    operationProgress = Signal(str)
    operationFinished = Signal(str)
    safeExitCompleted = Signal()
    applicationLanguageChanged = Signal(str)
    frontendReady = Signal()

    def __init__(
        self,
        translator: Translator,
        window: QMainWindow,
        settings: QSettings,
        *,
        recovery_in_game: bool = False,
    ) -> None:
        super().__init__(window)
        self._translator = translator
        self._window = window
        self._settings = settings
        self._recovery_in_game = recovery_in_game
        self._games = load_game_catalog()
        self._candidates: dict[tuple[str, str], InstallationCandidate] = {}
        self._inspection_generation = 0
        self._inspections: dict[tuple[str, str], InstallationInspection] = {}
        self._operation_running = False
        self._operation_generation = 0
        self._active_action: str | None = None
        self._safe_exit_requested = threading.Event()

    @property
    def operation_running(self) -> bool:
        """Return whether a background operation currently owns the game files."""
        return self._operation_running

    @property
    def games(self) -> tuple[GameCatalogEntry, ...]:
        """Return the immutable catalog used by discovery and recovery."""
        return self._games

    @property
    def active_action(self) -> str | None:
        """Return the operation whose worker is currently running."""
        return self._active_action

    @property
    def safe_exit_pending(self) -> bool:
        """Return whether the install should be rolled back before closing."""
        return self._safe_exit_requested.is_set()

    def request_safe_exit(self) -> None:
        """Request rollback after the current install reaches a safe boundary."""
        self._safe_exit_requested.set()

    @Slot(result=str)
    def initialState(self) -> str:  # noqa: N802 - JavaScript API name
        games = [
            {
                "id": game.game_id,
                "name": game.display_name,
                "available": game.package_available,
                "credits": [],
            }
            for game in self._games
        ]
        return json.dumps(
            {
                "locale": self._settings.value("ui/language", self._translator.language, type=str),
                "showWelcome": self._settings.value("ui/show_welcome", True, type=bool),
                "version": VERSION,
                "games": games,
            },
            ensure_ascii=False,
        )

    @Slot()
    def exitApplication(self) -> None:  # noqa: N802 - JavaScript API name
        """Close the application after the user has reviewed the result."""
        self._window.close()

    @Slot(str)
    def copyText(self, value: str) -> None:  # noqa: N802 - JavaScript API name
        """Copy a result detail without exposing general clipboard access to the page."""
        QApplication.clipboard().setText(value[:100_000])

    @Slot()
    def reportFrontendReady(self) -> None:  # noqa: N802 - JavaScript API name
        """Report that local content, JavaScript and the typed bridge initialized."""
        self.frontendReady.emit()

    @Slot(str)
    def setApplicationLanguage(self, language: str) -> None:  # noqa: N802 - JavaScript API name
        """Keep native Qt dialogs synchronized with the web UI locale."""
        if language not in {"en", "hu"} or language == self._translator.language:
            return
        self._translator = Translator(language)
        self._settings.setValue("ui/language", language)
        self.applicationLanguageChanged.emit(language)

    @Slot(bool)
    def setWelcomeEnabled(self, enabled: bool) -> None:  # noqa: N802 - JavaScript API name
        """Persist whether the welcome page should be shown on future starts."""
        self._settings.setValue("ui/show_welcome", enabled)

    @Slot(str, result=str)
    def discoverInstallations(self, game_id: str) -> str:  # noqa: N802 - JavaScript API name
        """Discover installation cards for a catalog game."""
        if not any(game.game_id == game_id for game in self._games):
            return json.dumps({"installations": [], "error": "Unknown game."})
        candidates = discover_installations(self._games)
        for candidate in candidates:
            self._candidates[(candidate.game.game_id, str(candidate.path))] = candidate
        return json.dumps(
            {
                "installations": installation_payload(
                    candidates,
                    game_id,
                    project_root=PROJECT_ROOT,
                )
            },
            ensure_ascii=False,
        )

    @Slot(str, result=str)
    def browseInstallation(self, game_id: str) -> str:  # noqa: N802 - JavaScript API name
        """Ask for and validate a custom installation folder."""
        game = next((item for item in self._games if item.game_id == game_id), None)
        if game is None:
            return json.dumps({"installation": None, "error": "Unknown game."})
        selected = QFileDialog.getExistingDirectory(
            self._window,
            self._translator.text("gui_browse_title"),
        )
        if not selected:
            return json.dumps({"installation": None})
        candidate = InstallationCandidate(game, Path(selected), "Custom folder")
        self._candidates[(game_id, str(candidate.path))] = candidate
        payload = installation_payload((candidate,), game_id, project_root=PROJECT_ROOT)
        return json.dumps({"installation": payload[0]}, ensure_ascii=False)

    @Slot(str, str, result=int)
    def requestOperationState(  # noqa: N802 - JavaScript API name
        self, game_id: str, installation_path: str
    ) -> int:
        """Validate a selected installation without blocking the renderer."""
        candidate = self._candidates.get((game_id, installation_path))
        self._inspection_generation += 1
        generation = self._inspection_generation
        if candidate is None:
            self.operationStateReady.emit(
                json.dumps({"generation": generation, "error": "Unknown installation."})
            )
            return generation
        threading.Thread(
            target=self._inspect_worker,
            args=(candidate, generation),
            daemon=True,
        ).start()
        return generation

    def _inspect_worker(self, candidate: InstallationCandidate, generation: int) -> None:
        try:
            inspection = inspect_installation(candidate, project_root=PROJECT_ROOT)
            result = check_translation(
                inspection,
                transaction_roots=transaction_search_roots(candidate.path),
                progress=lambda current, total, message: self.validationProgress.emit(
                    json.dumps(
                        {
                            "generation": generation,
                            "current": current,
                            "total": total,
                            "message": message,
                        }
                    )
                ),
            )
            if generation == self._inspection_generation:
                self._inspections[(candidate.game.game_id, str(candidate.path))] = result
            payload: dict[str, object] = dict(operation_payload(result))
        except Exception as exc:  # Boundary converts backend failures into UI state.
            payload = {"error": str(exc)}
        payload["generation"] = generation
        self.operationStateReady.emit(json.dumps(payload, ensure_ascii=False))

    @Slot(str, str, str, result=int)
    def executeOperation(  # noqa: N802 - JavaScript API name
        self, game_id: str, installation_path: str, action: str
    ) -> int:
        """Start one validated backend operation and reject duplicate starts."""
        self._operation_generation += 1
        generation = self._operation_generation
        inspection = self._inspections.get((game_id, installation_path))
        allowed = (
            inspection is not None
            and action in {"check", "install", "restore"}
            and next(
                (
                    item["available"]
                    for item in operation_payload(inspection)["operations"]
                    if item["id"] == action
                ),
                False,
            )
        )
        if self._operation_running or not allowed or inspection is None:
            self.operationFinished.emit(
                json.dumps(
                    {
                        "generation": generation,
                        "status": "error",
                        "detail": "The selected operation is not available.",
                    }
                )
            )
            return generation
        self._operation_running = True
        self._active_action = action
        self._safe_exit_requested.clear()
        threading.Thread(
            target=self._operation_worker,
            args=(inspection, action, generation),
            daemon=True,
        ).start()
        return generation

    def _operation_worker(
        self, inspection: InstallationInspection, action: str, generation: int
    ) -> None:
        recovery_root = (
            game_transaction_root(inspection.candidate.path)
            if self._recovery_in_game and action == "install"
            else transaction_root()
        )
        result, safe_exit_completed = run_translation_operation(
            inspection,
            action,
            transaction_root=recovery_root,
            transaction_roots=transaction_search_roots(inspection.candidate.path),
            safe_exit_requested=self._safe_exit_requested.is_set,
            progress=lambda current, total, message: self.operationProgress.emit(
                json.dumps(
                    {
                        "generation": generation,
                        "current": current,
                        "total": total,
                        "message": message,
                    }
                )
            ),
        )
        if self._recovery_in_game and action == "install" and result.restore_path is not None:
            ensure_game_transaction_root(inspection.candidate.path)
        self._operation_running = False
        self._active_action = None
        self._safe_exit_requested.clear()
        self._inspections[(result.candidate.game.game_id, str(result.candidate.path))] = result
        self.operationFinished.emit(
            json.dumps(
                {
                    "generation": generation,
                    "status": result.status.value,
                    "detail": result.detail,
                    "recoveryPath": str(result.restore_path) if result.restore_path else "",
                },
                ensure_ascii=False,
            )
        )
        if safe_exit_completed:
            self.safeExitCompleted.emit()


class TranslationWindow(QMainWindow):
    """Top-level window hosting the packaged local wizard frontend."""

    def __init__(
        self,
        translator: Translator,
        *,
        settings: QSettings | None = None,
        recovery_in_game: bool = False,
    ) -> None:
        super().__init__()
        self._translator = translator
        self.setWindowTitle(translator.text("gui_title"))
        self.setWindowIcon(QIcon(str(gui_resource("app-icon.png"))))
        self.setMinimumSize(960, 640)
        self.resize(1280, 800)

        self.profile = QWebEngineProfile.defaultProfile()
        self.profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
        )
        self.profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)

        self.page = LocalApplicationPage(self.profile, self)
        self.page.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,
            False,
        )
        self.page.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls,
            True,
        )
        self.page.featurePermissionRequested.connect(
            lambda origin, feature: self.page.setFeaturePermission(
                origin,
                feature,
                QWebEnginePage.PermissionPolicy.PermissionDeniedByUser,
            )
        )

        self.settings = settings if settings is not None else user_settings()
        self.bridge = GuiBridge(
            translator,
            self,
            self.settings,
            recovery_in_game=recovery_in_game,
        )
        self.bridge.safeExitCompleted.connect(self.close)
        self.bridge.applicationLanguageChanged.connect(self._set_application_language)
        self.channel = QWebChannel(self.page)
        self.channel.registerObject("pytrtt", self.bridge)
        self.page.setWebChannel(self.channel)

        view = FixedZoomWebEngineView(self)
        view.setPage(self.page)
        view.setZoomFactor(1.0)
        self.setCentralWidget(view)
        view.setUrl(QUrl.fromLocalFile(str(gui_resource("index.html"))))

    def recover_interrupted_operations(self) -> None:
        """Offer recovery for journaled writes left incomplete by an earlier run."""
        candidates = discover_installations(self.bridge.games)
        roots = tuple(
            dict.fromkeys(
                root
                for candidate in (None, *candidates)
                for root in transaction_search_roots(None if candidate is None else candidate.path)
            )
        )
        interrupted = find_interrupted_transactions_in_roots(roots)
        if not interrupted:
            return
        prompt = ConfirmationDialog(
            self,
            title=self._translator.text("gui_recovery_title"),
            message=self._translator.text("gui_recovery_message", count=len(interrupted)),
            accept_text=self._translator.text("gui_confirm_yes"),
            reject_text=self._translator.text("gui_confirm_no"),
        )
        if prompt.exec() != QDialog.DialogCode.Accepted:
            return

        progress = QProgressDialog(
            self._translator.text("gui_recovery_running"),
            "",
            0,
            len(interrupted),
            self,
        )
        disabled_cancel = QPushButton(progress)
        disabled_cancel.hide()
        progress.setCancelButton(disabled_cancel)
        progress.setWindowTitle(self._translator.text("gui_recovery_title"))
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.show()
        try:
            for position, (game_dir, transaction) in enumerate(interrupted, 1):
                progress.setLabelText(
                    f"{self._translator.text('gui_recovery_running')}\n{game_dir}"
                )
                QApplication.processEvents()
                recover_interrupted_transaction(game_dir, transaction)
                progress.setValue(position)
            QMessageBox.information(
                self,
                self._translator.text("gui_recovery_complete_title"),
                self._translator.text("gui_recovery_complete_message"),
            )
        except Exception as exc:  # Native recovery boundary keeps journals for retry.
            QMessageBox.critical(
                self,
                self._translator.text("gui_recovery_error_title"),
                self._translator.text("gui_recovery_error_message", detail=str(exc)),
            )
        finally:
            progress.close()

    @Slot(str)
    def _set_application_language(self, language: str) -> None:
        """Use the web UI locale for subsequent native dialogs."""
        self._translator = Translator(language)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt virtual method name
        """Protect active game-file writes from an unsafe window close."""
        if not self.bridge.operation_running or self.bridge.active_action == "check":
            event.accept()
            return

        if self.bridge.active_action == "restore" or self.bridge.safe_exit_pending:
            QMessageBox.information(
                self,
                self._translator.text("gui_exit_restore_title"),
                self._translator.text("gui_exit_restore_message"),
            )
            event.ignore()
            return

        prompt = QMessageBox(self)
        prompt.setIcon(QMessageBox.Icon.Warning)
        prompt.setWindowTitle(self._translator.text("gui_exit_title"))
        prompt.setText(self._translator.text("gui_exit_message"))
        continue_button = prompt.addButton(
            self._translator.text("gui_exit_continue"),
            QMessageBox.ButtonRole.RejectRole,
        )
        safe_button = prompt.addButton(
            self._translator.text("gui_exit_safe"),
            QMessageBox.ButtonRole.AcceptRole,
        )
        force_button = prompt.addButton(
            self._translator.text("gui_exit_force"),
            QMessageBox.ButtonRole.DestructiveRole,
        )
        prompt.setDefaultButton(continue_button)
        prompt.setEscapeButton(continue_button)
        prompt.exec()

        if prompt.clickedButton() is safe_button:
            self.bridge.request_safe_exit()
            event.ignore()
            return
        if prompt.clickedButton() is force_button:
            confirmation = ConfirmationDialog(
                self,
                title=self._translator.text("gui_exit_force_title"),
                message=self._translator.text("gui_exit_force_message"),
                accept_text=self._translator.text("gui_confirm_yes"),
                reject_text=self._translator.text("gui_confirm_no"),
                destructive=True,
            )
            if confirmation.exec() == QDialog.DialogCode.Accepted:
                event.accept()
                return
        event.ignore()


def main(arguments: Sequence[str] | None = None) -> int:
    """Run the Qt graphical client."""
    parser_arguments = list(sys.argv[1:] if arguments is None else arguments)
    locale = "hu" if "--hu" in parser_arguments else "en"
    recovery_in_game = "--recovery-in-game" in parser_arguments
    smoke_test = "--smoke-test" in parser_arguments
    qt_arguments = [
        item
        for item in parser_arguments
        if item not in {"--hu", "--recovery-in-game", "--smoke-test"}
    ]
    if sys.platform == "win32":
        chromium_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").split()
        if "--disable-direct-composition" not in chromium_flags:
            chromium_flags.append("--disable-direct-composition")
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(chromium_flags)
    application = QApplication([sys.argv[0], *qt_arguments])
    settings = user_settings()
    if "--hu" not in parser_arguments:
        stored_locale = settings.value("ui/language", locale, type=str)
        if stored_locale in {"en", "hu"}:
            locale = str(stored_locale)
    window = TranslationWindow(
        Translator(locale),
        settings=settings,
        recovery_in_game=recovery_in_game,
    )
    if smoke_test:
        window.bridge.frontendReady.connect(lambda: application.exit(0))
        QTimer.singleShot(30_000, lambda: application.exit(2))
    window.show()
    if not smoke_test:
        QTimer.singleShot(0, window.recover_interrupted_operations)
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
