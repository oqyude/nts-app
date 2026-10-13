from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import ComputeResult, InputData, compute, read_input_file


def print_report(result: ComputeResult) -> None:
    t = result["t_tests"]
    print(result["equation"])
    print("")
    print("t-tests:")
    for label, key, sign_key in (("t_0", "t0", "sign_b0"), ("t_1", "t1", "sign_b1"), ("t_2", "t2", "sign_b2")):
        print(f"  {label}: t={t[key]:.4f} sign={t[sign_key]}")
    print("")
    print("G-tests:")
    for row in result["g_tests"]:
        print(f"  row {row['row']}: G={row['g']:.4f} ({row['ok']})")
    print("")
    print("Output:")
    headers = ("y_avg", "delta1", "delta2", "y_pred", "y_avg-y", "(y_avg-y)^2")
    print("  " + " | ".join(headers))
    for r in result["output_rows"]:
        cells = (
            f"{r['y_avg']:.6g}", f"{r['delta1']:.6g}", f"{r['delta2']:.6g}",
            f"{r['y_pred']:.6g}", f"{r['y_avg_minus_y']:.6g}", f"{r['y_avg_minus_y_sq']:.6g}",
        )
        print("  " + " | ".join(cells))
    print("")
    print(f"F_avg={result['f_avg']:.6g}")
    print(f"F_value={result['f_value']:.6g}")
    print(result["f_result"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute results without Excel dependencies.")
    parser.add_argument("--input", dest="input_path", required=True, help="Path to JSON or XLSX input file.")
    parser.add_argument("--json", dest="json_path", help="Write result JSON to this path.")
    args = parser.parse_args()

    path = Path(args.input_path)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    data: InputData = read_input_file(path)
    result = compute(data)
    print_report(result)

    if args.json_path:
        json_path = Path(args.json_path)
        json_path.write_text(json.dumps(result, ensure_ascii=True, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
