from __future__ import annotations

import json
import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List
from urllib.parse import unquote

from .core import EXPECTED_EXPERIMENTS, Experiment, InputData, compute, fmt3, read_input_file
from .i18n import DEFAULT_LANGUAGE, I18N, LANGUAGES, normalize_lang

try:
    import openpyxl
except Exception:
    openpyxl = None

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    import tkinterdnd2 as _tkd2_module
    import platform as _platform

    def _patched_require(tkroot):
        """Find tkdnd data dir in any of tkinterdnd2.__path__ entries.

        Nuitka onefile puts the python code at one extraction path and the data
        files at another (sometimes a virtual ``\\not_existing`` path that Nuitka
        rewrites for data-file lookups). Searching all ``__path__`` entries is the
        only portable way to locate the data.
        """
        system = _platform.system()
        if system == "Windows":
            machine = os.environ.get("PROCESSOR_ARCHITECTURE", _platform.machine())
        else:
            machine = _platform.machine()
        if system == "Darwin" and machine == "arm64":
            plat = "osx-arm64"
        elif system == "Darwin" and machine == "x86_64":
            plat = "osx-x64"
        elif system == "Linux" and machine == "aarch64":
            plat = "linux-arm64"
        elif system == "Linux" and machine == "x86_64":
            plat = "linux-x64"
        elif system == "Windows" and machine == "ARM64":
            plat = "win-arm64"
        elif system == "Windows" and machine == "AMD64":
            plat = "win-x64"
        elif system == "Windows" and machine == "x86":
            plat = "win-x86"
        else:
            raise RuntimeError(f"Platform not supported: {system}/{machine}")

        tcl_major = int(tkroot.tk.call("info", "tclversion").split(".")[0])
        suffix = "-tcl9" if tcl_major >= 9 else ""
        subdir = f"tkdnd/{plat}{suffix}"

        last_err: Exception | None = None
        for base in _tkd2_module.__path__:
            candidate = os.path.join(base, subdir)
            if os.path.isdir(candidate):
                tkroot.tk.call("lappend", "auto_path", candidate)
                try:
                    TkinterDnD.TkdndVersion = tkroot.tk.call("package", "require", "tkdnd")
                    return TkinterDnD.TkdndVersion
                except Exception as exc:
                    last_err = exc
        raise RuntimeError(
            f"tkdnd data not found in any __path__ entry (last error: {last_err})"
        )

    TkinterDnD._require = _patched_require
    DND_AVAILABLE = True
except Exception:
    DND_AVAILABLE = False
    DND_FILES = None
    TkinterDnD = None


INPUT_COLUMNS: List[tuple[str, str]] = [
    ("idx", "no"),
    ("delta1", "delta1"),
    ("delta2", "delta2"),
    ("x1", "x1"),
    ("x2", "x2"),
    ("x3", "x3"),
    ("y1", "y1"),
    ("y2", "y2"),
    ("y3", "y3"),
]

T_BLOCK: tuple[tuple[str, str, str], ...] = (
    ("t_0", "t0", "b0"),
    ("t_1", "t1", "b1"),
    ("t_2", "t2", "b2"),
)


def normalize_number(value: str) -> str:
    return value.strip().replace(",", ".")


def extract_dropped_path(data: str) -> str:
    raw = data.strip()
    if raw.startswith("{"):
        end = raw.find("}")
        if end != -1:
            raw = raw[1:end]
    elif " " in raw:
        raw = raw.split(" ", 1)[0]
    raw = unquote(raw)
    if raw.startswith("file://"):
        raw = raw[7:]
    return raw.lstrip("/")


def _experiment_from_form(entries: Dict[tuple[int, str], tk.Entry], row: int, t_msg: str) -> Experiment:
    def get(key: str) -> float:
        raw = normalize_number(entries[(row, key)].get())
        if raw == "":
            raise ValueError(t_msg.format(row=row + 1, key=key))
        return float(raw)

    return Experiment(
        idx=int(get("idx")),
        delta1=get("delta1"),
        delta2=get("delta2"),
        x1=get("x1"),
        x2=get("x2"),
        x3=get("x3"),
        y1=get("y1"),
        y2=get("y2"),
        y3=get("y3"),
    )


