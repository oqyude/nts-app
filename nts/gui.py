from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Dict, List, Tuple

from .core import Experiment, compute


INPUT_COLUMNS = [
    ("idx", "No"),
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
    ("y_avg_minus_y", "y_avg - y", 120),
    ("sq", "(y_avg - y)^2", 140),
]


def load_input_json(path: Path) -> Tuple[List[Experiment], float, float, float]:
    data = json.loads(path.read_text(encoding="utf-8"))
    experiments: List[Experiment] = []
    for item in data["experiments"]:
        experiments.append(
            Experiment(
                idx=int(item["idx"]),
                delta1=float(item["delta1"]),
                delta2=float(item["delta2"]),
                x1=float(item["x1"]),
                x2=float(item["x2"]),
                x3=float(item["x3"]),
                y1=float(item["y1"]),
                y2=float(item["y2"]),
                y3=float(item["y3"]),
            )
        )
    return experiments, float(data["g_crit"]), float(data["t_crit"]), float(data["f_crit"])


def normalize_number(value: str) -> str:
    return value.strip().replace(",", ".")


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("NTS Calculator")
        self.geometry("980x520")

        self.selected_file = tk.StringVar(value="")

        self.entries: Dict[Tuple[int, str], tk.Entry] = {}
        self.g_crit_var = tk.StringVar()
        self.t_crit_var = tk.StringVar()
        self.f_crit_var = tk.StringVar()

        self._build_ui()

    def _build_ui(self) -> None:
        top = ttk.Frame(self, padding=10)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Input file:").pack(side=tk.LEFT)
        ttk.Entry(top, textvariable=self.selected_file, width=70, state="readonly").pack(side=tk.LEFT, padx=8)
        ttk.Button(top, text="Browse", command=self._browse_file).pack(side=tk.LEFT)
        ttk.Button(top, text="Clear", command=self._clear_inputs).pack(side=tk.LEFT, padx=(6, 0))

        grid = ttk.Frame(self, padding=(10, 0, 10, 10))
        grid.pack(fill=tk.BOTH, expand=True)

        for col_idx, (_, label) in enumerate(INPUT_COLUMNS):
            ttk.Label(grid, text=label).grid(row=0, column=col_idx, padx=6, pady=6)
            grid.columnconfigure(col_idx, weight=1)

        for row_idx in range(4):
            for col_idx, (key, _label) in enumerate(INPUT_COLUMNS):
                ent = ttk.Entry(grid, width=10)
                ent.grid(row=row_idx + 1, column=col_idx, padx=6, pady=4, sticky="nsew")
                self.entries[(row_idx, key)] = ent

        footer = ttk.Frame(self, padding=(10, 0, 10, 10))
        footer.pack(fill=tk.X)

        ttk.Label(footer, text="G_crit").grid(row=0, column=0, padx=6, pady=4, sticky="w")
        ttk.Entry(footer, textvariable=self.g_crit_var, width=10).grid(row=0, column=1, padx=6, pady=4)
        ttk.Label(footer, text="t_crit").grid(row=0, column=2, padx=6, pady=4, sticky="w")
        ttk.Entry(footer, textvariable=self.t_crit_var, width=10).grid(row=0, column=3, padx=6, pady=4)
        ttk.Label(footer, text="F_crit").grid(row=0, column=4, padx=6, pady=4, sticky="w")
        ttk.Entry(footer, textvariable=self.f_crit_var, width=10).grid(row=0, column=5, padx=6, pady=4)

        ttk.Button(footer, text="Calculate", command=self._calculate).grid(row=0, column=6, padx=12, pady=4)

    def _browse_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Select input JSON",
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
            experiments, g_crit, t_crit, f_crit = load_input_json(path)
        except Exception as exc:
            messagebox.showerror("Load error", str(exc))
            return

        for i, exp in enumerate(experiments):
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

        self.g_crit_var.set(str(g_crit))
        self.t_crit_var.set(str(t_crit))
        self.f_crit_var.set(str(f_crit))

    def _read_experiments(self) -> List[Experiment]:
        experiments: List[Experiment] = []
        for i in range(4):
            def get(key: str) -> float:
                raw = normalize_number(self.entries[(i, key)].get())
                if raw == "":
                    raise ValueError(f"Empty value in row {i + 1}, {key}.")
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
            raise ValueError("G_crit, t_crit and F_crit must be filled.")
        return float(g_raw), float(t_raw), float(f_raw)

    def _calculate(self) -> None:
        try:
            experiments = self._read_experiments()
            g_crit, t_crit, f_crit = self._read_crit()
            result = compute(experiments, g_crit, t_crit, f_crit)
        except Exception as exc:
            messagebox.showerror("Calculation error", str(exc))
            return

        self._show_output(result)

    def _show_output(self, result: Dict[str, object]) -> None:
        win = tk.Toplevel(self)
        win.title("Output")
        win.geometry("920x460")

        top = ttk.Frame(win, padding=10)
        top.pack(fill=tk.X)
        ttk.Label(top, text=result["equation"]).pack(anchor="w")

        mid = ttk.Frame(win, padding=(10, 0, 10, 10))
        mid.pack(fill=tk.X)
        t = result["t_tests"]
        ttk.Label(mid, text=f"t0={t['t0']:.4f} ({t['sign_b0']})").grid(row=0, column=0, padx=6, pady=2)
        ttk.Label(mid, text=f"t1={t['t1']:.4f} ({t['sign_b1']})").grid(row=0, column=1, padx=6, pady=2)
        ttk.Label(mid, text=f"t2={t['t2']:.4f} ({t['sign_b2']})").grid(row=0, column=2, padx=6, pady=2)

        table = ttk.Frame(win)
        table.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tree = ttk.Treeview(
            table,
            columns=[col[0] for col in OUTPUT_COLUMNS],
            show="headings",
        )
        for key, label, width in OUTPUT_COLUMNS:
            tree.heading(key, text=label)
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
        ttk.Label(bottom, text=f"F_avg={result['f_avg']:.6g}").pack(side=tk.LEFT, padx=6)
        ttk.Label(bottom, text=f"F_value={result['f_value']:.6g}").pack(side=tk.LEFT, padx=6)
        ttk.Label(bottom, text=str(result["f_result"])).pack(side=tk.LEFT, padx=6)


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
