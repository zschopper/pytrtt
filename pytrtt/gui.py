"""Setup-style Tk graphical adapter for PyTRTT."""

from __future__ import annotations

import argparse
import os
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from collections.abc import Callable
from functools import partial
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from pytrtt.application_paths import transaction_root, transaction_search_roots
from pytrtt.gui_flow import WizardFlow, WizardStep
from pytrtt.gui_support import (
    InstallationCandidate,
    InstallationInspection,
    InstallationStatus,
    apply_translation,
    check_translation,
    discover_steam_installations,
    find_interrupted_transactions,
    inspect_installation,
    installation_choices,
    load_game_catalog,
    recover_interrupted_transaction,
    restore_translation,
)
from pytrtt.i18n import Translator

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def apply_platform_style(root: tk.Tk) -> None:
    """Prefer native Windows widgets and typography when they are available."""
    style = ttk.Style(root)
    if os.name != "nt":
        return
    themes = set(style.theme_names())
    for theme in ("vista", "xpnative", "winnative"):
        if theme in themes:
            style.theme_use(theme)
            break
    families = set(tkfont.families(root))
    family = next(
        (name for name in ("Segoe UI Variable Text", "Segoe UI") if name in families),
        "Segoe UI",
    )
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        tkfont.nametofont(name).configure(family=family, size=9)
    root.configure(background="#f3f3f3")
    style.configure("WizardHeader.TFrame", background="#ffffff")
    style.configure("WizardContent.TFrame", background="#ffffff")
    style.configure("WizardFooter.TFrame", background="#f3f3f3")
    style.configure("Wizard.TLabel", background="#ffffff", font=(family, 9))
    style.configure("WizardTitle.TLabel", background="#ffffff", font=(family, 17, "bold"))
    style.configure("WizardHeading.TLabel", background="#ffffff", font=(family, 12, "bold"))
    style.configure("WizardResult.TLabel", background="#ffffff", font=(family, 10, "bold"))
    style.configure("Wizard.TRadiobutton", background="#ffffff", font=(family, 9))
    style.configure("Wizard.TLabelframe", background="#ffffff")
    style.configure("Wizard.TLabelframe.Label", background="#ffffff", font=(family, 9))
    style.configure("Wizard.TButton", padding=(12, 5), font=(family, 9))
    root.option_add("*tearOff", False)


