from pathlib import Path

import pytest

from pytrtt.gui_resources import application_resource_root, gui_resource, is_packaged_file


def test_application_resource_root_contains_translation_packages() -> None:
    root = application_resource_root()
    assert (root / "translations/tomb-raider/hu.json").is_file()
    assert (root / "pytrtt/resources/gui/index.html").is_file()


def test_packaged_gui_shell_has_local_content_security_policy() -> None:
    html = gui_resource("index.html").read_text(encoding="utf-8")
    assert "default-src 'none'" in html
    assert "connect-src 'none'" in html
    assert "qrc:///qtwebchannel/qwebchannel.js" in html
    assert "http://" not in html
    assert "https://" not in html
    assert 'src="app-icon.png"' in html
    assert gui_resource("app-icon.png").is_file()
    assert 'src="brand-lockup.png"' in html
    assert gui_resource("brand-lockup.png").is_file()
    assert "bridge.reportFrontendReady()" in gui_resource("app.js").read_text(encoding="utf-8")


def test_game_selection_updates_accessible_state_and_navigation() -> None:
    script = gui_resource("app.js").read_text(encoding="utf-8")
    styles = gui_resource("styles.css").read_text(encoding="utf-8")
    assert 'card.addEventListener("click"' in script
    assert 'card.setAttribute("aria-pressed", "false")' in script
    assert 'candidate.classList.toggle("selected", selected)' in script
    assert 'document.querySelector("#continue").disabled = false' in script
    assert ".game-card.selected" in styles
    assert "padding: 34px 4px" in styles
    assert 'selected.className = "selected-indicator"' in script
    assert "selected.textContent = selectedIndicatorText()" in script
    assert ".game-card { display: grid;" in styles
    assert ".game-card, .installation-card { position: relative;" in styles
    assert ".selected-indicator { position: absolute; top: 16px; right: 18px;" in styles
    assert ".selected-indicator[hidden]" in styles


def test_installation_step_uses_the_typed_bridge_and_preserves_selection() -> None:
    script = gui_resource("app.js").read_text(encoding="utf-8")
    assert "bridge.discoverInstallations(selectedGame.id" in script
    assert "bridge.browseInstallation(selectedGame.id" in script
    assert "const preserved = selectedInstallation?.path ?? null" in script
    assert "selectable.length === 1" in script
    assert "let installationChoices = []" in script
    assert "mergeInstallations(installationChoices, result.installation)" in script
    assert "source.textContent = translatedText(installation.source, appLanguage)" in script


def test_wizard_keeps_navigation_fixed_while_page_content_scrolls() -> None:
    styles = gui_resource("styles.css").read_text(encoding="utf-8")
    assert "html, body { width: 100%; height: 100%; overflow: hidden; }" in styles
    assert "max-width: 1440px" not in styles
    assert "grid-template-rows: auto minmax(0, 1fr) auto" in styles
    assert ".installation-page { min-height: 0;" in styles
    assert "backdrop-filter" not in styles
    assert "@media (forced-colors: active)" in styles
    assert ".rail { background-image: none; }" in styles


def test_wizard_pages_crossfade_and_respect_reduced_motion() -> None:
    html = gui_resource("index.html").read_text(encoding="utf-8")
    script = gui_resource("app.js").read_text(encoding="utf-8")
    styles = gui_resource("styles.css").read_text(encoding="utf-8")
    assert 'id="welcome" class="welcome-page page-panel active"' in html
    assert "function switchPage(from, to, direction)" in script
    assert 'from.setAttribute("aria-hidden", "true")' in script
    assert ".page-panel.active" in styles
    assert "prefers-reduced-motion: reduce" in styles


def test_sidebar_shows_completed_route_between_steps() -> None:
    script = gui_resource("app.js").read_text(encoding="utf-8")
    styles = gui_resource("styles.css").read_text(encoding="utf-8")
    assert "function setActiveStep(index)" in script
    assert 'step.classList.toggle("completed", position < index)' in script
    assert ".steps li:not(:last-child)::after" in styles
    assert ".steps li.completed:not(:last-child)::after" in styles
    assert "background-size: 100% 100%, auto" in styles
    assert "background-position: center, center center" in styles
    assert ".rail::after" in styles
    assert ".brand::before" in styles
    assert "grid-template-columns: repeat(auto-fit, minmax(240px, 1fr))" in styles


def test_operation_step_waits_for_current_background_validation() -> None:
    script = gui_resource("app.js").read_text(encoding="utf-8")
    assert "bridge.requestOperationState(selectedGame.id, selectedInstallation.path" in script
    assert "state.generation === operationGeneration && currentStep === 3" in script
    assert 'document.querySelector("#language-card").hidden = operation.id !== "install"' in script
    assert "bridge.validationProgress.connect" in script
    assert "progress.generation !== operationGeneration" in script
    assert "bar.value = Math.min(progress.current, progress.total)" in script
    assert "function installationStateLabel(status)" in script
    assert "installationStateLabel(state.status)" in script
    assert 'already_translated: "Translation already installed"' in script
    assert "const label = translatedText(" in script


