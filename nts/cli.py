from __future__ import annotations

import argparse
import json
import sys
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


def _force_utf8_output() -> None:
    """Make stdout/stderr UTF-8 so ``δ`` and ``✓``/``✗`` survive a cp1252 console.

    Without this the CLI dies with ``UnicodeEncodeError`` on the default
    Windows console encoding (cp1252 cannot encode ``δ`` or the checklist
    glyphs) — the report and the self-check checklist both carry them.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


def main() -> None:
    _force_utf8_output()
    parser = argparse.ArgumentParser(description="Compute results without Excel dependencies.")
    parser.add_argument(
        "path",
        nargs="?",
        help="Input file path (positional alternative to --input).",
    )
    parser.add_argument(
        "--input",
        dest="input_path",
        default=None,
        help="Path to JSON or XLSX input file (or self-check file when --self-check).",
    )
    parser.add_argument(
        "--self-check",
        dest="self_check",
        action="store_true",
        help="Run self-check mode: input JSON must be {\"input\": {...}, \"expected\": {...}}.",
    )
    parser.add_argument("--json", dest="json_path", help="Write result JSON to this path.")
    args = parser.parse_args()

    input_path_str = args.input_path or args.path
    if input_path_str is None:
        parser.error("the following arguments are required: --input or a positional path")
    args.input_path = input_path_str

    if args.self_check:
        from .checker import parse_self_check_bundle, print_checklist, verify
        try:
            bundle = parse_self_check_bundle(Path(args.input_path))
        except (ValueError, FileNotFoundError) as e:
            print(f"error: {e}", file=sys.stderr)
            sys.exit(2)
        actual = compute(bundle.input_data)
        result = verify(actual, bundle.expected, mode=bundle.mode)
        print_checklist(result)
        sys.exit(0 if result.failed == 0 else 1)
        return

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