class TranslationGui:
    """Four-step wizard that keeps the first implementation read-only."""

    def __init__(self, root: tk.Tk, translator: Translator) -> None:
        self.root = root
        apply_platform_style(root)
        self.translator = translator
        self.flow = WizardFlow()
        self.games = load_game_catalog()
        self.candidates: tuple[InstallationCandidate, ...] = ()
        self.current_candidate: InstallationCandidate | None = None
        self.current_inspection: InstallationInspection | None = None
        self.active_action: str | None = None
        self.closed = False
        self.safe_exit_requested = threading.Event()
        self.live_progress: dict[str, tuple[ttk.Progressbar, tk.StringVar, str, float, int]] = {}
        self.progress_generation = 0
        self.game_by_name = {game.display_name: game for game in self.games}
        self.game_name = tk.StringVar()
        self.path = tk.StringVar()
        self.discovery = tk.StringVar(value=self._text("gui_searching"))
        self.game_status = tk.StringVar(value=self._text("gui_status_waiting"))
        self.selected_action = tk.StringVar(value="check")
        self.install_note = tk.StringVar(value=self._text("gui_action_not_available"))
        self.restore_note = tk.StringVar(value=self._text("gui_action_not_available"))
        self.progress_text = tk.StringVar(value=self._text("gui_status_checking"))
        self.complete_title = tk.StringVar()
        self.complete_detail = tk.StringVar()
        self.pages: dict[WizardStep, ttk.Frame] = {}
        self._build()
        self._show_step()
        self.root.after(0, self._check_interrupted_transactions)

    def _text(self, key: str, **parameters: object) -> str:
        return self.translator.text(key, **parameters)

    def _schedule(self, callback: Callable[..., object], *arguments: object) -> None:
        if self.closed:
            return
        try:
            self.root.after(0, callback, *arguments)
        except tk.TclError:
            self.closed = True

    def _build(self) -> None:
        self.root.title(self._text("gui_title"))
        self.root.geometry("760x520")
        self.root.minsize(720, 490)
        self.root.protocol("WM_DELETE_WINDOW", self.exit)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        header = ttk.Frame(
            self.root,
            padding=(28, 22, 28, 18),
            style="WizardHeader.TFrame",
        )
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(
            header,
            text=self._text("gui_title"),
            style="WizardTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        self.step_label = ttk.Label(header, style="Wizard.TLabel")
        self.step_label.grid(row=0, column=1, sticky="e")
        self.content = ttk.Frame(
            self.root,
            padding=(28, 24),
            style="WizardContent.TFrame",
        )
        self.content.grid(row=1, column=0, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)
        self._build_game_page()
        self._build_action_page()
        self._build_progress_page()
        self._build_complete_page()
        ttk.Separator(self.root).grid(row=2, column=0, sticky="ew")
        navigation = ttk.Frame(
            self.root,
            padding=(24, 14),
            style="WizardFooter.TFrame",
        )
        navigation.grid(row=3, column=0, sticky="ew")
        navigation.columnconfigure(0, weight=1)
        self.back_button = ttk.Button(
            navigation,
            text=self._text("gui_back"),
            command=self.back,
            width=14,
            style="Wizard.TButton",
        )
        self.back_button.grid(row=0, column=1, padx=(8, 0))
        self.next_button = ttk.Button(
            navigation,
            text=self._text("gui_next"),
            command=self.next,
            width=14,
            style="Wizard.TButton",
        )
        self.next_button.grid(row=0, column=2, padx=(8, 0))
        self.exit_button = ttk.Button(
            navigation,
            text=self._text("gui_exit"),
            command=self.exit,
            width=14,
            style="Wizard.TButton",
        )
        self.exit_button.grid(row=0, column=3, padx=(8, 0))

    def _page(self, step: WizardStep) -> ttk.Frame:
        page = ttk.Frame(self.content, style="WizardContent.TFrame")
        page.grid(row=0, column=0, sticky="nsew")
        page.columnconfigure(0, weight=1)
        self.pages[step] = page
        return page

    def _heading(self, page: ttk.Frame, title: str, description: str) -> None:
        ttk.Label(page, text=title, style="WizardHeading.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w"
        )
        ttk.Label(page, text=description, wraplength=680, style="Wizard.TLabel").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(6, 22)
        )

    def _build_game_page(self) -> None:
        page = self._page(WizardStep.GAME)
        self._heading(page, self._text("gui_select_game"), self._text("gui_select_game_help"))
        ttk.Label(page, text=self._text("gui_game"), style="Wizard.TLabel").grid(
            row=2, column=0, sticky="w"
        )
        self.game_box = ttk.Combobox(
            page,
            textvariable=self.game_name,
            values=tuple(game.display_name for game in self.games),
            state="readonly",
        )
        self.game_box.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(5, 16))
        self.game_box.bind("<<ComboboxSelected>>", self._game_selected)
        ttk.Label(page, text=self._text("gui_installation"), style="Wizard.TLabel").grid(
            row=4, column=0, sticky="w"
        )
        self.installation_box = ttk.Combobox(page, textvariable=self.path, state="readonly")
        self.installation_box.grid(row=5, column=0, sticky="ew", pady=(5, 5))
        self.installation_box.bind("<<ComboboxSelected>>", self._installation_selected)
        ttk.Button(
            page,
            text=self._text("gui_browse"),
            command=self.browse,
            style="Wizard.TButton",
        ).grid(row=5, column=1, padx=(8, 0))
        ttk.Button(
            page,
            text=self._text("gui_refresh"),
            command=self.refresh,
            style="Wizard.TButton",
        ).grid(row=5, column=2, padx=(8, 0))
        ttk.Label(page, textvariable=self.discovery, style="Wizard.TLabel").grid(
            row=6, column=0, columnspan=3, sticky="w", pady=(0, 16)
        )
        status = ttk.LabelFrame(
            page,
            text=self._text("gui_installation_status"),
            padding=12,
            style="Wizard.TLabelframe",
        )
        status.grid(row=7, column=0, columnspan=3, sticky="ew")
        status.columnconfigure(0, weight=1)
        ttk.Label(
            status,
            textvariable=self.game_status,
            wraplength=650,
            style="Wizard.TLabel",
        ).grid(row=0, column=0, sticky="ew")
        self.check_progress = ttk.Progressbar(status, mode="determinate", maximum=3)
        self.check_progress.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self.check_progress.grid_remove()

    def _build_action_page(self) -> None:
        page = self._page(WizardStep.ACTION)
        self._heading(page, self._text("gui_select_action"), self._text("gui_select_action_help"))
        ttk.Radiobutton(
            page,
            text=self._text("gui_action_check"),
            variable=self.selected_action,
            value="check",
            style="Wizard.TRadiobutton",
        ).grid(row=2, column=0, sticky="w", pady=(0, 4))
        ttk.Label(
            page,
            text=self._text("gui_action_check_help"),
            wraplength=650,
            style="Wizard.TLabel",
        ).grid(row=3, column=0, sticky="w", padx=(24, 0), pady=(0, 16))
        self.install_option = ttk.Radiobutton(
            page,
            text=self._text("gui_action_install"),
            variable=self.selected_action,
            value="install",
            state="disabled",
            style="Wizard.TRadiobutton",
        )
        self.install_option.grid(row=4, column=0, sticky="w", pady=(0, 4))
        ttk.Label(
            page,
            textvariable=self.install_note,
            style="Wizard.TLabel",
        ).grid(row=5, column=0, sticky="w", padx=(24, 0), pady=(0, 12))
        self.restore_option = ttk.Radiobutton(
            page,
            text=self._text("gui_action_restore"),
            variable=self.selected_action,
            value="restore",
            state="disabled",
            style="Wizard.TRadiobutton",
        )
        self.restore_option.grid(row=6, column=0, sticky="w", pady=(0, 4))
        ttk.Label(page, textvariable=self.restore_note, style="Wizard.TLabel").grid(
            row=7, column=0, sticky="w", padx=(24, 0), pady=(0, 12)
        )

    def _build_progress_page(self) -> None:
        page = self._page(WizardStep.PROGRESS)
        self._heading(page, self._text("gui_progress"), self._text("gui_progress_help"))
        self.progress = ttk.Progressbar(page, mode="indeterminate")
        self.progress.grid(row=2, column=0, sticky="ew", pady=(12, 18))
        ttk.Label(
            page,
            textvariable=self.progress_text,
            wraplength=680,
            style="Wizard.TLabel",
        ).grid(row=3, column=0, sticky="w")

    def _build_complete_page(self) -> None:
        page = self._page(WizardStep.COMPLETE)
        self._heading(page, self._text("gui_complete"), self._text("gui_complete_help"))
        ttk.Label(
            page,
            textvariable=self.complete_title,
            style="WizardResult.TLabel",
        ).grid(row=2, column=0, sticky="w", pady=(12, 8))
        ttk.Label(
            page,
            textvariable=self.complete_detail,
            wraplength=680,
            style="Wizard.TLabel",
        ).grid(row=3, column=0, sticky="w")

    def _show_step(self) -> None:
        self.pages[self.flow.step].tkraise()
        number = list(WizardStep).index(self.flow.step) + 1
        self.step_label.configure(text=self._text("gui_step", current=number, total=4))
        self.back_button.configure(
            state=(
                "normal"
                if self.flow.step in {WizardStep.ACTION, WizardStep.COMPLETE}
                else "disabled"
            )
        )
        labels = {
            WizardStep.GAME: "gui_next",
            WizardStep.ACTION: "gui_start",
            WizardStep.PROGRESS: "gui_next",
            WizardStep.COMPLETE: "gui_restart",
        }
        self.next_button.configure(text=self._text(labels[self.flow.step]))
        if self.flow.step is WizardStep.GAME:
            enabled = self.current_inspection is not None and (
                self.current_inspection.status
                in {
                    InstallationStatus.CHANGES_AVAILABLE,
                    InstallationStatus.ALREADY_TRANSLATED,
                }
            )
            self.next_button.configure(state="normal" if enabled else "disabled")
        elif self.flow.step is WizardStep.PROGRESS:
            self.next_button.configure(state="disabled")
        else:
            self.next_button.configure(state="normal")
        self.exit_button.configure(
            state=(
                "disabled"
                if self.flow.step is WizardStep.PROGRESS and self.active_action == "restore"
                else "normal"
            )
        )

    def refresh(self) -> None:
        self.discovery.set(self._text("gui_searching"))
        self.next_button.configure(state="disabled")
        threading.Thread(target=self._discover, daemon=True).start()

    def _check_interrupted_transactions(self) -> None:
        interrupted = tuple(
            dict.fromkeys(
                item
                for root in transaction_search_roots()
                for item in find_interrupted_transactions(root)
            )
        )
        if not interrupted:
            self.refresh()
            return
        if not messagebox.askyesno(
            self._text("gui_recovery_title"),
            self._text("gui_recovery_message", count=len(interrupted)),
            icon="warning",
            parent=self.root,
        ):
            self.closed = True
            self.root.destroy()
            return
        self.discovery.set(self._text("gui_recovery_running"))
        self.check_progress.configure(mode="indeterminate")
        self.check_progress.grid()
        self.check_progress.start(50)
        threading.Thread(
            target=self._recover_interrupted_worker,
            args=(interrupted,),
            daemon=True,
        ).start()

    def _recover_interrupted_worker(self, interrupted: tuple[tuple[Path, Path], ...]) -> None:
        try:
            for game_dir, transaction in interrupted:
                recover_interrupted_transaction(game_dir, transaction)
        except (OSError, UnicodeError, ValueError, TypeError, RuntimeError) as exc:
            self._schedule(self._recovery_finished, f"{type(exc).__name__}: {exc}")
            return
        self._schedule(self._recovery_finished, "")

    def _recovery_finished(self, error: str) -> None:
        self.check_progress.stop()
        self.check_progress.grid_remove()
        self.check_progress.configure(mode="determinate", maximum=3, value=0)
        if error:
            messagebox.showerror(
                self._text("gui_recovery_error_title"),
                self._text("gui_recovery_error_message", detail=error),
                parent=self.root,
            )
            self.closed = True
            self.root.destroy()
            return
        messagebox.showinfo(
            self._text("gui_recovery_complete_title"),
            self._text("gui_recovery_complete_message"),
            parent=self.root,
        )
        self.refresh()

    def _discover(self) -> None:
        candidates = discover_steam_installations(self.games)
        self._schedule(self._show_discovery, candidates)

    def _show_discovery(self, candidates: tuple[InstallationCandidate, ...]) -> None:
        manual = tuple(item for item in self.candidates if item.source == "Manual")
        self.candidates = candidates + manual
        self.discovery.set(self._text("gui_found", count=len(candidates)))
        candidate = None
        if self.current_candidate is not None:
            choices = installation_choices(self.candidates, self.current_candidate.game.game_id)
            candidate = choices.get(str(self.current_candidate.path))
        if candidate is None:
            candidate = next(iter(self.candidates), None)
        if candidate is not None:
            self.game_name.set(candidate.game.display_name)
            self._select_candidate(candidate)
        elif self.games and not self.game_name.get():
            self.game_name.set(self.games[0].display_name)
            self._game_selected()

    def _game_selected(self, _event: object | None = None) -> None:
        game = self.game_by_name.get(self.game_name.get())
        if game is None:
            return
        choices = installation_choices(self.candidates, game.game_id)
        self.installation_box.configure(values=tuple(choices))
        candidate = choices.get(self.path.get()) or next(iter(choices.values()), None)
        if candidate is None:
            self.current_candidate = None
            self.current_inspection = None
            self.path.set("")
            self.game_status.set(self._text("gui_status_browse"))
            self._show_step()
        else:
            self._select_candidate(candidate)

    def _installation_selected(self, _event: object | None = None) -> None:
        game = self.game_by_name.get(self.game_name.get())
        if game is not None:
            candidate = installation_choices(self.candidates, game.game_id).get(self.path.get())
            if candidate is not None:
                self._select_candidate(candidate)

    def _select_candidate(self, candidate: InstallationCandidate) -> None:
        self.candidates = tuple(
            item
            for item in self.candidates
            if not (item.game.game_id == candidate.game.game_id and item.path == candidate.path)
        ) + (candidate,)
        self.installation_box.configure(
            values=tuple(installation_choices(self.candidates, candidate.game.game_id))
        )
        self.current_candidate = candidate
        self.path.set(str(candidate.path))
        self.current_inspection = inspect_installation(candidate, project_root=PROJECT_ROOT)
        messages = {
            InstallationStatus.NOT_FOUND: "gui_status_not_found",
            InstallationStatus.PACKAGE_UNAVAILABLE: "gui_status_no_package",
            InstallationStatus.READY: "gui_status_ready",
        }
        self.game_status.set(self._text(messages[self.current_inspection.status]))
        self._show_step()
        if self.current_inspection.status is InstallationStatus.READY:
            self.game_status.set(self._text("gui_status_checking"))
            self.check_progress.grid()
            self._start_live_progress("check", self.check_progress, self.game_status)
            threading.Thread(
                target=self._inspect_worker,
                args=(self.current_inspection,),
                daemon=True,
            ).start()

    def _inspect_worker(self, inspection: InstallationInspection) -> None:
        result = check_translation(
            inspection,
            transaction_roots=transaction_search_roots(),
            progress=self._queue_check_progress,
        )
        self._schedule(self._inspection_finished, result)

    def _inspection_finished(self, result: InstallationInspection) -> None:
        if self.current_candidate != result.candidate:
            return
        self._stop_live_progress("check")
        self.check_progress.grid_remove()
        self.current_inspection = result
        messages = {
            InstallationStatus.CHANGES_AVAILABLE: "gui_status_changes",
            InstallationStatus.ALREADY_TRANSLATED: "gui_status_translated",
            InstallationStatus.UNKNOWN_MODIFIED: "gui_status_unknown_modified",
            InstallationStatus.ERROR: "gui_status_error",
        }
        self.game_status.set(self._text(messages[result.status]))
        restorable = (
            result.status is InstallationStatus.ALREADY_TRANSLATED
            and result.restore_path is not None
        )
        installable = result.status is InstallationStatus.CHANGES_AVAILABLE
        self.install_option.configure(state="normal" if installable else "disabled")
        self.restore_option.configure(state="normal" if restorable else "disabled")
        self.install_note.set(
            self._text("gui_action_install_ready" if installable else "gui_action_not_available")
        )
        if installable:
            self.selected_action.set("install")
        elif restorable:
            self.selected_action.set("restore")
        elif result.status is InstallationStatus.ALREADY_TRANSLATED:
            self.selected_action.set("check")
        else:
            self.selected_action.set("check")
        if restorable:
            restore_note = "gui_action_restore_ready"
        elif result.status is InstallationStatus.ALREADY_TRANSLATED:
            restore_note = "gui_action_restore_unsafe"
        else:
            restore_note = "gui_action_not_available"
        self.restore_note.set(self._text(restore_note))
        self._show_step()

    def browse(self) -> None:
        game = self.game_by_name.get(self.game_name.get())
        if game is None:
            messagebox.showinfo(self._text("gui_title"), self._text("gui_choose_game"))
            return
        selected = filedialog.askdirectory(title=self._text("gui_browse_title"), mustexist=True)
        if selected:
            self._select_candidate(InstallationCandidate(game, Path(selected), "Manual"))

    def next(self) -> None:
        if self.flow.step is WizardStep.COMPLETE:
            self.flow.restart()
            if self.current_candidate is not None:
                self._select_candidate(self.current_candidate)
            else:
                self._show_step()
            return
        if self.flow.step is WizardStep.GAME and (
            self.current_inspection is None
            or self.current_inspection.status
            not in {
                InstallationStatus.CHANGES_AVAILABLE,
                InstallationStatus.ALREADY_TRANSLATED,
            }
        ):
            return
        if self.flow.step is WizardStep.ACTION:
            self.active_action = self.selected_action.get()
        self.flow.advance()
        self._show_step()
        if self.flow.step is WizardStep.PROGRESS:
            self._start_operation()

    def back(self) -> None:
        self.flow.back()
        self._show_step()

    def _start_operation(self) -> None:
        if self.current_inspection is None:
            return
        action = self.selected_action.get()
        keys = {
            "check": "gui_status_checking",
            "install": "gui_status_installing",
            "restore": "gui_status_restoring",
        }
        key = keys[action]
        self.progress_text.set(self._text(key))
        self._start_live_progress("operation", self.progress, self.progress_text)
        threading.Thread(
            target=self._operation_worker,
            args=(self.current_inspection, action),
            daemon=True,
        ).start()

    def _operation_worker(self, inspection: InstallationInspection, action: str) -> None:
        if action == "restore":
            result = restore_translation(
                inspection,
                transaction_roots=transaction_search_roots(),
                progress=self._queue_operation_progress,
            )
        elif action == "install":
            result = apply_translation(
                inspection,
                transaction_root=transaction_root(),
                progress=self._queue_operation_progress,
            )
        else:
            result = check_translation(
                inspection,
                transaction_roots=transaction_search_roots(),
                progress=self._queue_operation_progress,
            )
        if (
            action == "install"
            and self.safe_exit_requested.is_set()
            and result.status is InstallationStatus.ALREADY_TRANSLATED
            and result.restore_path is not None
        ):
            result = restore_translation(
                result,
                transaction_roots=transaction_search_roots(),
                progress=self._queue_operation_progress,
            )
            self._schedule(self._safe_exit_finished, result)
            return
        self._schedule(self._operation_finished, result)

    def _safe_exit_finished(self, result: InstallationInspection) -> None:
        if result.status is InstallationStatus.RESTORED:
            self.closed = True
            self.root.destroy()
            return
        self.safe_exit_requested.clear()
        self._operation_finished(result)

    def _queue_check_progress(self, current: int, total: int, message: str) -> None:
        self._schedule(
            self._show_progress,
            self.check_progress,
            current,
            total,
            message,
            self.game_status,
        )

    def _queue_operation_progress(self, current: int, total: int, message: str) -> None:
        if self.safe_exit_requested.is_set():
            return
        self._schedule(
            self._show_progress,
            self.progress,
            current,
            total,
            message,
            self.progress_text,
        )

    def _show_progress(
        self,
        bar: ttk.Progressbar,
        current: int,
        total: int,
        message: str,
        label: tk.StringVar,
    ) -> None:
        position = total if current >= total else current + 1
        name = "check" if bar is self.check_progress else "operation"
        resource_messages = {
            "gui_progress_detect_resources",
            "gui_progress_plan_resources",
        }
        if message in resource_messages:
            status = self._text(message, current=current, total=total)
        else:
            status = self._text(message)
        if name == "operation" and message not in resource_messages:
            status = self._text(
                "gui_progress_position",
                current=position,
                total=total,
                status=status,
            )
        if message in resource_messages:
            fraction = current / total if total else 1.0
            if message == "gui_progress_plan_resources":
                # Archive layout and input hashes are still built after all
                # translation resources have been prepared.
                fraction *= 0.9
            stage_start = (
                1 if message == "gui_progress_detect_resources" or name == "operation" else 2
            )
            stage_count = 3 if name == "check" else 4
            bar.stop()
            bar.configure(
                mode="determinate",
                maximum=stage_count,
                value=stage_start + fraction,
            )
        else:
            bar.configure(maximum=max(total, 1), value=current)
        state = self.live_progress.get(name)
        if state is not None:
            self.live_progress[name] = (state[0], state[1], status, state[3], state[4])
            label.set(self._elapsed_progress_text(status, state[3]))
        else:
            label.set(status)

    def _start_live_progress(self, name: str, bar: ttk.Progressbar, label: tk.StringVar) -> None:
        self.progress_generation += 1
        generation = self.progress_generation
        bar.stop()
        bar.configure(mode="determinate", maximum=1, value=0)
        self.live_progress[name] = (
            bar,
            label,
            label.get(),
            time.monotonic(),
            generation,
        )
        label.set(self._elapsed_progress_text(label.get(), time.monotonic()))
        self.root.after(1000, self._tick_live_progress, name, generation)

    def _tick_live_progress(self, name: str, generation: int) -> None:
        state = self.live_progress.get(name)
        if state is None or state[4] != generation or self.closed:
            return
        bar, label, status, started, _generation = state
        label.set(self._elapsed_progress_text(status, started))
        self.root.after(1000, self._tick_live_progress, name, generation)

    def _elapsed_progress_text(self, status: str, started: float) -> str:
        elapsed = max(0, int(time.monotonic() - started))
        minutes, seconds = divmod(elapsed, 60)
        return self._text(
            "gui_progress_elapsed",
            status=status,
            minutes=minutes,
            seconds=f"{seconds:02d}",
        )

    def _stop_live_progress(self, name: str) -> None:
        state = self.live_progress.pop(name, None)
        if state is None:
            return
        bar, _label, _status, _started, _generation = state
        bar.stop()
        bar.configure(mode="determinate", value=0)

    def _operation_finished(self, result: InstallationInspection) -> None:
        self._stop_live_progress("operation")
        self.active_action = None
        if result.status is InstallationStatus.ALREADY_TRANSLATED:
            title = self._text("gui_status_translated")
        elif result.status is InstallationStatus.CHANGES_AVAILABLE:
            title = self._text("gui_status_changes")
        elif result.status is InstallationStatus.UNKNOWN_MODIFIED:
            title = self._text("gui_status_unknown_modified")
        elif result.status is InstallationStatus.RESTORED:
            title = self._text("gui_status_restored")
        else:
            title = self._text("gui_status_error")
        self.complete_title.set(title)
        if result.status is InstallationStatus.ERROR:
            detail = result.detail
        elif result.status is InstallationStatus.UNKNOWN_MODIFIED:
            detail = self._text("gui_unknown_detail", detail=result.detail)
        elif result.status is InstallationStatus.RESTORED:
            detail = self._text("gui_restored_detail")
        else:
            detail = self._text("gui_missing", count=result.detail)
        self.complete_detail.set(detail)
        self.flow.complete()
        self._show_step()

    def exit(self) -> None:
        if self.flow.step is WizardStep.PROGRESS:
            if self.active_action == "check":
                self.closed = True
                self.root.destroy()
                return
            if self.active_action == "restore":
                messagebox.showinfo(
                    self._text("gui_exit_restore_title"),
                    self._text("gui_exit_restore_message"),
                    parent=self.root,
                )
                return
            if self.active_action == "install":
                choice = self._ask_install_exit()
                if choice == "safe":
                    self.safe_exit_requested.set()
                    self.exit_button.configure(state="disabled")
                    status = self._text("gui_exit_safe_wait")
                    self.progress_text.set(status)
                    state = self.live_progress.get("operation")
                    if state is not None:
                        self.live_progress["operation"] = (
                            state[0],
                            state[1],
                            status,
                            state[3],
                            state[4],
                        )
                elif choice == "force" and messagebox.askyesno(
                    self._text("gui_exit_force_title"),
                    self._text("gui_exit_force_message"),
                    icon="warning",
                    parent=self.root,
                ):
                    self.closed = True
                    self.root.destroy()
                return
        self.closed = True
        self.root.destroy()

    def _ask_install_exit(self) -> str:
        dialog = tk.Toplevel(self.root)
        dialog.title(self._text("gui_exit_title"))
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        result = tk.StringVar(value="continue")

        body = ttk.Frame(dialog, padding=24)
        body.grid(sticky="nsew")
        ttk.Label(
            body,
            text=self._text("gui_exit_title"),
            style="WizardHeading.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            body,
            text=self._text("gui_exit_message"),
            wraplength=560,
            style="Wizard.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(8, 18))

        choices = (
            ("continue", "gui_exit_continue", "gui_exit_continue_help"),
            ("safe", "gui_exit_safe", "gui_exit_safe_help"),
            ("force", "gui_exit_force", "gui_exit_force_help"),
        )

        def choose(value: str) -> None:
            result.set(value)
            dialog.destroy()

        for row, (value, title, help_key) in enumerate(choices, 2):
            option = ttk.Frame(body)
            option.grid(row=row, column=0, sticky="ew", pady=(0, 10))
            option.columnconfigure(1, weight=1)
            ttk.Button(
                option,
                text=self._text(title),
                command=partial(choose, value),
                width=23,
            ).grid(row=0, column=0, sticky="nw")
            ttk.Label(
                option,
                text=self._text(help_key),
                wraplength=340,
            ).grid(row=0, column=1, sticky="w", padx=(12, 0))

        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.root.wait_window(dialog)
        return result.get()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PyTRTT graphical client")
    parser.add_argument("--ui-language", default="hu")
    args = parser.parse_args(argv)
    root = tk.Tk()
    TranslationGui(root, Translator(args.ui_language))
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
