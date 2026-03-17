import argparse
import json
from pathlib import Path
from typing import Any, Dict

from .core import compute, read_input_json


def print_report(result: Dict[str, Any]) -> None:
    print(result["equation"])
    print("")
    print("t-tests:")
    print(f"  b0: t={result['t_tests']['t0']:.4f} sign={result['t_tests']['sign_b0']}")
    print(f"  b1: t={result['t_tests']['t1']:.4f} sign={result['t_tests']['sign_b1']}")
    print(f"  b2: t={result['t_tests']['t2']:.4f} sign={result['t_tests']['sign_b2']}")
    print("")
    print("G-tests:")
    for row in result["g_tests"]:
        print(f"  row {row['row']}: G={row['g']:.4f} ({row['ok']})")
    print("")
    print("Output:")
    headers = ["y_avg", "delta1", "delta2", "y_pred", "y_avg-y", "(y_avg-y)^2"]
    print("  " + " | ".join(headers))
    for r in result["output_rows"]:
        print(
            "  "
            + " | ".join(
                [
                    f"{r['y_avg']:.6g}",
                    f"{r['delta1']:.6g}",
                    f"{r['delta2']:.6g}",
                    f"{r['y_pred']:.6g}",
                    f"{r['y_avg_minus_y']:.6g}",
                    f"{r['y_avg_minus_y_sq']:.6g}",
                ]
            )
        )
    print("")
    print(f"F_avg={result['f_avg']:.6g}")
    print(f"F_value={result['f_value']:.6g}")
    print(result["f_result"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute results without Excel dependencies.")
    parser.add_argument("--input", dest="input_path", required=True, help="Path to JSON input file.")
    parser.add_argument("--json", dest="json_path", help="Write result JSON to this path.")
    args = parser.parse_args()

    path = Path(args.input_path)
    if not path.exists():
        raise FileNotFoundError(f"Input JSON not found: {path}")
    experiments, g_crit, t_crit, f_crit = read_input_json(path)
    result = compute(experiments, g_crit, t_crit, f_crit)
    print_report(result)

    if args.json_path:
        json_path = Path(args.json_path)
        json_path.write_text(json.dumps(result, ensure_ascii=True, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
