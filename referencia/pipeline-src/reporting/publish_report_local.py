from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


def _bootstrap_source_path() -> None:
    source_root: str | None = None

    if "--source-root" in sys.argv:
        index = sys.argv.index("--source-root")
        if index + 1 < len(sys.argv):
            source_root = sys.argv[index + 1]
    elif "__file__" in globals():
        source_root = str(Path(__file__).resolve().parents[2])

    if source_root and source_root not in sys.path:
        sys.path.insert(0, source_root)


_bootstrap_source_path()

from comex.common.logging import get_logger
from comex.project import DEFAULT_STATE_CODE, Project
from comex.reporting.excel_workbook import write_excel_report, write_template_excel_report
from comex.reporting.publish_report import (
    LATEST_DETAIL_COLUMNS,
    build_metadata_sheet,
    missing_required_columns,
    should_filter_state,
)
from comex.reporting.template_report import (
    build_template_workbook_data,
    default_template_output_path,
)

LOGGER = get_logger(__name__)

NUMERIC_COLUMNS = (
    "nr_competencia",
    "nr_ano",
    "nr_mes",
    "qt_estatistica",
    "qt_kilo_liquido",
    "vl_fob",
    "vl_frete",
    "vl_seguro",
)


def resolve_local_output_path(gold_file: Path, output_path: str | None, state_code: str) -> Path:
    if output_path:
        return Path(output_path)

    state_suffix = state_code.lower() if should_filter_state(state_code) else "all"
    return gold_file.with_name(f"{gold_file.stem}_report_{state_suffix}.xlsx")


def read_local_gold_file(gold_file: Path) -> pd.DataFrame:
    suffix = gold_file.suffix.lower()

    if suffix == ".csv":
        return pd.read_csv(gold_file, sep=None, engine="python")

    if suffix in {".parquet", ".pq"}:
        try:
            return pd.read_parquet(gold_file)
        except ImportError as exc:
            raise RuntimeError(
                "Reading Parquet locally requires pyarrow or fastparquet."
            ) from exc

    raise RuntimeError(
        f"Unsupported local gold file format {gold_file.suffix!r}. Use .csv or .parquet."
    )


