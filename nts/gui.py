from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
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


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("NTS Calculator")
        self.geometry("980x520")

        self.inputs_dir = Path(__file__).resolve().parent.parent / "inputs"
        self.input_files = sorted(self.inputs_dir.glob("*.json"))
        if not self.input_files:
            raise FileNotFoundError("No input JSON files found in ./inputs")

        self.selected_file = tk.StringVar(value=str(self.input_files[0]))

        self.entries: Dict[Tuple[int, str], tk.Entry] = {}
        self.g_crit_var = tk.StringVar()
        self.t_crit_var = tk.StringVar()
        self.f_crit_var = tk.StringVar()

        self._build_ui()
        self._load_selected()

    def _build_ui(self) -> None:
        top = ttk.Frame(self, padding=10)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Input set:").pack(side=tk.LEFT)
        combo = ttk.Combobox(
            top,
            values=[str(p) for p in self.input_files],
            textvariable=self.selected_file,
            state="readonly",
            width=60,
        )
        combo.pack(side=tk.LEFT, padx=8)
        combo.bind("<<ComboboxSelected>>", lambda _e: self._load_selected())

        ttk.Button(top, text="Reload", command=self._load_selected).pack(side=tk.LEFT)

        grid = ttk.Frame(self, padding=(10, 0, 10, 10))
        grid.pack(fill=tk.BOTH, expand=True)

        for col_idx, (_, label) in enumerate(INPUT_COLUMNS):
            ttk.Label(grid, text=label).grid(row=0, column=col_idx, padx=6, pady=6)

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

    def _load_selected(self) -> None:
        try:
            experiments, g_crit, t_crit, f_crit = load_input_json(Path(self.selected_file.get()))
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
                return float(self.entries[(i, key)].get())

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

    def _calculate(self) -> None:
        try:
            experiments = self._read_experiments()
            g_crit = float(self.g_crit_var.get())
            t_crit = float(self.t_crit_var.get())
            f_crit = float(self.f_crit_var.get())
            result = compute(experiments, g_crit, t_crit, f_crit)
        except Exception as exc:
            messagebox.showerror("Calculation error", str(exc))
            return

        self._show_output(result)

    def _show_output(self, result: Dict[str, object]) -> None:
        win = tk.Toplevel(self)
        win.title("Output")
        win.geometry("820x420")

        top = ttk.Frame(win, padding=10)
        top.pack(fill=tk.X)
        ttk.Label(top, text=result["equation"]).pack(anchor="w")

        mid = ttk.Frame(win, padding=(10, 0, 10, 10))
        mid.pack(fill=tk.X)
        t = result["t_tests"]
        ttk.Label(mid, text=f"t0={t['t0']:.4f} ({t['sign_b0']})").grid(row=0, column=0, padx=6, pady=2)
        ttk.Label(mid, text=f"t1={t['t1']:.4f} ({t['sign_b1']})").grid(row=0, column=1, padx=6, pady=2)
        ttk.Label(mid, text=f"t2={t['t2']:.4f} ({t['sign_b2']})").grid(row=0, column=2, padx=6, pady=2)

        tree = ttk.Treeview(win, columns=("y_avg", "delta1", "delta2", "y_pred", "y_avg_minus_y", "sq"), show="headings")
        tree.heading("y_avg", text="y_avg")
        tree.heading("delta1", text="delta1")
        tree.heading("delta2", text="delta2")
        tree.heading("y_pred", text="y_pred")
        tree.heading("y_avg_minus_y", text="y_avg - y")
        tree.heading("sq", text="(y_avg - y)^2")
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

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
