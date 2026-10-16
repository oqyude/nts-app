"""Self-check (``reverse``) GUI.

Variant of the NTS calculator GUI: instead of computing from a raw input,
it loads a self-check JSON file (with both ``input`` and ``expected`` keys),
runs the canonical :func:`nts.core.compute`, and renders a checklist of
field-by-field comparisons produced by :func:`nts.checker.verify`.

The layout differs from :mod:`nts.gui`:
  * no manual experiment grid — the file is the single source of truth;
  * the result is a colour-coded checklist (green ✓ / red ✗) instead of an
    equation/coeffs/grubbs/fisher panel;
  * export writes the same checklist as plain text (see
    :func:`nts.checker.print_checklist`).

Drag-and-drop uses the same TkinterDnD setup as :mod:`nts.gui`; if the
optional ``tkinterdnd2`` package is missing, a hint label is shown and the
``Browse`` button still works.
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Optional

from .checker import CheckResult, parse_self_check_file, print_checklist, verify
from .core import ComputeResult, InputData, compute
from .gui import DND_AVAILABLE, DND_FILES, TkinterDnD, extract_dropped_path
from .i18n import DEFAULT_LANGUAGE, I18N, LANGUAGES, normalize_lang


# Keep the checklist row schema tight: one tuple per visible column. Order
# matches the Treeview ``columns=`` declaration in :meth:`ReverseApp._build_ui`.
_CHECKLIST_COLUMNS: tuple[str, ...] = (
    "icon", "name", "actual", "expected", "diff", "message",
)


def _format_cell(value: Any, missing_label: str) -> str:
    """Render a CheckEntry field for the Treeview cell.

    - ``None`` becomes the localized "missing" label so the row stays readable.
    - floats are formatted with ``%g`` (6 significant digits) to mirror CLI.
    - everything else falls back to ``repr`` (keeps quotes ``str``/``bool``).
    """
    if value is None:
        return missing_label
    if isinstance(value, float):
        return f"{value:.6g}"
    return repr(value)


def _format_diff(diff: Optional[float], missing_label: str) -> str:
    if diff is None:
        return missing_label
    return f"{diff:.6g}"


class ReverseApp(TkinterDnD.Tk if DND_AVAILABLE else tk.Tk):  # type: ignore[misc]
    """Self-check GUI window."""

    def __init__(self) -> None:
        super().__init__()
        self.geometry("900x560")
        self.lang = tk.StringVar(value=DEFAULT_LANGUAGE)
        self.selected_file = tk.StringVar(value="")
        self.last_payload: Optional[InputData] = None
        self.last_expected: Optional[ComputeResult] = None
        self.last_result: Optional[CheckResult] = None

        self._build_ui()
        self._apply_lang()
        self._show_placeholder()
        if DND_AVAILABLE:
            self._setup_dnd()

    # ---- i18n helpers -------------------------------------------------------

    def t(self, key: str) -> str:
        return I18N[self.lang.get()][key]

    # ---- UI construction -----------------------------------------------------

    def _build_ui(self) -> None:
        top = ttk.Frame(self, padding=10)
        top.pack(fill=tk.X)

        self.label_input_file = ttk.Label(top)
        self.label_input_file.pack(side=tk.LEFT)
        self.file_entry = ttk.Entry(
            top, textvariable=self.selected_file, width=60, state="readonly"
        )
        self.file_entry.pack(side=tk.LEFT, padx=8)

        self.btn_browse = ttk.Button(top, command=self._browse_file)
        self.btn_browse.pack(side=tk.LEFT)
        self.btn_reload = ttk.Button(top, command=self._reload)
        self.btn_reload.pack(side=tk.LEFT, padx=(6, 0))
        self.btn_clear = ttk.Button(top, command=self._clear)
        self.btn_clear.pack(side=tk.LEFT, padx=(6, 0))
        self.btn_run = ttk.Button(top, command=self._run_check)
        self.btn_run.pack(side=tk.LEFT, padx=(6, 0))
        self.btn_export = ttk.Button(top, command=self._export_report)
        self.btn_export.pack(side=tk.LEFT, padx=(6, 0))

        self.lang_label = ttk.Label(top)
        self.lang_label.pack(side=tk.LEFT, padx=(14, 4))
        self.lang_combo = ttk.Combobox(
            top, values=LANGUAGES, textvariable=self.lang,
            state="readonly", width=4,
        )
        self.lang_combo.pack(side=tk.LEFT)
        self.lang_combo.bind("<<ComboboxSelected>>", lambda _e: self._apply_lang())

        self.label_dnd_hint: ttk.Label | None = None
        if not DND_AVAILABLE:
            self.label_dnd_hint = ttk.Label(top)
            self.label_dnd_hint.pack(side=tk.LEFT, padx=8)

        # Summary header — shows passed/failed badge or the "no data" hint.
        self.summary_var = tk.StringVar(value="")
        self.summary_label = ttk.Label(self, padding=(10, 0, 10, 6), anchor="w")
        self.summary_label.config(textvariable=self.summary_var)
        self.summary_label.pack(fill=tk.X)

        # Checklist Treeview.
        tree_wrap = ttk.Frame(self, padding=(10, 0, 10, 10))
        tree_wrap.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(
            tree_wrap,
            columns=_CHECKLIST_COLUMNS,
            show="headings",
            height=14,
        )
        self._tree_heading_keys = {
            "name": "reverse_col_name",
            "actual": "reverse_col_actual",
            "expected": "reverse_col_expected",
            "diff": "reverse_col_diff",
            "message": "reverse_col_message",
        }
        widths = {
            "icon": 32,
            "name": 220,
            "actual": 160,
            "expected": 160,
            "diff": 90,
            "message": 220,
        }
        for col in _CHECKLIST_COLUMNS:
            self.tree.heading(col, text=col)
            self.tree.column(
                col, width=widths[col], anchor="w", stretch=(col != "icon")
            )
        self.tree.tag_configure("passed", foreground="#1a7a1a")
        self.tree.tag_configure("failed", foreground="#a01010")
        vsb = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

    def _setup_dnd(self) -> None:
        assert DND_FILES is not None
        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<Drop>>", self._on_drop)
        self.file_entry.drop_target_register(DND_FILES)
        self.file_entry.dnd_bind("<<Drop>>", self._on_drop)

    def _apply_lang(self) -> None:
        self.lang.set(normalize_lang(self.lang.get()))
        self.title(self.t("reverse_title_main"))
        self.label_input_file.config(text=self.t("input_file"))
        self.btn_browse.config(text=self.t("reverse_load"))
        self.btn_reload.config(text=self.t("reverse_reload"))
        self.btn_clear.config(text=self.t("reverse_clear"))
        self.btn_run.config(text=self.t("reverse_run"))
        self.btn_export.config(text=self.t("reverse_export_report"))
        self.lang_label.config(text=self.t("lang"))
        if self.label_dnd_hint is not None:
            self.label_dnd_hint.config(text=self.t("dnd_hint"))
        for col, key in self._tree_heading_keys.items():
            self.tree.heading(col, text=self.t(key))
        # Re-translate the current summary, if any.
        if self.last_result is not None:
            self._refresh_summary(self.last_result)
        else:
            self.summary_var.set(self.t("reverse_no_data"))

    # ---- DnD / file loading -------------------------------------------------

    def _on_drop(self, event: tk.Event) -> None:  # type: ignore[override]
        path = extract_dropped_path(getattr(event, "data", ""))
        if not path:
            return
        p = Path(path)
        if p.suffix.lower() != ".json":
            messagebox.showerror(
                self.t("reverse_load_error"), self.t("reverse_drop_file")
            )
            return
        self.selected_file.set(str(p))
        self._run_from_path(p)

    def _browse_file(self) -> None:
        path = filedialog.askopenfilename(
            title=self.t("reverse_load"),
            filetypes=[("Self-check JSON", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        self.selected_file.set(path)
        self._run_from_path(Path(path))

    def _reload(self) -> None:
        raw = self.selected_file.get()
        if not raw:
            messagebox.showerror(self.t("reverse_load_error"), self.t("reverse_no_file"))
            return
        self._run_from_path(Path(raw))

    def _clear(self) -> None:
        self.selected_file.set("")
        self.last_payload = None
        self.last_expected = None
        self.last_result = None
        self._show_placeholder()

    def _run_from_path(self, path: Path) -> None:
        try:
            payload, expected = parse_self_check_file(path)
        except (ValueError, FileNotFoundError) as exc:
            messagebox.showerror(self.t("reverse_load_error"), str(exc))
            return
        self.last_payload = payload
        self.last_expected = expected
        self._run_check()

    # ---- core verification ---------------------------------------------------

    def _run_check(self) -> None:
        if self.last_payload is None or self.last_expected is None:
            messagebox.showerror(self.t("reverse_load_error"), self.t("reverse_no_file"))
            return
        try:
            actual = compute(self.last_payload)
            result = verify(actual, self.last_expected)
        except Exception as exc:  # noqa: BLE001 — surface everything to the user.
            messagebox.showerror(self.t("reverse_run_error"), str(exc))
            return
        self.last_result = result
        self._render_result(result)

    # ---- rendering -----------------------------------------------------------

    def _show_placeholder(self) -> None:
        self._clear_tree()
        self.summary_var.set(self.t("reverse_no_data"))

    def _clear_tree(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

    def _render_result(self, result: CheckResult) -> None:
        self._clear_tree()
        missing_label = self.t("missing_label")
        for entry in result.entries:
            tag = "passed" if entry.passed else "failed"
            icon = "✓" if entry.passed else "✗"
            self.tree.insert(
                "",
                "end",
                values=(
                    icon,
                    entry.name,
                    _format_cell(entry.actual, missing_label),
                    _format_cell(entry.expected, missing_label),
                    _format_diff(entry.diff, missing_label),
                    entry.message,
                ),
                tags=(tag,),
            )
        self._refresh_summary(result)

    def _refresh_summary(self, result: CheckResult) -> None:
        total = result.passed + result.failed
        if result.failed == 0:
            self.summary_var.set(
                self.t("reverse_summary_all_passed").format(total=total)
            )
        else:
            self.summary_var.set(
                self.t("reverse_summary_some_failed").format(
                    passed=result.passed, failed=result.failed, total=total
                )
            )

    # ---- export --------------------------------------------------------------

    def _export_report(self) -> None:
        if self.last_result is None:
            messagebox.showerror(
                self.t("reverse_export_error"), self.t("reverse_no_file")
            )
            return
        try:
            path = filedialog.asksaveasfilename(
                title=self.t("reverse_export_title"),
                defaultextension=".txt",
                filetypes=[("Text", "*.txt"), ("All files", "*.*")],
            )
            if not path:
                return
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(f"# {self.t('reverse_title_main')}\n")
                if self.selected_file.get():
                    fh.write(f"# source: {self.selected_file.get()}\n")
                fh.write("#\n")
                print_checklist(self.last_result, file=fh)
            messagebox.showinfo(
                self.t("reverse_export_title"), self.t("reverse_export_done")
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(
                self.t("reverse_export_error"), str(exc)
            )


def main() -> None:
    ReverseApp().mainloop()


if __name__ == "__main__":
    main()