def ensure_local_columns(dataframe: pd.DataFrame) -> None:
    missing_columns = missing_required_columns(tuple(dataframe.columns))
    if missing_columns:
        raise RuntimeError(
            "Gold source file is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    missing_detail_columns = [column for column in LATEST_DETAIL_COLUMNS if column not in dataframe.columns]
    if missing_detail_columns:
        raise RuntimeError(
            "Gold source file is missing detail columns required for latest_sample: "
            + ", ".join(sorted(missing_detail_columns))
        )


def prepare_local_gold_dataframe(dataframe: pd.DataFrame, state_code: str) -> pd.DataFrame:
    gold_df = dataframe.copy()
    ensure_local_columns(gold_df)

    for column in NUMERIC_COLUMNS:
        gold_df[column] = pd.to_numeric(gold_df[column], errors="coerce")

    if should_filter_state(state_code):
        gold_df = gold_df.loc[gold_df["sg_uf"] == state_code].copy()

    if gold_df.empty:
        raise RuntimeError(f"Gold source file returned zero rows for state filter {state_code!r}.")

    return gold_df


def aggregate_latest_slice(
    latest_df: pd.DataFrame, group_columns: list[str], sort_column: str
) -> pd.DataFrame:
    return (
        latest_df.groupby(group_columns, dropna=False)[
            ["vl_fob", "qt_kilo_liquido", "qt_estatistica"]
        ]
        .sum()
        .reset_index()
        .sort_values([sort_column, group_columns[1]], ascending=[False, True])
        .head(50)
        .reset_index(drop=True)
    )


def build_local_report_sheets(
    project: Project, gold_df: pd.DataFrame, *, source_name: str
) -> dict[str, pd.DataFrame]:
    filtered_df = prepare_local_gold_dataframe(gold_df, project.state_code)

    metrics = {
        "first_competencia": filtered_df["nr_competencia"].min(),
        "latest_competencia": filtered_df["nr_competencia"].max(),
        "competencias": filtered_df["nr_competencia"].nunique(dropna=True),
        "flow_kinds": filtered_df["tp_carga"].nunique(dropna=True),
        "distinct_ncm": filtered_df["cd_ncm"].nunique(dropna=True),
        "distinct_countries": filtered_df["cd_pais"].nunique(dropna=True),
        "total_vl_fob": filtered_df["vl_fob"].sum(),
        "total_qt_kilo_liquido": filtered_df["qt_kilo_liquido"].sum(),
        "total_qt_estatistica": filtered_df["qt_estatistica"].sum(),
        "total_vl_frete": filtered_df["vl_frete"].sum(),
        "total_vl_seguro": filtered_df["vl_seguro"].sum(),
    }

    latest_competencia = metrics["latest_competencia"]
    latest_df = filtered_df.loc[filtered_df["nr_competencia"] == latest_competencia].copy()

    monthly_summary = (
        filtered_df.groupby(["nr_ano", "nr_mes", "nr_competencia", "tp_carga"], dropna=False)[
            ["vl_fob", "qt_kilo_liquido", "qt_estatistica", "vl_frete", "vl_seguro"]
        ]
        .sum()
        .reset_index()
        .sort_values(["nr_ano", "nr_mes", "tp_carga"])
        .reset_index(drop=True)
    )

    top_products = aggregate_latest_slice(latest_df, ["tp_carga", "cd_ncm", "ds_ncm"], "vl_fob")
    top_countries = aggregate_latest_slice(latest_df, ["tp_carga", "cd_pais", "ds_pais"], "vl_fob")
    top_cgce_n3 = aggregate_latest_slice(
        latest_df, ["tp_carga", "cd_cgce_n3", "ds_cgce_n3"], "vl_fob"
    )
    latest_sample = (
        latest_df.loc[:, list(LATEST_DETAIL_COLUMNS)]
        .sort_values(["vl_fob", "cd_ncm", "cd_pais"], ascending=[False, True, True])
        .head(200)
        .reset_index(drop=True)
    )

    sheets = {
        "metadata": build_metadata_sheet(
            project,
            source_table=source_name,
            row_count=len(filtered_df),
            latest_row_count=len(latest_df),
            metrics=metrics,
        ),
        "monthly_summary": monthly_summary,
        "top_products": top_products,
        "top_countries": top_countries,
        "top_cgce_n3": top_cgce_n3,
        "latest_sample": latest_sample,
    }

    for sheet_name, dataframe in sheets.items():
        LOGGER.info("Prepared local sheet %s rows=%s", sheet_name, len(dataframe))

    return sheets


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the final Excel report from a local gold file.")
    parser.add_argument("--source-root", default=None)
    parser.add_argument("--gold-file", required=True)
    parser.add_argument("--state-code", default=DEFAULT_STATE_CODE)
    parser.add_argument("--output-path", default=None)
    parser.add_argument("--template-path", default=None)
    args = parser.parse_args()

    gold_file = Path(args.gold_file)
    if args.template_path:
        output_path = Path(args.output_path) if args.output_path else default_template_output_path(gold_file, args.state_code)
    else:
        output_path = resolve_local_output_path(gold_file, args.output_path, args.state_code)
    project = Project(catalog="local", schema="local", state_code=args.state_code, gold_table=str(gold_file))

    LOGGER.info(
        "Starting local report generation gold_file=%s state_code=%s output=%s",
        gold_file,
        project.state_code,
        output_path,
    )
    gold_df = read_local_gold_file(gold_file)
    if args.template_path:
        workbook_data = build_template_workbook_data(project, gold_df)
        destination = write_template_excel_report(args.template_path, output_path, workbook_data)
    else:
        sheets = build_local_report_sheets(project, gold_df, source_name=str(gold_file))
        destination = write_excel_report(output_path, sheets)
    LOGGER.info("Wrote local Excel report to %s", destination)


if __name__ == "__main__":
    main()
