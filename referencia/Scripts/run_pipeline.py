from __future__ import annotations

import argparse
import importlib.util
import sys
from datetime import datetime
from pathlib import Path

try:
    from .bronze_ingest import bronze_backfill_all, bronze_monthly_incremental
    from .build_gold_report_compatible import ALL_GOLD_PATH, SC_GOLD_PATH, build_gold
    from .paths import DADOS, ROOT
except ImportError:
    from bronze_ingest import bronze_backfill_all, bronze_monthly_incremental
    from build_gold_report_compatible import ALL_GOLD_PATH, SC_GOLD_PATH, build_gold
    from paths import DADOS, ROOT

DEFAULT_TEMPLATE_PATH = DADOS / "reports" / "Template - Comex Imprensa.xlsx"
DEFAULT_REPORT_PATH = DADOS / "reports" / "comex_report_sc.xlsx"
REPORT_REPO_SRC = ROOT.parent / "pipeline-relatorio-comex" / "src"
LOCAL_REPORT_SRC = ROOT / "pipeline-src"


def ensure_report_repo_on_path() -> None:
    report_source = LOCAL_REPORT_SRC if LOCAL_REPORT_SRC.exists() else REPORT_REPO_SRC
    if not report_source.exists():
        raise RuntimeError(
            f"Report-only source not found. Checked {LOCAL_REPORT_SRC} and {REPORT_REPO_SRC}."
        )

    if report_source == LOCAL_REPORT_SRC:
        init_path = report_source / "__init__.py"
        if "comex" not in sys.modules and init_path.exists():
            spec = importlib.util.spec_from_file_location(
                "comex",
                init_path,
                submodule_search_locations=[str(report_source.resolve())],
            )
            if spec is None or spec.loader is None:
                raise RuntimeError(f"Could not load local report source as package: {report_source}")
            module = importlib.util.module_from_spec(spec)
            sys.modules["comex"] = module
            spec.loader.exec_module(module)

    report_src = str(report_source.resolve())
    if report_src not in sys.path:
        sys.path.insert(0, report_src)


def generate_report(
    *,
    gold_file: Path,
    template_path: Path,
    output_path: Path,
    state_code: str,
) -> Path:
    ensure_report_repo_on_path()

    from comex.project import Project
    from comex.reporting.excel_workbook import write_template_excel_report
    from comex.reporting.publish_report_local import read_local_gold_file
    from comex.reporting.template_report import build_template_workbook_data

    template_path = template_path.resolve()
    if not template_path.exists():
        raise RuntimeError(f"Template workbook not found: {template_path}")

    project = Project(catalog="local", schema="local", state_code=state_code, gold_table=str(gold_file))
    gold_df = read_local_gold_file(gold_file.resolve())
    report_df = gold_df.copy()

    # Product tabs in the template report are built from cd_ncm/ds_ncm.
    # For the local pipeline, reinterpret both columns at product-label grain so
    # one product aggregates even when the dictionary maps it to many SH6/NCM8s.
    product_label = None
    if "ds_produto" in report_df.columns:
        product_label = report_df["ds_produto"]
    elif "nm_ncm_produto_sh6" in report_df.columns:
        product_label = report_df["nm_ncm_produto_sh6"]

    if product_label is not None:
        product_label = product_label.fillna(report_df.get("ds_ncm")).fillna(report_df.get("cd_ncm"))
        report_df["cd_ncm"] = product_label
        report_df["ds_ncm"] = product_label

    workbook_data = build_template_workbook_data(project, report_df)
    destination = write_template_excel_report(template_path, output_path.resolve(), workbook_data)
    print(f"[report] wrote {destination}")
    return destination


def run_monthly_pipeline(
    *,
    lookback_years: int,
    verify: bool,
    force: bool,
    state_code: str,
    template_path: Path,
    report_output: Path,
) -> None:
    print("[pipeline] bronze monthly refresh")
    bronze_results = bronze_monthly_incremental(
        lookback_years=lookback_years,
        verify=verify,
        force=force,
    )
    changed_years = sorted({int(row["year"]) for row in bronze_results if row["action"] in {"downloaded_new", "replaced_changed"}})
    skipped_years = sorted({int(row["year"]) for row in bronze_results if row["action"] == "skip_unchanged"})
    unavailable_years = sorted({int(row["year"]) for row in bronze_results if row["action"] == "source_unavailable"})

    if unavailable_years and not changed_years and not skipped_years:
        raise RuntimeError(
            "Monthly bronze refresh could not reach the current-year source files. "
            f"Unavailable years: {unavailable_years}"
        )

    if changed_years:
        print(f"[pipeline] gold incremental merge for years {changed_years}")
        build_gold(
            out_all=ALL_GOLD_PATH.resolve(),
            out_sc=SC_GOLD_PATH.resolve(),
            start_year=min(changed_years),
            end_year=max(changed_years),
            incremental_merge=True,
        )
    else:
        print("[pipeline] no bronze changes detected; reusing current gold")

    print("[pipeline] generating template report")
    generate_report(
        gold_file=SC_GOLD_PATH,
        template_path=template_path,
        output_path=report_output,
        state_code=state_code,
    )