class App(TkinterDnD.Tk if DND_AVAILABLE else tk.Tk):  # type: ignore[misc]
    def __init__(self) -> None:
        super().__init__()
        self.geometry("980x520")
        self.lang = tk.StringVar(value=DEFAULT_LANGUAGE)
        self.selected_file = tk.StringVar(value="")
        self.last_input: InputData | None = None

        self.entries: Dict[tuple[int, str], tk.Entry] = {}
        self.g_crit_var = tk.StringVar()
        self.t_crit_var = tk.StringVar()
        self.f_crit_var = tk.StringVar()

        self.header_labels: List[ttk.Label] = []

        self._build_ui()
        self._apply_lang()
        self._clear_inputs()
        if DND_AVAILABLE:
            self._setup_dnd()

    def t(self, key: str) -> str:
        return I18N[self.lang.get()][key]

    def t_header(self, key: str) -> str:
        return I18N[self.lang.get()]["headers"][key]

    def _build_ui(self) -> None:
        top = ttk.Frame(self, padding=10)
        top.pack(fill=tk.X)

        self.label_input_file = ttk.Label(top)
        self.label_input_file.pack(side=tk.LEFT)
        self.file_entry = ttk.Entry(top, textvariable=self.selected_file, width=60, state="readonly")
        self.file_entry.pack(side=tk.LEFT, padx=8)
        self.btn_browse = ttk.Button(top, command=self._browse_file)
        self.btn_browse.pack(side=tk.LEFT)
        self.btn_clear = ttk.Button(top, command=self._clear_inputs)
        self.btn_clear.pack(side=tk.LEFT, padx=(6, 0))

        self.lang_label = ttk.Label(top)
        self.lang_label.pack(side=tk.LEFT, padx=(14, 4))
        self.lang_combo = ttk.Combobox(top, values=LANGUAGES, textvariable=self.lang, state="readonly", width=4)
        self.lang_combo.pack(side=tk.LEFT)
        self.lang_combo.bind("<<ComboboxSelected>>", lambda _e: self._apply_lang())

        self.label_dnd_hint: ttk.Label | None = None
        if not DND_AVAILABLE:
            self.label_dnd_hint = ttk.Label(top)
            self.label_dnd_hint.pack(side=tk.LEFT, padx=8)

        grid = ttk.Frame(self, padding=(10, 0, 10, 10))
        grid.pack(fill=tk.BOTH, expand=True)
        for col_idx, (_, key) in enumerate(INPUT_COLUMNS):
            lbl = ttk.Label(grid)
            lbl.grid(row=0, column=col_idx, padx=6, pady=6)
            self.header_labels.append(lbl)
            grid.columnconfigure(col_idx, weight=1)

        for row_idx in range(EXPECTED_EXPERIMENTS):
            for col_idx, (key, _label_key) in enumerate(INPUT_COLUMNS):
                ent = ttk.Entry(grid, width=10)
                ent.grid(row=row_idx + 1, column=col_idx, padx=6, pady=4, sticky="nsew")
                self.entries[(row_idx, key)] = ent

        footer = ttk.Frame(self, padding=(10, 0, 10, 10))
        footer.pack(fill=tk.X)

        self.label_g = ttk.Label(footer)
        self.label_g.grid(row=0, column=0, padx=6, pady=4, sticky="w")
        ttk.Entry(footer, textvariable=self.g_crit_var, width=10).grid(row=0, column=1, padx=6, pady=4)
        self.label_t = ttk.Label(footer)
        self.label_t.grid(row=0, column=2, padx=6, pady=4, sticky="w")
        ttk.Entry(footer, textvariable=self.t_crit_var, width=10).grid(row=0, column=3, padx=6, pady=4)
        self.label_f = ttk.Label(footer)
        self.label_f.grid(row=0, column=4, padx=6, pady=4, sticky="w")
        ttk.Entry(footer, textvariable=self.f_crit_var, width=10).grid(row=0, column=5, padx=6, pady=4)
        self.btn_calc = ttk.Button(footer, command=self._calculate)
        self.btn_calc.grid(row=0, column=6, padx=12, pady=4)

    def _setup_dnd(self) -> None:
        assert DND_FILES is not None
        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<Drop>>", self._on_drop)
        self.file_entry.drop_target_register(DND_FILES)
        self.file_entry.dnd_bind("<<Drop>>", self._on_drop)

    def _apply_lang(self) -> None:
        self.lang.set(normalize_lang(self.lang.get()))
        self.title(self.t("title_main"))
        self.label_input_file.config(text=self.t("input_file"))
        self.btn_browse.config(text=self.t("browse"))
        self.btn_clear.config(text=self.t("clear"))
        self.btn_calc.config(text=self.t("calculate"))
        self.label_g.config(text=self.t("g_crit"))
        self.label_t.config(text=self.t("t_crit"))
        self.label_f.config(text=self.t("f_crit"))
        self.lang_label.config(text=self.t("lang"))
        if self.label_dnd_hint is not None:
            self.label_dnd_hint.config(text=self.t("dnd_hint"))
        for idx, (_key, header_key) in enumerate(INPUT_COLUMNS):
            self.header_labels[idx].config(text=self.t_header(header_key))

    def _on_drop(self, event: tk.Event) -> None:  # type: ignore[override]
        path = extract_dropped_path(getattr(event, "data", ""))
        if not path:
            return
        p = Path(path)
        if p.suffix.lower() not in {".json", ".xlsx", ".xlsm"}:
            messagebox.showerror(self.t("load_error"), self.t("drop_file"))
            return
        self.selected_file.set(str(p))
        self._load_from_path(p)

    def _browse_file(self) -> None:
        path = filedialog.askopenfilename(
            title=self.t("input_file"),
            filetypes=[
                ("Input files", "*.json;*.xlsx;*.xlsm"),
                ("JSON", "*.json"),
                ("Excel", "*.xlsx;*.xlsm"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        self.selected_file.set(path)
        self._load_from_path(Path(path))

    def _clear_inputs(self) -> None:
        self.selected_file.set("")
        for (row_idx, key), ent in self.entries.items():
            ent.delete(0, tk.END)
            if key == "idx":
                ent.insert(0, str(row_idx + 1))
        self.g_crit_var.set("")
        self.t_crit_var.set("")
        self.f_crit_var.set("")

    def _load_from_path(self, path: Path) -> None:
        try:
            data = read_input_file(path)
        except Exception as exc:
            messagebox.showerror(self.t("load_error"), str(exc))
            return

        self.last_input = data
        experiments = data.experiments

        for (row_idx, key), ent in self.entries.items():
            ent.delete(0, tk.END)
            if key == "idx":
                ent.insert(0, str(row_idx + 1))
        self.update_idletasks()

        def fill_row(i: int) -> None:
            exp = experiments[i]
            for key, val in (
                ("idx", exp.idx), ("delta1", exp.delta1), ("delta2", exp.delta2),
                ("x1", exp.x1), ("x2", exp.x2), ("x3", exp.x3),
                ("y1", exp.y1), ("y2", exp.y2), ("y3", exp.y3),
            ):
                ent = self.entries[(i, key)]
                ent.delete(0, tk.END)
                ent.insert(0, str(val))

        def fill_next(i: int) -> None:
            if i >= min(EXPECTED_EXPERIMENTS, len(experiments)):
                self.g_crit_var.set(str(data.g_crit))
                self.t_crit_var.set(str(data.t_crit))
                self.f_crit_var.set(str(data.f_crit))
                return
            fill_row(i)
            self.update_idletasks()
            self.after(1, lambda: fill_next(i + 1))

        self.after(1, lambda: fill_next(0))

    def _read_experiments(self) -> List[Experiment]:
        return [
            _experiment_from_form(self.entries, i, self.t("empty_value"))
            for i in range(EXPECTED_EXPERIMENTS)
        ]

    def _read_crit(self) -> tuple[float, float, float]:
        g_raw = normalize_number(self.g_crit_var.get())
        t_raw = normalize_number(self.t_crit_var.get())
        f_raw = normalize_number(self.f_crit_var.get())
        if g_raw == "" or t_raw == "" or f_raw == "":
            raise ValueError(self.t("crit_required"))
        return float(g_raw), float(t_raw), float(f_raw)

    def _calculate(self) -> None:
        try:
            experiments = self._read_experiments()
            g_crit, t_crit, f_crit = self._read_crit()
            data = InputData(experiments=experiments, g_crit=g_crit, t_crit=t_crit, f_crit=f_crit)
            result = compute(data)
        except Exception as exc:
            messagebox.showerror(self.t("calc_error"), str(exc))
            return

        self.last_input = data
        self._show_output(result)

    def _show_output(self, result: Dict[str, Any]) -> None:
        win = tk.Toplevel(self)
        win.title(self.t("title_output"))
        win.geometry("760x520")

        top = ttk.Frame(win, padding=10)
        top.pack(fill=tk.X)
        ttk.Label(top, text=str(result["equation"])).pack(anchor="w")

        mid = ttk.Frame(win, padding=(10, 0, 10, 6))
        mid.pack(fill=tk.X)
        t_tests = result["t_tests"]
        coeffs_v = result["coefficients_v"]
        for row, (tk_label_key, key, vk) in enumerate(T_BLOCK):
            ttk.Label(
                mid,
                text=f"{self.t(tk_label_key)} = {fmt3(t_tests[key])} ({t_tests[f'sign_{vk}']})",
            ).grid(row=row, column=0, sticky="w", padx=6, pady=2)
            ttk.Label(
                mid,
                text=f"{self.t(f'{vk}v')} = {fmt3(coeffs_v[vk])}",
            ).grid(row=row, column=1, sticky="w", padx=20, pady=2)

        grubbs = ttk.LabelFrame(win, text=self.t("grubbs_title"), padding=(10, 6, 10, 6))
        grubbs.pack(fill=tk.X, padx=10, pady=(4, 6))
        for i, g in enumerate(result["g_tests"]):
            cmp_sign = self.t("cmp_le") if g["g"] <= result["g_crit"] else self.t("cmp_gt")
            status = self.t("status_ok") if g["g"] <= result["g_crit"] else self.t("status_bad")
            line = self.t("grubbs_row").format(
                row=g["row"], g=fmt3(g["g"]), cmp=cmp_sign,
                gcrit=fmt3(result["g_crit"]), status=status,
            )
            ttk.Label(grubbs, text=line).grid(row=i, column=0, sticky="w", pady=1)

        fisher = ttk.LabelFrame(win, text=self.t("fisher_title"), padding=(10, 6, 10, 6))
        fisher.pack(fill=tk.X, padx=10, pady=(2, 10))
        cmp_sign = self.t("cmp_le") if result["f_value"] <= result["f_crit"] else self.t("cmp_gt")
        fisher_line = self.t("fisher_cmp").format(
            f=fmt3(result["f_value"]), cmp=cmp_sign, fcrit=fmt3(result["f_crit"]),
        )
        ttk.Label(fisher, text=fisher_line).grid(row=0, column=0, sticky="w", pady=1)

        res_code = result.get("f_result_code")
        if res_code == "not_rejected":
            res_text = self.t("result_not_rejected")
        elif res_code == "rejected":
            res_text = self.t("result_rejected")
        else:
            res_text = str(result.get("f_result", ""))
        ttk.Label(fisher, text=res_text).grid(row=1, column=0, sticky="w", pady=2)

        btns = ttk.Frame(win, padding=(10, 0, 10, 10))
        btns.pack(fill=tk.X)
        ttk.Button(btns, text=self.t("export_json"), command=lambda: self._export_json(result)).pack(side=tk.LEFT)
        ttk.Button(btns, text=self.t("export_xlsx"), command=lambda: self._export_xlsx(result)).pack(side=tk.LEFT, padx=8)

    def _build_export_payload(self, result: Dict[str, Any]) -> Dict[str, Any]:
        if self.last_input is None:
            raise ValueError("No input data to export.")
        data = self.last_input
        return {
            "input": {
                "experiments": [
                    {
                        "idx": exp.idx,
                        "delta1": exp.delta1,
                        "delta2": exp.delta2,
                        "x1": exp.x1,
                        "x2": exp.x2,
                        "x3": exp.x3,
                        "y1": exp.y1,
                        "y2": exp.y2,
                        "y3": exp.y3,
                    }
                    for exp in data.experiments
                ],
                "g_crit": data.g_crit,
                "t_crit": data.t_crit,
                "f_crit": data.f_crit,
            },
            "result": result,
        }

    def _export_json(self, result: Dict[str, Any]) -> None:
        try:
            payload = self._build_export_payload(result)
            path = filedialog.asksaveasfilename(
                title=self.t("export_title"),
                defaultextension=".json",
                filetypes=[("JSON", "*.json"), ("All files", "*.*")],
            )
            if not path:
                return
            Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            messagebox.showinfo(self.t("export_title"), self.t("export_done"))
        except Exception as exc:
            messagebox.showerror(self.t("export_error"), str(exc))

    def _export_xlsx(self, result: Dict[str, Any]) -> None:
        if openpyxl is None:
            messagebox.showerror(self.t("export_error"), "openpyxl not installed")
            return
        try:
            payload = self._build_export_payload(result)
            path = filedialog.asksaveasfilename(
                title=self.t("export_title"),
                defaultextension=".xlsx",
                filetypes=[("Excel", "*.xlsx"), ("All files", "*.*")],
            )
            if not path:
                return

            wb = openpyxl.Workbook()
            ws_input = wb.active
            ws_input.title = "input"
            ws_input.append(["idx", "delta1", "delta2", "x1", "x2", "x3", "y1", "y2", "y3"])
            for exp in payload["input"]["experiments"]:
                ws_input.append([
                    exp["idx"], exp["delta1"], exp["delta2"],
                    exp["x1"], exp["x2"], exp["x3"],
                    exp["y1"], exp["y2"], exp["y3"],
                ])

            ws_crit = wb.create_sheet("criteria")
            ws_crit.append(["g_crit", "t_crit", "f_crit"])
            ws_crit.append([
                payload["input"]["g_crit"],
                payload["input"]["t_crit"],
                payload["input"]["f_crit"],
            ])

            ws_res = wb.create_sheet("result")
            coeffs = result["coefficients"]
            coeffs_v = result["coefficients_v"]
            t_tests = result["t_tests"]
            ws_res.append(["b0", coeffs["b0"], "b1", coeffs["b1"], "b2", coeffs["b2"]])
            ws_res.append(["b0_v", coeffs_v["b0"], "b1_v", coeffs_v["b1"], "b2_v", coeffs_v["b2"]])
            ws_res.append(["t_0", t_tests["t0"], "t_1", t_tests["t1"], "t_2", t_tests["t2"]])
            ws_res.append(["F", result["f_value"], "F_crit", result["f_crit"]])
            ws_res.append(["G_crit", result["g_crit"], "t_crit", result["t_crit"]])

            ws_g = wb.create_sheet("grubbs")
            ws_g.append(["row", "G", "status"])
            for g in result["g_tests"]:
                ws_g.append([g["row"], g["g"], g["ok"]])

            wb.save(path)
            messagebox.showinfo(self.t("export_title"), self.t("export_done"))
        except Exception as exc:
            messagebox.showerror(self.t("export_error"), str(exc))


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
