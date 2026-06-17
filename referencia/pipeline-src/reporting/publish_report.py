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
from comex.reporting.template_report import build_template_workbook_data

LOGGER = get_logger(__name__)

REQUIRED_GOLD_COLUMNS = (
    "nr_competencia",
    "nr_ano",
    "nr_mes",
    "tp_carga",
    "cd_ncm",
    "ds_ncm",
    "cd_pais",
    "ds_pais",
    "sg_uf",
    "qt_estatistica",
    "qt_kilo_liquido",
    "vl_fob",
    "vl_frete",
    "vl_seguro",
    "cd_cgce_n3",
    "ds_cgce_n3",
)

LATEST_DETAIL_COLUMNS = (
    "nr_competencia",
    "nr_ano",
    "nr_mes",
    "tp_carga",
    "cd_ncm",
    "ds_ncm",
    "cd_pais",
    "ds_pais",
    "sg_uf",
    "vl_fob",
    "qt_kilo_liquido",
    "qt_estatistica",
    "cd_cgce_n3",
    "ds_cgce_n3",
    "cd_unidade",
    "sg_unindade",
    "cd_via",
    "ds_via",
)


def missing_required_columns(columns: list[str] | tuple[str, ...]) -> list[str]:
    return [column for column in REQUIRED_GOLD_COLUMNS if column not in columns]


def resolve_output_path(project: Project, output_path: str | None) -> str:
    return output_path or project.default_report_path


def should_filter_state(state_code: str | None) -> bool:
    return bool(state_code and state_code.upper() != "ALL")


def build_metadata_sheet(
    project: Project,
    *,
    source_table: str,
    row_count: int,
    latest_row_count: int,
    metrics: dict[str, object],
) -> pd.DataFrame:
    state_scope = project.state_code if should_filter_state(project.state_code) else "ALL"
    rows = [
        ("source_table", source_table),
        ("state_scope", state_scope),
        ("row_count", row_count),
        ("latest_row_count", latest_row_count),
        ("first_competencia", metrics["first_competencia"]),
        ("latest_competencia", metrics["latest_competencia"]),
        ("competencias", metrics["competencias"]),
        ("flow_kinds", metrics["flow_kinds"]),
        ("distinct_ncm", metrics["distinct_ncm"]),
        ("distinct_countries", metrics["distinct_countries"]),
        ("total_vl_fob", metrics["total_vl_fob"]),
        ("total_qt_kilo_liquido", metrics["total_qt_kilo_liquido"]),
        ("total_qt_estatistica", metrics["total_qt_estatistica"]),
        ("total_vl_frete", metrics["total_vl_frete"]),
        ("total_vl_seguro", metrics["total_vl_seguro"]),
    ]
    return pd.DataFrame(rows, columns=["item", "value"])


