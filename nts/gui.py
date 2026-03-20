from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Dict, List, Tuple
from urllib.parse import unquote

from .core import Experiment, compute, read_input_file

try:
    import openpyxl
except Exception:
    openpyxl = None

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except Exception:
    DND_AVAILABLE = False
    DND_FILES = None
    TkinterDnD = None


# Конфигурация таблицы ввода.
INPUT_COLUMNS = [
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

OUTPUT_COLUMNS = [
    ("y_avg", "y_avg", 110),
    ("delta1", "delta1", 80),
    ("delta2", "delta2", 80),
    ("y_pred", "y_pred", 120),
    ("y_avg_minus_y", "y_avg_minus_y", 140),
    ("sq", "y_avg_minus_y_sq", 150),
]


# Тексты интерфейса (RU/EN).
I18N = {
    "EN": {
        "title_main": "NTS Calculator",
        "title_output": "Output",
        "input_file": "Input file:",
        "browse": "Browse",
        "clear": "Clear",
        "calculate": "Calculate",
        "g_crit": "G_crit",
        "t_crit": "t_crit",
        "f_crit": "F_crit",
        "f_avg": "F_avg",
        "f_value": "F_value",
        "dnd_hint": "(Install tkinterdnd2 for drag & drop)",
        "load_error": "Load error",
        "calc_error": "Calculation error",
        "drop_file": "Please drop a .json or .xlsx file.",
        "empty_value": "Empty value in row {row}, {key}.",
        "crit_required": "G_crit, t_crit and F_crit must be filled.",
        "headers": {
            "no": "No",
            "delta1": "δ1",
            "delta2": "δ2",
            "x1": "x1",
            "x2": "x2",
            "x3": "x3",
            "y1": "y1",
            "y2": "y2",
            "y3": "y3",
        },
        "t0": "b0 (t)",
        "t1": "b1 (t)",
        "t2": "b2 (t)",
        "b0v": "b0 (v)",
        "b1v": "b1 (v)",
        "b2v": "b2 (v)",
        "lang": "Lang:",
        "result_not_rejected": "Hypothesis not rejected",
        "result_rejected": "Hypothesis rejected",
        "export_json": "Export JSON",
        "export_xlsx": "Export XLSX",
        "export_done": "Saved successfully.",
        "export_error": "Export error",
        "export_title": "Export",
        "delta1_sym": "δ1",
        "delta2_sym": "δ2",
        "grubbs_title": "Grubbs criterion",
        "grubbs_row": "Experiment {row}: G={g} {cmp} G_crit={gcrit} ({status})",
        "fisher_title": "Fisher criterion",
        "fisher_cmp": "F={f} {cmp} F_crit={fcrit}",
        "cmp_le": "<=",
        "cmp_gt": ">",
        "status_ok": "OK",
        "status_bad": "not OK",
    },
    "RU": {
        "title_main": "Калькулятор НТС",
        "title_output": "Результат",
        "input_file": "Файл ввода:",
        "browse": "Обзор",
        "clear": "Очистить",
        "calculate": "Расчет",
        "g_crit": "G_крит",
        "t_crit": "t_крит",
        "f_crit": "F_крит",
        "f_avg": "F_ср",
        "f_value": "F_знач",
        "dnd_hint": "(Установите tkinterdnd2 для drag & drop)",
        "load_error": "Ошибка загрузки",
        "calc_error": "Ошибка расчета",
        "drop_file": "Перетащите файл .json или .xlsx.",
        "empty_value": "Пустое значение в строке {row}, {key}.",
        "crit_required": "Заполните G_крит, t_крит и F_крит.",
        "headers": {
            "no": "№",
            "delta1": "δ1",
            "delta2": "δ2",
            "x1": "x1",
            "x2": "x2",
            "x3": "x3",
            "y1": "y1",
            "y2": "y2",
            "y3": "y3",
        },
        "t0": "b0 (t)",
        "t1": "b1 (t)",
        "t2": "b2 (t)",
        "b0v": "b0 (в)",
        "b1v": "b1 (в)",
        "b2v": "b2 (в)",
        "lang": "Язык:",
        "result_not_rejected": "Гипотеза не отвергается",
        "result_rejected": "Гипотеза отвергается",
        "export_json": "Экспорт JSON",
        "export_xlsx": "Экспорт XLSX",
        "export_done": "Файл сохранен.",
        "export_error": "Ошибка экспорта",
        "export_title": "Экспорт",
        "delta1_sym": "δ1",
        "delta2_sym": "δ2",
        "grubbs_title": "Критерий Граббса",
        "grubbs_row": "Опыт {row}: G={g} {cmp} G_крит={gcrit} ({status})",
        "fisher_title": "Критерий Фишера",
        "fisher_cmp": "F={f} {cmp} F_крит={fcrit}",
        "cmp_le": "<=",
        "cmp_gt": ">",
        "status_ok": "OK",
        "status_bad": "не OK",
    },
}


# Нормализация чисел для ввода с запятой.
def normalize_number(value: str) -> str:
    return value.strip().replace(",", ".")


def fmt3(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


# Главное окно приложения.
class App((TkinterDnD.Tk if DND_AVAILABLE else tk.Tk)):  # type: ignore[misc]
    def __init__(self) -> None:
        super().__init__()
        self.geometry("980x520")
        self.lang = tk.StringVar(value="RU")

        self.selected_file = tk.StringVar(value="")

        self.entries: Dict[Tuple[int, str], tk.Entry] = {}
        self.g_crit_var = tk.StringVar()
        self.t_crit_var = tk.StringVar()
        self.f_crit_var = tk.StringVar()

        self.file_entry: ttk.Entry
        self.label_input_file: ttk.Label
        self.label_dnd_hint: ttk.Label | None = None
        self.label_g: ttk.Label
        self.label_t: ttk.Label
        self.label_f: ttk.Label
        self.btn_browse: ttk.Button
        self.btn_clear: ttk.Button
        self.btn_calc: ttk.Button
        self.lang_label: ttk.Label
        self.lang_combo: ttk.Combobox
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

    # Сборка интерфейса.
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

        self.lang_combo = ttk.Combobox(top, values=["RU", "EN"], textvariable=self.lang, state="readonly", width=4)
        self.lang_combo.pack(side=tk.LEFT)
        self.lang_combo.bind("<<ComboboxSelected>>", lambda _e: self._apply_lang())

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

        for row_idx in range(4):
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

    def _build_export_payload(self, result: Dict[str, object]) -> Dict[str, object]:
        if self.last_input is None:
            # Fallback: read from current form
            experiments = self._read_experiments()
            g_crit, t_crit, f_crit = self._read_crit()
        else:
            experiments, g_crit, t_crit, f_crit = self.last_input
        exp_list = []
        for exp in experiments:
            exp_list.append(
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
            )
        return {
            "input": {
                "experiments": exp_list,
                "g_crit": g_crit,
                "t_crit": t_crit,
                "f_crit": f_crit,
            },
            "result": result,
        }
    def _export_json(self, result: Dict[str, object]) -> None:
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

    def _export_xlsx(self, result: Dict[str, object]) -> None:
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
            ws_exp = wb.active
            ws_exp.title = "experiments"
            ws_exp.append(["idx", "delta1", "delta2", "x1", "x2", "x3", "y1", "y2", "y3"])
            for exp in payload["input"]["experiments"]:
                ws_exp.append([
                    exp["idx"],
                    exp["delta1"],
                    exp["delta2"],
                    exp["x1"],
                    exp["x2"],
                    exp["x3"],
                    exp["y1"],
                    exp["y2"],
                    exp["y3"],
                ])

            ws_crit = wb.create_sheet("criteria")
            ws_crit.append(["g_crit", "t_crit", "f_crit"])
            ws_crit.append([
                payload["input"]["g_crit"],
                payload["input"]["t_crit"],
                payload["input"]["f_crit"],
            ])

            ws_calc = wb.create_sheet("calculated")
            coeffs = result["coefficients"]
            coeffs_v = result["coefficients_v"]
            t_tests = result["t_tests"]
            ws_calc.append(["b0", coeffs["b0"], "b1", coeffs["b1"], "b2", coeffs["b2"]])
            ws_calc.append(["b0_v", coeffs_v["b0"], "b1_v", coeffs_v["b1"], "b2_v", coeffs_v["b2"]])
            ws_calc.append(["t0", t_tests["t0"], "t1", t_tests["t1"], "t2", t_tests["t2"]])
            ws_calc.append(["G_crit", result["g_crit"], "t_crit", result["t_crit"], "F_crit", result["f_crit"]])
            ws_calc.append(["F", result["f_value"], "F_avg", result["f_avg"], "F_result", result["f_result_code"]])
            ws_calc.append([])
            ws_calc.append(["Grubbs", "row", "G", "status"])
            for g in result["g_tests"]:
                ws_calc.append(["", g["row"], g["g"], g["ok"]])

            wb.save(path)
            messagebox.showinfo(self.t("export_title"), self.t("export_done"))
        except Exception as exc:
            messagebox.showerror(self.t("export_error"), str(exc))
    def _apply_lang(self) -> None:
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

        for (idx, (_key, header_key)) in enumerate(INPUT_COLUMNS):
            self.header_labels[idx].config(text=self.t_header(header_key))

    def _setup_dnd(self) -> None:
        assert DND_FILES is not None
        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<Drop>>", self._on_drop)
        self.file_entry.drop_target_register(DND_FILES)
        self.file_entry.dnd_bind("<<Drop>>", self._on_drop)

    def _extract_path(self, data: str) -> str:
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
        raw = raw.lstrip("/")
        return raw

    def _on_drop(self, event: tk.Event) -> None:  # type: ignore[override]
        path = self._extract_path(getattr(event, "data", ""))
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
            filetypes=[("Input files", "*.json;*.xlsx;*.xlsm"), ("JSON", "*.json"), ("Excel", "*.xlsx;*.xlsm"), ("All files", "*.*")],
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

    # Загрузка входного файла и заполнение таблицы.
    def _load_from_path(self, path: Path) -> None:
        try:
            experiments, g_crit, t_crit, f_crit = read_input_file(path)
            self.last_input = (experiments, g_crit, t_crit, f_crit)
        except Exception as exc:
            messagebox.showerror(self.t("load_error"), str(exc))
            return

        for (row_idx, key), ent in self.entries.items():
            ent.delete(0, tk.END)
            if key == "idx":
                ent.insert(0, str(row_idx + 1))
        self.update_idletasks()

        def fill_row(i: int) -> None:
            exp = experiments[i]
            values = {
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
            for key, val in values.items():
                ent = self.entries[(i, key)]
                ent.delete(0, tk.END)
                ent.insert(0, str(val))

        def fill_next(i: int) -> None:
            if i >= min(4, len(experiments)):
                self.g_crit_var.set(str(g_crit))
                self.t_crit_var.set(str(t_crit))
                self.f_crit_var.set(str(f_crit))
                return
            fill_row(i)
            self.update_idletasks()
            self.after(1, lambda: fill_next(i + 1))

        self.after(1, lambda: fill_next(0))

    def _read_experiments(self) -> List[Experiment]:
        experiments: List[Experiment] = []
        for i in range(4):
            def get(key: str) -> float:
                raw = normalize_number(self.entries[(i, key)].get())
                if raw == "":
                    raise ValueError(self.t("empty_value").format(row=i + 1, key=key))
                return float(raw)

            experiments.append(
                Experiment(
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
            )
        return experiments

    def _read_crit(self) -> Tuple[float, float, float]:
        g_raw = normalize_number(self.g_crit_var.get())
        t_raw = normalize_number(self.t_crit_var.get())
        f_raw = normalize_number(self.f_crit_var.get())
        if g_raw == "" or t_raw == "" or f_raw == "":
            raise ValueError(self.t("crit_required"))
        return float(g_raw), float(t_raw), float(f_raw)

    # Чтение данных из формы и расчет.
    def _calculate(self) -> None:
        try:
            experiments = self._read_experiments()
            g_crit, t_crit, f_crit = self._read_crit()
            self.last_input = (experiments, g_crit, t_crit, f_crit)
            result = compute(experiments, g_crit, t_crit, f_crit)
        except Exception as exc:
            messagebox.showerror(self.t("calc_error"), str(exc))
            return

        self._show_output(result)

    # Окно с результатами расчета.
    def _show_output(self, result: Dict[str, object]) -> None:
        win = tk.Toplevel(self)
        win.title(self.t("title_output"))
        win.geometry("760x520")

        coeffs = result["coefficients"]
        delta1 = self.t("delta1_sym")
        delta2 = self.t("delta2_sym")
        equation = _format_equation(coeffs["b0"], coeffs["b1"], coeffs["b2"], delta1, delta2)

        top = ttk.Frame(win, padding=10)
        top.pack(fill=tk.X)
        ttk.Label(top, text=equation).pack(anchor="w")

        mid = ttk.Frame(win, padding=(10, 0, 10, 6))
        mid.pack(fill=tk.X)
        t = result["t_tests"]
        b_v = result["coefficients_v"]

        ttk.Label(mid, text=self.t("t0") + f" = {fmt3(t['t0'])} ({t['sign_b0']})").grid(row=0, column=0, sticky="w", padx=6, pady=2)
        ttk.Label(mid, text=self.t("b0v") + f" = {fmt3(b_v['b0'])}").grid(row=0, column=1, sticky="w", padx=20, pady=2)

        ttk.Label(mid, text=self.t("t1") + f" = {fmt3(t['t1'])} ({t['sign_b1']})").grid(row=1, column=0, sticky="w", padx=6, pady=2)
        ttk.Label(mid, text=self.t("b1v") + f" = {fmt3(b_v['b1'])}").grid(row=1, column=1, sticky="w", padx=20, pady=2)

        ttk.Label(mid, text=self.t("t2") + f" = {fmt3(t['t2'])} ({t['sign_b2']})").grid(row=2, column=0, sticky="w", padx=6, pady=2)
        ttk.Label(mid, text=self.t("b2v") + f" = {fmt3(b_v['b2'])}").grid(row=2, column=1, sticky="w", padx=20, pady=2)

        grubbs = ttk.LabelFrame(win, text=self.t("grubbs_title"), padding=(10, 6, 10, 6))
        grubbs.pack(fill=tk.X, padx=10, pady=(4, 6))
        for i, g in enumerate(result["g_tests"]):
            cmp_sign = self.t("cmp_le") if g["g"] <= result["g_crit"] else self.t("cmp_gt")
            status = self.t("status_ok") if g["g"] <= result["g_crit"] else self.t("status_bad")
            line = self.t("grubbs_row").format(
                row=g["row"],
                g=fmt3(g["g"]),
                cmp=cmp_sign,
                gcrit=fmt3(result["g_crit"]),
                status=status,
            )
            ttk.Label(grubbs, text=line).grid(row=i, column=0, sticky="w", pady=1)

        fisher = ttk.LabelFrame(win, text=self.t("fisher_title"), padding=(10, 6, 10, 6))
        fisher.pack(fill=tk.X, padx=10, pady=(2, 10))
        cmp_sign = self.t("cmp_le") if result["f_value"] <= result["f_crit"] else self.t("cmp_gt")
        fisher_line = self.t("fisher_cmp").format(
            f=fmt3(result["f_value"]),
            cmp=cmp_sign,
            fcrit=fmt3(result["f_crit"]),
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

    def _build_export_payload(self, result: Dict[str, object]) -> Dict[str, object]:
        if self.last_input is None:
            raise ValueError("No input data to export.")
        experiments, g_crit, t_crit, f_crit = self.last_input
        exp_list = []
        for exp in experiments:
            exp_list.append(
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
            )
        return {
            "input": {
                "experiments": exp_list,
                "g_crit": g_crit,
                "t_crit": t_crit,
                "f_crit": f_crit,
            },
            "result": result,
        }

    def _export_json(self, result: Dict[str, object]) -> None:
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

    def _export_xlsx(self, result: Dict[str, object]) -> None:
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
                    exp["idx"],
                    exp["delta1"],
                    exp["delta2"],
                    exp["x1"],
                    exp["x2"],
                    exp["x3"],
                    exp["y1"],
                    exp["y2"],
                    exp["y3"],
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
            ws_res.append(["t0", t_tests["t0"], "t1", t_tests["t1"], "t2", t_tests["t2"]])
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

    def _apply_lang(self) -> None:
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

        for (idx, (_key, header_key)) in enumerate(INPUT_COLUMNS):
            self.header_labels[idx].config(text=self.t_header(header_key))


def _format_equation(b0: float, b1: float, b2: float, d1: str, d2: str) -> str:
    def term(value: float, name: str) -> str:
        sign = "+" if value >= 0 else "-"
        return f" {sign} {fmt3(abs(value))}*{name}"

    return f"Y = {fmt3(b0)}{term(b1, d1)}{term(b2, d2)}"


if __name__ == "__main__":
    app = App()
    app.mainloop()



def main() -> None:
    app = App()
    app.mainloop()













