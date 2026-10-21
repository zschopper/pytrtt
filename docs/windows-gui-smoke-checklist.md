# Windows GUI smoke checklist

Use this checklist on a native, supported x64 Windows installation. Test the source launcher and the packaged build
separately. Record the Windows version, display scaling, PyTRTT version, build artifact SHA-256 and result for every
run. Do not use an installed game for modifying tests unless that exact installation was explicitly approved; use a
copy and preserve its first recovery data.

## Automated prerequisites

- Run `bash scripts/check.sh` in the development environment.
- Build a clean executable with `scripts\build-windows.cmd --clean`.
- Confirm the packaged executable starts from a path containing spaces and non-ASCII characters.
- Confirm the application starts while the network is disconnected.

## Scaling matrix

Repeat the visual and keyboard checks at 100%, 125%, 150% and 200% Windows display scaling. Start at the documented
minimum window size of 960 × 640, then test 1280 × 800 and a maximized window.

For every scaling level, verify:

- all four step markers, headings and primary actions remain visible or reachable by scrolling;
- cards, paths and translated text do not overlap or escape their containers;
- the Back and Continue/Start buttons remain on one row;
- selected, completed, disabled, warning and error states include text or shape changes, not color alone;
- the illustrated rail can be ignored or visually unavailable without preventing navigation;
- keyboard focus is visible and is not clipped by a scrolling container.

## Keyboard and accessibility

- Traverse every interactive control using `Tab` and `Shift+Tab`; confirm the order follows the visible workflow.
- Select cards and activate buttons using `Space` or `Enter`.
- Confirm inactive wizard pages cannot receive focus.
- Change the application language and verify the visible page updates immediately.
- Open and close the translation-credit dialog using the keyboard.
- Expand technical details and copy them without selecting the text manually.
- Confirm Ctrl+mouse-wheel and Ctrl+plus/minus do not zoom the interface.
- Confirm Windows high-contrast/forced-colors mode leaves controls and focus indicators distinguishable.

## Workflow states

- Verify zero, one and multiple discovered installations.
- Verify Steam, Epic Games, local configuration and custom-folder labels where available.
- Refresh installation discovery and confirm an unchanged selection is preserved.
- Change the game or installation and confirm dependent operation state is cleared.
- Exercise dry run, install/update, already-installed/no-change, restore and validation-error results on approved copies.
- During installation, request safe exit and confirm the original state is restored before the application closes.
- Force-close an approved fixture operation, restart PyTRTT, accept recovery and confirm recovery completes before use.
- Confirm the final page offers both another game and Exit.

## Packaged-content boundary

- Review `packaging/package-data.ignore` and the collection roots in `packaging/pytrtt.spec` whenever publishable runtime
  data was added, moved or removed; confirm required files are present and excluded development files are absent.
- Confirm the UI works with the network disconnected and does not request remote content.
- Attempt external navigation from developer tools only in a controlled test and confirm it is rejected.
- Confirm application images, scripts, styles, catalog and translation packages load outside the repository directory.
- Confirm the installed application does not require system Python, WebView2, Git, WSL or Bash.

Attach screenshots for the four scaling levels and retain the completed checklist with the tested artifact's SHA-256.
