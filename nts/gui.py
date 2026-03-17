from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Dict, List, Tuple
from urllib.parse import unquote

from .core import Experiment, compute, read_input_json

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except Exception:
    DND_AVAILABLE = False
    DND_FILES = None
    TkinterDnD = None


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
        "drop_json": "Please drop a .json file.",
        "empty_value": "Empty value in row {row}, {key}.",
        "crit_required": "G_crit, t_crit and F_crit must be filled.",
        "headers": {
            "no": "No",
            "delta1": "delta1",
            "delta2": "delta2",
            "x1": "x1",
            "x2": "x2",
            "x3": "x3",
            "y1": "y1",
            "y2": "y2",
            "y3": "y3",
        },
        "out_headers": {
            "y_avg": "y_avg",
            "delta1": "delta1",
            "delta2": "delta2",
            "y_pred": "y_pred",
            "y_avg_minus_y": "y_avg - y",
            "y_avg_minus_y_sq": "(y_avg - y)^2",
        },
        "t0": "t0",
        "t1": "t1",
        "t2": "t2",
        "lang": "Lang:",
        "result_not_rejected": "Hypothesis not rejected",
        "result_rejected": "Hypothesis rejected",
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
        "drop_json": "Перетащите файл .json.",
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
        "out_headers": {
            "y_avg": "y_ср",
            "delta1": "δ1",
            "delta2": "δ2",
            "y_pred": "y",
            "y_avg_minus_y": "y_ср - y",
            "y_avg_minus_y_sq": "(y_ср - y)^2",
        },
        "t0": "t0",
        "t1": "t1",
        "t2": "t2",
        "lang": "Язык:",
        "result_not_rejected": "Гипотеза не отвергается",
        "result_rejected": "Гипотеза отвергается",
    },
}


def normalize_number(value: str) -> str:
    return value.strip().replace(",", ".")


class App((TkinterDnD.Tk if DND_AVAILABLE else tk.Tk)):  # type: ignore[misc]
    def __init__(self) -> None:
        super().__init__()
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

    def t_out_header(self, key: str) -> str:
        return I18N[self.lang.get()]["out_headers"][key]

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
        if p.suffix.lower() != ".json":
            messagebox.showerror(self.t("load_error"), self.t("drop_json"))
            return
        self.selected_file.set(str(p))
        self._load_from_path(p)

    def _browse_file(self) -> None:
        path = filedialog.askopenfilename(
            title=self.t("input_file"),
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
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
            experiments, g_crit, t_crit, f_crit = read_input_json(path)
        except Exception as exc:
            messagebox.showerror(self.t("load_error"), str(exc))
            return

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
            self.after(0, lambda: fill_next(i + 1))

        fill_next(0)

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

    def _calculate(self) -> None:
        try:
            experiments = self._read_experiments()
            g_crit, t_crit, f_crit = self._read_crit()
            result = compute(experiments, g_crit, t_crit, f_crit)
        except Exception as exc:
            messagebox.showerror(self.t("calc_error"), str(exc))
            return

        self._show_output(result)

    def _show_output(self, result: Dict[str, object]) -> None:
        win = tk.Toplevel(self)
        win.title(self.t("title_output"))
        win.geometry("920x460")

        top = ttk.Frame(win, padding=10)
        top.pack(fill=tk.X)
        ttk.Label(top, text=result["equation"]).pack(anchor="w")

        mid = ttk.Frame(win, padding=(10, 0, 10, 10))
        mid.pack(fill=tk.X)
        t = result["t_tests"]
        ttk.Label(mid, text=f"{self.t('t0')}={t['t0']:.4f} ({t['sign_b0']})").grid(row=0, column=0, padx=6, pady=2)
        ttk.Label(mid, text=f"{self.t('t1')}={t['t1']:.4f} ({t['sign_b1']})").grid(row=0, column=1, padx=6, pady=2)
        ttk.Label(mid, text=f"{self.t('t2')}={t['t2']:.4f} ({t['sign_b2']})").grid(row=0, column=2, padx=6, pady=2)

        table = ttk.Frame(win)
        table.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tree = ttk.Treeview(
            table,
            columns=[col[0] for col in OUTPUT_COLUMNS],
            show="headings",
        )
        for key, _label_key, width in OUTPUT_COLUMNS:
            tree.heading(key, text=self.t_out_header(_label_key))
            tree.column(key, width=width, minwidth=width, anchor="center", stretch=True)

        vsb = ttk.Scrollbar(table, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(table, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)

        for row in result["output_rows"]:
            tree.insert(
                "",
                "end",
                values=(
                    f"{row['y_avg']:.6g}",
                    f"{row['delta1']:.6g}",
                    f"{row['delta2']:.6g}",
                    f"{row['y_pred']:.6g}",
                    f"{row['y_avg_minus_y']:.6g}",
                    f"{row['y_avg_minus_y_sq']:.6g}",
                ),
            )

        bottom = ttk.Frame(win, padding=(10, 0, 10, 10))
        bottom.pack(fill=tk.X)
        ttk.Label(bottom, text=f"{self.t('f_avg')}={result['f_avg']:.6g}").pack(side=tk.LEFT, padx=6)
        ttk.Label(bottom, text=f"{self.t('f_value')}={result['f_value']:.6g}").pack(side=tk.LEFT, padx=6)

        res_code = result.get("f_result_code")
        if res_code == "not_rejected":
            res_text = self.t("result_not_rejected")
        elif res_code == "rejected":
            res_text = self.t("result_rejected")
        else:
            res_text = str(result.get("f_result", ""))
        ttk.Label(bottom, text=res_text).pack(side=tk.LEFT, padx=6)


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
