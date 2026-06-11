import sys
import os
import argparse

from src.pipeline.pipeline import run_pipeline
from src.utils.config import (
    DEFAULT_REPORT_DIR,
    DEFAULT_REPORT_PATH,
    DEFAULT_SAVE_CLEAN,
    DEFAULT_SKIP_CLEAN,
    resolve_project_path,
)
# =============================================================================
# src/cli/cli.py — CLI Controller
# Rule: Only this file prints to the user.
#       Pipeline returns data. CLI displays it.
# =============================================================================


# ── Output Helpers ────────────────────────────────────────────────────────────

def _print_header():
    print("\n" + "=" * 54)
    print("   DataForge")
    print("   Transform Raw Data into Trusted Data")
    print("=" * 54)


def _print_step(num, label):
    print(f"\n  [{num}/5] {label}...")


def _print_meta(meta):
    print(f"         Rows      : {meta['original_rows']}")
    print(f"         Columns   : {meta['original_cols']}")
    print(f"         Encoding  : {meta['encoding']}")
    print(f"         Delimiter : {repr(meta['delimiter'])}")


def _print_profile(profile):
    print(f"         Profiled  : {len(profile)} columns")

    for col, info in profile.items():
        null_indicator = ""
        if info["null_pct"] > 40:
            null_indicator = f"  !! {info['null_pct']:.1f}% missing"
        elif info["null_pct"] > 5:
            null_indicator = f"  !  {info['null_pct']:.1f}% missing"

        print(
            f"         └ {col:<22} "
            f"[{info['inferred_type']:<12}] "
            f"unique: {info['unique']}"
            f"{null_indicator}"
        )


def _print_issues(issues, summary):
    if summary is None:
        summary = {"critical":0,"warning":0,"info":0,"total":0}

    if issues is None:
        issues = []

    print(f"         Total     : {summary['total']}")
    print(f"         Critical  : {summary['critical']}")
    print(f"         Warnings  : {summary['warning']}")
    print(f"         Info      : {summary['info']}")

    if issues:
        print()
        tags = {
            "critical": "[CRIT]",
            "warning" : "[WARN]",
            "info"    : "[INFO]"
        }
        for issue in issues:
            tag = tags.get(issue["severity"], "[    ]")
            print(f"         {tag} {issue['column']} — {issue['message']}")


def _print_clean_log(clean_log):
    if clean_log:
        for action in clean_log:
            print(f"         - {action}")
    else:
        print("         No cleaning actions taken.")


def _print_summary(result, output_path, save_clean):
    shape = result["clean_df"].shape if result["clean_df"] is not None else ("?", "?")

    print("\n" + "=" * 54)
    print("   Done")
    print("=" * 54)
    report_loc = result.get("report_path") or resolve_project_path(output_path)
    print(f"   Report     : {report_loc}")

    if save_clean:
        print(f"   Cleaned    : {save_clean}")

    print(f"   Final shape: {shape[0]} rows × {shape[1]} cols")
    print("=" * 54 + "\n")


def _print_error(message):
    print(f"\n  [ERROR] {message}\n", file=sys.stderr)


# ── Argument Parser ───────────────────────────────────────────────────────────

def build_parser():

    parser = argparse.ArgumentParser(
        prog="maincsv",
        description="CSV Quality Analyzer — profile, validate, clean, and report.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python maincsv.py data/sample.csv\n"
            "  python maincsv.py data/sample.csv --output outputs/report.html\n"
            "  python maincsv.py data/sample.csv --save-clean outputs/clean.csv\n"
            "  python maincsv.py data/sample.csv --skip-clean\n"
            "  python maincsv.py data/sample.csv --quiet\n"
            "  python maincsv.py data/sample.csv --verbose\n"
        )
    )

    parser.add_argument(
        "filepath",
        help="Path to the input CSV file"
    )

    parser.add_argument(
        "--output",
        default=DEFAULT_REPORT_PATH,
        metavar="PATH",
        help=(
            "Output path for HTML report\n"
            f"(default: timestamped report in {DEFAULT_REPORT_DIR}/)"
        )
    )

    parser.add_argument(
        "--save-clean",
        default=DEFAULT_SAVE_CLEAN,
        metavar="PATH",
        dest="save_clean",
        help="Save cleaned CSV to this path"
    )

    parser.add_argument(
        "--skip-clean",
        action="store_true",
        default=DEFAULT_SKIP_CLEAN,
        dest="skip_clean",
        help="Skip the cleaning stage entirely"
    )

    # Mutually exclusive: --quiet vs --verbose
    verbosity = parser.add_mutually_exclusive_group()

    verbosity.add_argument(
        "--quiet",
        action="store_true",
        default=False,
        help="Only show final summary — suppress step output"
    )

    verbosity.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Show full column profile in terminal"
    )

    return parser


# ── Validators ────────────────────────────────────────────────────────────────

def validate_args(args):
    """
    Validate CLI arguments before hitting the pipeline.
    Raises SystemExit with a clean message on failure.
    """

    if not os.path.exists(args.filepath):
        _print_error(f"File not found: {args.filepath}")
        sys.exit(1)

    if not args.filepath.lower().endswith(".csv"):
        _print_error(f"Expected a .csv file, got: {args.filepath}")
        sys.exit(1)

    if args.save_clean:
        save_resolved = resolve_project_path(args.save_clean)
        save_dir = os.path.dirname(save_resolved)
        if save_dir:
            os.makedirs(save_dir, exist_ok=True)

    if args.output:
        output_resolved = resolve_project_path(args.output)
        output_dir = os.path.dirname(output_resolved)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():

    parser = build_parser()
    args   = parser.parse_args()

    # ── Validate before pipeline ──────────────────────────────────────────────
    validate_args(args)

    # ── Header ────────────────────────────────────────────────────────────────
    if not args.quiet:
        _print_header()
        print(f"\n   File: {args.filepath}")

    # ── Run pipeline ──────────────────────────────────────────────────────────
    result = run_pipeline(
        filepath    = args.filepath,
        output_path = args.output,
        skip_clean  = args.skip_clean,
        save_clean  = args.save_clean
    )

    # ── Pipeline failure ──────────────────────────────────────────────────────
    if not result["success"]:
        _print_error(result["error"])
        sys.exit(1)

    # ── Print results ─────────────────────────────────────────────────────────
    if not args.quiet:

        _print_step(1, "Loading")
        _print_meta(result["meta"])

        _print_step(2, "Profiling")
        if args.verbose:
            _print_profile(result["profile"])
        else:
            print(f"         Profiled  : {len(result['profile'])} columns")
            print("         (use --verbose to see full column breakdown)")

        _print_step(3, "Quality Checks")
        _print_issues(result["issues"], result["quality_summary"])

        _print_step(4, "Cleaning")
        _print_clean_log(result["clean_log"])

        _print_step(5, "Report")
        print(f"         Saved to  : {result['report_path']}")

    _print_summary(result, args.output, args.save_clean)


if __name__ == "__main__":
    main()