def build_report_sheets(project: Project) -> dict[str, pd.DataFrame]:
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F

    spark = SparkSession.builder.getOrCreate()
    source_table = project.gold_source_table
    LOGGER.info("Reading gold source table %s", source_table)
    gold_df = spark.read.table(source_table)

    missing_columns = missing_required_columns(gold_df.columns)
    if missing_columns:
        raise RuntimeError(
            "Gold source table is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    if should_filter_state(project.state_code):
        LOGGER.info("Applying state filter sg_uf=%s", project.state_code)
        gold_df = gold_df.filter(F.col("sg_uf") == project.state_code)
    else:
        LOGGER.info("No state filter applied")

    row_count = gold_df.count()
    if row_count == 0:
        raise RuntimeError(
            f"Gold source table {source_table} returned zero rows for state filter {project.state_code!r}."
        )

    metrics_row = (
        gold_df.agg(
            F.min("nr_competencia").alias("first_competencia"),
            F.max("nr_competencia").alias("latest_competencia"),
            F.countDistinct("nr_competencia").alias("competencias"),
            F.countDistinct("tp_carga").alias("flow_kinds"),
            F.countDistinct("cd_ncm").alias("distinct_ncm"),
            F.countDistinct("cd_pais").alias("distinct_countries"),
            F.sum("vl_fob").alias("total_vl_fob"),
            F.sum("qt_kilo_liquido").alias("total_qt_kilo_liquido"),
            F.sum("qt_estatistica").alias("total_qt_estatistica"),
            F.sum("vl_frete").alias("total_vl_frete"),
            F.sum("vl_seguro").alias("total_vl_seguro"),
        )
        .first()
        .asDict(recursive=True)
    )

    latest_competencia = metrics_row["latest_competencia"]
    latest_df = gold_df.filter(F.col("nr_competencia") == F.lit(latest_competencia))
    latest_row_count = latest_df.count()
    LOGGER.info(
        "Building report for %s rows, latest_competencia=%s latest_rows=%s",
        row_count,
        latest_competencia,
        latest_row_count,
    )

    monthly_summary = (
        gold_df.groupBy("nr_ano", "nr_mes", "nr_competencia", "tp_carga")
        .agg(
            F.sum("vl_fob").alias("vl_fob"),
            F.sum("qt_kilo_liquido").alias("qt_kilo_liquido"),
            F.sum("qt_estatistica").alias("qt_estatistica"),
            F.sum("vl_frete").alias("vl_frete"),
            F.sum("vl_seguro").alias("vl_seguro"),
        )
        .orderBy("nr_ano", "nr_mes", "tp_carga")
    )

    top_products = (
        latest_df.groupBy("tp_carga", "cd_ncm", "ds_ncm")
        .agg(
            F.sum("vl_fob").alias("vl_fob"),
            F.sum("qt_kilo_liquido").alias("qt_kilo_liquido"),
            F.sum("qt_estatistica").alias("qt_estatistica"),
        )
        .orderBy(F.desc("vl_fob"), F.asc("cd_ncm"))
        .limit(50)
    )

    top_countries = (
        latest_df.groupBy("tp_carga", "cd_pais", "ds_pais")
        .agg(
            F.sum("vl_fob").alias("vl_fob"),
            F.sum("qt_kilo_liquido").alias("qt_kilo_liquido"),
            F.sum("qt_estatistica").alias("qt_estatistica"),
        )
        .orderBy(F.desc("vl_fob"), F.asc("cd_pais"))
        .limit(50)
    )

    top_cgce_n3 = (
        latest_df.groupBy("tp_carga", "cd_cgce_n3", "ds_cgce_n3")
        .agg(
            F.sum("vl_fob").alias("vl_fob"),
            F.sum("qt_kilo_liquido").alias("qt_kilo_liquido"),
            F.sum("qt_estatistica").alias("qt_estatistica"),
        )
        .orderBy(F.desc("vl_fob"), F.asc("cd_cgce_n3"))
        .limit(50)
    )

    latest_details = (
        latest_df.select(*LATEST_DETAIL_COLUMNS)
        .orderBy(F.desc("vl_fob"), F.asc("cd_ncm"), F.asc("cd_pais"))
        .limit(200)
    )

    sheets = {
        "metadata": build_metadata_sheet(
            project,
            source_table=source_table,
            row_count=row_count,
            latest_row_count=latest_row_count,
            metrics=metrics_row,
        ),
        "monthly_summary": monthly_summary.toPandas(),
        "top_products": top_products.toPandas(),
        "top_countries": top_countries.toPandas(),
        "top_cgce_n3": top_cgce_n3.toPandas(),
        "latest_sample": latest_details.toPandas(),
    }

    for sheet_name, dataframe in sheets.items():
        LOGGER.info("Prepared sheet %s rows=%s", sheet_name, len(dataframe))

    return sheets


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the final Excel report from an existing gold table.")
    parser.add_argument("--source-root", default=None)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--state-code", default=DEFAULT_STATE_CODE)
    parser.add_argument("--gold-table", default=None)
    parser.add_argument("--output-path", default=None)
    parser.add_argument("--template-path", default=None)
    args = parser.parse_args()

    project = Project(
        catalog=args.catalog,
        schema=args.schema,
        state_code=args.state_code,
        gold_table=args.gold_table,
    )
    output_path = resolve_output_path(project, args.output_path)

    LOGGER.info(
        "Starting report generation source_table=%s state_code=%s output=%s",
        project.gold_source_table,
        project.state_code,
        output_path,
    )
    if args.template_path:
        from pyspark.sql import SparkSession

        spark = SparkSession.builder.getOrCreate()
        LOGGER.info("Reading gold source table %s into pandas for template rendering", project.gold_source_table)
        gold_df = spark.read.table(project.gold_source_table).toPandas()
        workbook_data = build_template_workbook_data(project, gold_df)
        destination = write_template_excel_report(args.template_path, output_path, workbook_data)
    else:
        sheets = build_report_sheets(project)
        destination = write_excel_report(output_path, sheets)
    LOGGER.info("Wrote Excel report to %s", destination)


if __name__ == "__main__":
    main()
