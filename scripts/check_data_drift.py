"""Dataset drift checker using baseline summary + KS tests.

Modes:
- baseline: create baseline profile from a reference dataset
- check: compare current dataset against baseline profile

Usage:
  python scripts/check_data_drift.py baseline --input data/sample.csv --output data/processed/baseline_profile.json
  python scripts/check_data_drift.py check --input data/sample.csv --baseline data/processed/baseline_profile.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from scipy.stats import ks_2samp


def _numeric_columns(df: pd.DataFrame) -> list[str]:
    return [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col])]


def build_baseline_profile(df: pd.DataFrame) -> dict:
    profile = {
        "row_count": int(len(df)),
        "columns": {},
    }
    for col in _numeric_columns(df):
        series = df[col].dropna().astype(float)
        profile["columns"][col] = {
            "mean": float(series.mean()) if not series.empty else None,
            "std": float(series.std(ddof=0)) if not series.empty else None,
            "values_sample": series.head(5000).tolist(),
        }
    return profile


def compare_against_baseline(df: pd.DataFrame, baseline: dict, alpha: float = 0.05) -> dict:
    results = {
        "drift_detected": False,
        "columns": {},
    }

    for col, info in baseline.get("columns", {}).items():
        if col not in df.columns:
            results["columns"][col] = {
                "status": "missing",
                "drift": True,
            }
            results["drift_detected"] = True
            continue

        current = df[col].dropna().astype(float)
        baseline_values = pd.Series(info.get("values_sample", []), dtype="float64")

        if current.empty or baseline_values.empty:
            results["columns"][col] = {
                "status": "insufficient_data",
                "drift": False,
            }
            continue

        ks_stat, p_value = ks_2samp(
            baseline_values,
            current.head(5000),
            method="asymp",
        )
        drift = bool(p_value < alpha)

        results["columns"][col] = {
            "status": "ok",
            "drift": drift,
            "p_value": float(p_value),
            "ks_stat": float(ks_stat),
            "current_mean": float(current.mean()),
            "baseline_mean": info.get("mean"),
        }
        if drift:
            results["drift_detected"] = True

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Data drift check utility")
    sub = parser.add_subparsers(dest="command", required=True)

    baseline_parser = sub.add_parser("baseline")
    baseline_parser.add_argument("--input", required=True)
    baseline_parser.add_argument("--output", required=True)

    check_parser = sub.add_parser("check")
    check_parser.add_argument("--input", required=True)
    check_parser.add_argument("--baseline", required=True)
    check_parser.add_argument("--alpha", type=float, default=0.05)

    args = parser.parse_args()

    if args.command == "baseline":
        df = pd.read_csv(args.input)
        profile = build_baseline_profile(df)
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        print(f"PASS: baseline profile saved -> {out_path}")
        return 0

    df = pd.read_csv(args.input)
    baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    result = compare_against_baseline(df, baseline, alpha=args.alpha)
    print(json.dumps(result, indent=2))
    if result.get("drift_detected"):
        print("WARN: drift detected")
        return 2
    print("PASS: no drift detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