def run_backfill_pipeline(
    *,
    start_year: int,
    end_year: int | None,
    verify: bool,
    force: bool,
    state_code: str,
    template_path: Path,
    report_output: Path,
) -> None:
    final_year = end_year or datetime.utcnow().year
    print(f"[pipeline] bronze backfill {start_year}-{final_year}")
    touched_years = bronze_backfill_all(
        start_year=start_year,
        end_year=final_year,
        verify=verify,
        force=force,
    )
    if not touched_years:
        raise RuntimeError("Backfill did not download any bronze years.")

    print("[pipeline] full gold rebuild")
    build_gold(
        out_all=ALL_GOLD_PATH.resolve(),
        out_sc=SC_GOLD_PATH.resolve(),
        start_year=start_year,
        end_year=final_year,
        incremental_merge=False,
    )

    print("[pipeline] generating template report")
    generate_report(
        gold_file=SC_GOLD_PATH,
        template_path=template_path,
        output_path=report_output,
        state_code=state_code,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local bronze -> gold -> report pipeline.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    monthly = subparsers.add_parser("monthly", help="Refresh current-year bronze, increment gold, and rebuild the report.")
    monthly.add_argument("--lookback-years", type=int, default=0)
    monthly.add_argument("--verify", action=argparse.BooleanOptionalAction, default=True)
    monthly.add_argument("--force", action="store_true")
    monthly.add_argument("--state-code", default="SC")
    monthly.add_argument("--template-path", type=Path, default=DEFAULT_TEMPLATE_PATH)
    monthly.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_PATH)

    backfill = subparsers.add_parser("backfill", help="Backfill bronze, rebuild gold, and rebuild the report.")
    backfill.add_argument("--start-year", type=int, default=1997)
    backfill.add_argument("--end-year", type=int, default=None)
    backfill.add_argument("--verify", action=argparse.BooleanOptionalAction, default=True)
    backfill.add_argument("--force", action="store_true")
    backfill.add_argument("--state-code", default="SC")
    backfill.add_argument("--template-path", type=Path, default=DEFAULT_TEMPLATE_PATH)
    backfill.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_PATH)

    gold = subparsers.add_parser("gold", help="Build or merge the report-compatible gold parquet only.")
    gold.add_argument("--start-year", type=int, default=None)
    gold.add_argument("--end-year", type=int, default=None)
    gold.add_argument("--incremental-merge", action="store_true")

    report = subparsers.add_parser("report", help="Generate the template report from the current SC gold parquet.")
    report.add_argument("--gold-file", type=Path, default=SC_GOLD_PATH)
    report.add_argument("--state-code", default="SC")
    report.add_argument("--template-path", type=Path, default=DEFAULT_TEMPLATE_PATH)
    report.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_PATH)

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.command == "monthly":
        run_monthly_pipeline(
            lookback_years=args.lookback_years,
            verify=args.verify,
            force=args.force,
            state_code=args.state_code,
            template_path=args.template_path,
            report_output=args.report_output,
        )
        return

    if args.command == "backfill":
        run_backfill_pipeline(
            start_year=args.start_year,
            end_year=args.end_year,
            verify=args.verify,
            force=args.force,
            state_code=args.state_code,
            template_path=args.template_path,
            report_output=args.report_output,
        )
        return

    if args.command == "gold":
        build_gold(
            out_all=ALL_GOLD_PATH.resolve(),
            out_sc=SC_GOLD_PATH.resolve(),
            start_year=args.start_year,
            end_year=args.end_year,
            incremental_merge=args.incremental_merge,
        )
        return

    generate_report(
        gold_file=args.gold_file,
        template_path=args.template_path,
        output_path=args.report_output,
        state_code=args.state_code,
    )


if __name__ == "__main__":
    main()