def test_progress_step_uses_generation_guard_and_operation_context() -> None:
    script = gui_resource("app.js").read_text(encoding="utf-8")
    assert "bridge.executeOperation(" in script
    assert "progress.generation !== executionGeneration" in script
    assert "result.generation !== executionGeneration" in script
    assert 'id="confirm-modification"' not in gui_resource("index.html").read_text(encoding="utf-8")
    assert 'document.querySelector("#context-game").textContent = selectedGame.name' in script
    assert (
        'document.querySelector("#context-path").textContent = selectedInstallation.path' in script
    )
    assert "function operationProgressCopy(message)" in script
    assert 'bar.removeAttribute("value")' in script
    assert "setInterval(updateElapsedTime, 1000)" in script
    assert "function formatDuration(seconds)" in script
    assert 'document.querySelector("#result-duration").textContent' in script
    assert 'const recovery = document.querySelector("#result-recovery")' in script
    assert 'return "< 1 second"' in script
    assert '"gui_progress_install_resources"' in script
    assert '"gui_progress_restore_bytes"' in script
    assert "progress.current * 100 / progress.total" in script
    assert 'document.querySelector(".selection-summary").hidden = true' in script


def test_progress_step_can_show_translation_credits_in_an_overlay() -> None:
    html = gui_resource("index.html").read_text(encoding="utf-8")
    script = gui_resource("app.js").read_text(encoding="utf-8")
    styles = gui_resource("styles.css").read_text(encoding="utf-8")
    assert 'id="credits-button"' in html
    assert 'id="credits-dialog"' in html
    assert "selectedGame.credits.length" in script
    assert "function showTranslationCredits()" in script
    assert 'credit.names.join(", ")' in script
    assert ".showModal()" in script
    assert "#credits-dialog::backdrop" in styles


def test_unnumbered_welcome_page_precedes_the_four_step_wizard() -> None:
    html = gui_resource("index.html").read_text(encoding="utf-8")
    script = gui_resource("app.js").read_text(encoding="utf-8")
    assert '<p id="step-counter">Welcome</p>' in html
    assert 'id="app-language"' in html
    assert 'id="skip-welcome"' in html
    assert "let currentStep = 0" in script
    assert "function startWizard()" in script
    assert "state.showWelcome" in script
    assert "bridge.setWelcomeEnabled(!event.target.checked)" in script
    assert 'id="app-version"' in html
    assert "state.version" in script


def test_application_language_switches_immediately_and_uses_flag_labels() -> None:
    html = gui_resource("index.html").read_text(encoding="utf-8")
    script = gui_resource("app.js").read_text(encoding="utf-8")
    assert 'data-language="en" aria-pressed="true"' in html
    assert 'data-language="hu" aria-pressed="false"' in html
    assert "🇬🇧" in html
    assert "🇭🇺" in html
    assert 'button.addEventListener("click"' in script
    assert 'button.setAttribute("aria-pressed"' in script
    assert "function applyLanguage(language)" in script
    assert "document.documentElement.lang = language" in script
    assert "bridge.setApplicationLanguage(language)" in script
    assert "if (root === null)" in script
    assert 'document.addEventListener("wheel"' in script
    assert "event.ctrlKey" in script


def test_application_language_prefers_matching_supported_translation_language() -> None:
    script = gui_resource("app.js").read_text(encoding="utf-8")
    assert "function preferMatchingTargetLanguage()" in script
    assert "option.value === appLanguage" in script
    assert "targetLanguageChosenByUser" in script
    assert 'document.querySelector("#target-language").addEventListener("change"' in script


def test_completed_operation_can_restart_with_another_game() -> None:
    html = gui_resource("index.html").read_text(encoding="utf-8")
    script = gui_resource("app.js").read_text(encoding="utf-8")
    assert "function restartWizard()" in script
    assert "executionGeneration = null" in script
    assert "selectedGame = null" in script
    assert 'document.querySelector("#summary").textContent = "No game selected"' in script
    assert 'document.querySelector("#language-card").hidden = true' in script
    assert 'document.querySelector("#restart").addEventListener("click", restartWizard)' in script
    assert 'id="exit-application"' in html
    assert "bridge.exitApplication()" in script
    assert "function resultStatusLabel(status)" in script
    assert 'document.querySelector(".progress-copy").hidden = true' in script
    assert 'result.detail !== "0"' in script
    assert 'id="result-detail-panel"' in html
    assert 'id="copy-result-detail"' in html
    assert "bridge.copyText" in script
    assert ".result-detail[hidden]" in gui_resource("styles.css").read_text(encoding="utf-8")


def test_selection_summary_sits_above_the_navigation_actions() -> None:
    html = gui_resource("index.html").read_text(encoding="utf-8")
    styles = gui_resource("styles.css").read_text(encoding="utf-8")
    assert 'class="selection-summary"' in html
    assert 'class="footer-actions"' in html
    assert html.index("<footer>") < html.index('class="selection-summary"')
    assert ".selection-summary { grid-column: 1 / -1;" in styles
    assert ".footer-actions { grid-column: 2; display: flex; flex-wrap: nowrap;" in styles


def test_gui_resource_lookup_is_cwd_independent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(Path.home())
    assert gui_resource("styles.css").is_file()


@pytest.mark.parametrize("name", ["../gui.py", "/tmp/gui.html"])
def test_gui_resource_lookup_rejects_unsafe_paths(name: str) -> None:
    with pytest.raises(ValueError, match="safe relative"):
        gui_resource(name)


def test_navigation_accepts_packaged_files_and_rejects_other_paths(tmp_path: Path) -> None:
    assert is_packaged_file(gui_resource("index.html"))
    assert not is_packaged_file(tmp_path / "outside.html")
