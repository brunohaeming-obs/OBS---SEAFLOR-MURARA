from __future__ import annotations

import argparse
import csv
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Iterable

import duckdb
import pandas as pd

try:
    from .paths import DADOS, ROOT
except ImportError:
    from paths import DADOS, ROOT


BRONZE_DIR = DADOS / "bronze"
GOLD_DIR = DADOS / "gold"
MANIFESTS_DIR = DADOS / "manifests"
STATE_PATH = MANIFESTS_DIR / "bronze_state.csv"
ALL_GOLD_PATH = GOLD_DIR / "comexstat_ncm_all.parquet"
SC_GOLD_PATH = GOLD_DIR / "comexstat_ncm_sc.parquet"
DEFAULT_REPORT_PATH = DADOS / "reports" / "comex_report_sc.xlsx"
DEFAULT_TEMPLATE_PATH = DADOS / "reports" / "Template - Comex Imprensa.xlsx"
REPORT_REPO_SRC = ROOT.parent / "pipeline-relatorio-comex" / "src"
AUDIT_DIR = DADOS / "audit"

METRICS = ["row_count", "vl_fob_sum", "kg_liquido_sum", "qt_estat_sum"]


def _csv_quote(path: Path) -> str:
    return path.as_posix().replace("'", "''")


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _pick(cols: Iterable[str], *candidates: str) -> str | None:
    cols_set = set(cols)
    for candidate in candidates:
        if candidate in cols_set:
            return candidate
    return None


def _num_int(expr: str | None) -> str:
    return f"TRY_CAST(NULLIF(TRIM({expr}), '') AS INTEGER)" if expr else "NULL"


def _num_double(expr: str | None) -> str:
    return f"TRY_CAST(NULLIF(TRIM({expr}), '') AS DOUBLE)" if expr else "NULL"


def _clean_text(expr: str | None) -> str:
    return f"NULLIF(TRIM({expr}), '')" if expr else "NULL"


def _clean_code(expr: str | None, width: int | None = None) -> str:
    if not expr:
        return "NULL"
    trimmed = f"NULLIF(TRIM({expr}), '')"
    stripped = f"REGEXP_REPLACE({trimmed}, '\\\\.0$', '')"
    if width:
        return f"CASE WHEN {trimmed} IS NULL THEN NULL ELSE LPAD({stripped}, {width}, '0') END"
    return stripped


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _data_rows_count(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.reader(handle, delimiter=";")
        try:
            next(reader)
        except StopIteration:
            return 0
        return sum(1 for row in reader if row)


def _write_csv(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def _to_markdown(df: pd.DataFrame) -> str:
    display = df.copy()
    max_rows = 50
    if len(display) > max_rows:
        display = display.head(max_rows)
    display = display.astype(object).where(pd.notna(display), "")
    columns = [str(col) for col in display.columns]
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for _, row in display.iterrows():
        values = [str(row[col]).replace("\n", " ").replace("|", "\\|") for col in display.columns]
        lines.append("| " + " | ".join(values) + " |")
    if len(df) > max_rows:
        lines.append(f"| ... | {' | '.join([''] * (len(columns) - 1))} |")
    return "\n".join(lines)


def _append_report(report: list[str], title: str, df: pd.DataFrame | None = None, note: str | None = None) -> None:
    report.append(f"\n## {title}\n")
    if note:
        report.append(note.strip() + "\n")
    if df is not None:
        if df.empty:
            report.append("_No rows._\n")
        else:
            report.append(_to_markdown(df) + "\n")


def _header_columns(con: duckdb.DuckDBPyConnection, csv_path: Path) -> list[str]:
    return con.execute(
        f"""
        SELECT *
        FROM read_csv_auto(
            '{_csv_quote(csv_path)}',
            HEADER=TRUE,
            IGNORE_ERRORS=TRUE,
            SAMPLE_SIZE=1,
            ALL_VARCHAR=TRUE
        )
        LIMIT 1
        """
    ).fetchdf().columns.tolist()


def _column_map(con: duckdb.DuckDBPyConnection, csv_path: Path) -> dict[str, str | None]:
    cols = _header_columns(con, csv_path)
    return {
        "co_ano": _pick(cols, "CO_ANO", "co_ano"),
        "co_mes": _pick(cols, "CO_MES", "co_mes"),
        "co_ncm": _pick(cols, "CO_NCM", "co_ncm"),
        "co_pais": _pick(cols, "CO_PAIS", "co_pais"),
        "co_unid": _pick(cols, "CO_UNID", "co_unid"),
        "co_via": _pick(cols, "CO_VIA", "co_via"),
        "co_urf": _pick(cols, "CO_URF", "co_urf"),
        "qt_estat": _pick(cols, "QT_ESTAT", "qt_estat"),
        "kg_liquido": _pick(cols, "KG_LIQUIDO", "kg_liquido", "KG_LIQ", "kg_liq"),
        "vl_fob": _pick(cols, "VL_FOB", "vl_fob", "VL_VALOR", "vl_valor"),
        "sg_uf": _pick(cols, "SG_UF_NCM", "sg_uf_ncm", "SG_UF", "sg_uf"),
    }


def _q(mapping: dict[str, str | None], key: str) -> str | None:
    col = mapping.get(key)
    return _quote_ident(col) if col else None


def _typed_csv_cte(csv_path: Path, kind: str, file_year: int, mapping: dict[str, str | None]) -> str:
    return f"""
    typed AS (
      SELECT
        ROW_NUMBER() OVER () AS source_row_id,
        '{kind}'::VARCHAR AS tp_carga,
        {file_year}::INTEGER AS arquivo_ano,
        {_num_int(_q(mapping, 'co_ano'))} AS nr_ano,
        {_num_int(_q(mapping, 'co_mes'))} AS nr_mes,
        {_clean_code(_q(mapping, 'co_ncm'), 8)} AS cd_ncm,
        {_num_int(_q(mapping, 'co_pais'))} AS cd_pais,
        {_clean_code(_q(mapping, 'co_unid'))} AS cd_unidade,
        {_clean_code(_q(mapping, 'co_via'), 2)} AS cd_via,
        {_clean_code(_q(mapping, 'co_urf'), 7)} AS cd_unidade_receita_federal,
        {_num_double(_q(mapping, 'qt_estat'))} AS qt_estatistica,
        {_num_double(_q(mapping, 'kg_liquido'))} AS qt_kilo_liquido,
        {_num_double(_q(mapping, 'vl_fob'))} AS vl_fob,
        {_clean_text(_q(mapping, 'sg_uf'))} AS sg_uf
      FROM read_csv_auto(
        '{_csv_quote(csv_path)}',
        HEADER=TRUE,
        IGNORE_ERRORS=TRUE,
        SAMPLE_SIZE=-1,
        ALL_VARCHAR=TRUE
      )
    )
    """


def _filters(args: argparse.Namespace, *, year_col: str, month_col: str, kind_col: str | None = None) -> str:
    clauses = []
    if args.year is not None:
        clauses.append(f"{year_col} = {int(args.year)}")
    if args.month is not None:
        clauses.append(f"{month_col} = {int(args.month)}")
    if args.uf:
        uf = args.uf.upper().replace("'", "''")
        clauses.append(f"UPPER(TRIM(sg_uf)) = '{uf}'")
    if args.ncm:
        ncm = args.ncm.replace("'", "''")
        clauses.append(f"cd_ncm = '{ncm}'")
    if args.country:
        clauses.append(f"cd_pais = {int(args.country)}")
    if kind_col:
        clauses.append(f"{kind_col} = '{args.kind.upper()}'")
    return "WHERE " + " AND ".join(clauses) if clauses else ""


def _metric_select(prefix: str = "") -> str:
    return f"""
      COUNT(*) AS {prefix}row_count,
      COALESCE(SUM(vl_fob), 0) AS {prefix}vl_fob_sum,
      COALESCE(SUM(qt_kilo_liquido), 0) AS {prefix}kg_liquido_sum,
      COALESCE(SUM(qt_estatistica), 0) AS {prefix}qt_estat_sum
    """


def _compare_frames(left: pd.DataFrame, right: pd.DataFrame, keys: list[str], left_name: str, right_name: str) -> pd.DataFrame:
    for frame in (left, right):
        for key in keys:
            if key not in frame.columns:
                frame[key] = pd.Series(dtype="object")
        for metric in METRICS:
            if metric not in frame.columns:
                frame[metric] = pd.Series(dtype="float64")
    merged = left.merge(right, on=keys, how="outer", suffixes=(f"_{left_name}", f"_{right_name}"))
    for metric in METRICS:
        lcol = f"{metric}_{left_name}"
        rcol = f"{metric}_{right_name}"
        if lcol in merged.columns and rcol in merged.columns:
            merged.loc[:, f"{metric}_diff"] = merged[rcol].fillna(0) - merged[lcol].fillna(0)
    return merged


def discover_case(kind: str, year: int | None, month: int | None) -> tuple[int | None, int | None, Path | None]:
    kind = kind.upper()
    candidates = sorted((BRONZE_DIR / kind).glob(f"{kind}_*.csv"))
    if year is not None:
        csv_path = BRONZE_DIR / kind / f"{kind}_{year}.csv"
        return year, month, csv_path if csv_path.exists() else None
    if not candidates:
        return year, month, None
    csv_path = candidates[-1]
    detected_year = int(csv_path.stem.split("_")[-1])
    if month is not None:
        return detected_year, month, csv_path

    con = duckdb.connect()
    try:
        mapping = _column_map(con, csv_path)
        typed = _typed_csv_cte(csv_path, kind, detected_year, mapping)
        detected_month = con.execute(
            f"""
            WITH {typed}
            SELECT MAX(nr_mes)
            FROM typed
            WHERE nr_ano = {detected_year}
            """
        ).fetchone()[0]
    finally:
        con.close()
    return detected_year, detected_month, csv_path


def sprint_1(args: argparse.Namespace, audit_dir: Path) -> pd.DataFrame:
    bronze_files = sorted(BRONZE_DIR.rglob("*.csv")) if BRONZE_DIR.exists() else []
    report_outputs = sorted((DADOS / "reports").glob("*.xlsx")) if (DADOS / "reports").exists() else []
    legacy_outputs = sorted(AUDIT_DIR.glob("*.xlsx")) if AUDIT_DIR.exists() else []
    last_log = ROOT / "last_run.log"
    log_text = last_log.read_text(encoding="utf-8", errors="replace") if last_log.exists() else ""
    legacy_seen = "Scripts\\datamarts.py" in log_text or "Scripts/datamarts.py" in log_text
    current_possible = REPORT_REPO_SRC.exists()
    decision = "current_flow_available" if current_possible else "current_flow_blocked_missing_report_repo"
    if legacy_seen:
        decision += "; legacy_flow_seen_in_last_run_log"

    rows = [
        {"item": "root", "value": str(ROOT), "exists": ROOT.exists()},
        {"item": "current_command", "value": "python main.py monthly|backfill|report", "exists": (ROOT / "main.py").exists()},
        {"item": "legacy_command", "value": "criar_relatorios.bat -> Scripts/datamarts.py", "exists": (ROOT / "criar_relatorios.bat").exists()},
        {"item": "report_repo_src", "value": str(REPORT_REPO_SRC), "exists": REPORT_REPO_SRC.exists()},
        {"item": "bronze_csv_count", "value": str(len(bronze_files)), "exists": bool(bronze_files)},
        {"item": "all_gold", "value": str(ALL_GOLD_PATH), "exists": ALL_GOLD_PATH.exists()},
        {"item": "sc_gold", "value": str(SC_GOLD_PATH), "exists": SC_GOLD_PATH.exists()},
        {"item": "template", "value": str(DEFAULT_TEMPLATE_PATH), "exists": DEFAULT_TEMPLATE_PATH.exists()},
        {"item": "report_outputs", "value": "; ".join(str(p) for p in report_outputs + legacy_outputs), "exists": bool(report_outputs or legacy_outputs)},
        {"item": "decision", "value": decision, "exists": current_possible},
    ]
    df = pd.DataFrame(rows)
    _write_csv(df, audit_dir / "sprint_1_pipeline_map.csv")
    return df


def sprint_2_source(args: argparse.Namespace, audit_dir: Path, csv_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    con = duckdb.connect()
    try:
        mapping = _column_map(con, csv_path)
        typed = _typed_csv_cte(csv_path, args.kind.upper(), args.year, mapping)
        where = _filters(args, year_col="nr_ano", month_col="nr_mes")
        summary = con.execute(
            f"""
            WITH {typed}
            SELECT
              tp_carga,
              nr_ano,
              nr_mes,
              sg_uf,
              {_metric_select()}
            FROM typed
            {where}
            GROUP BY 1, 2, 3, 4
            ORDER BY 1, 2, 3, 4
            """
        ).fetchdf()
        detail = con.execute(
            f"""
            WITH {typed}
            SELECT
              tp_carga,
              nr_ano,
              nr_mes,
              sg_uf,
              cd_ncm,
              cd_pais,
              {_metric_select()}
            FROM typed
            {where}
            GROUP BY 1, 2, 3, 4, 5, 6
            ORDER BY vl_fob_sum DESC
            """
        ).fetchdf()
    finally:
        con.close()
    _write_csv(summary, audit_dir / f"sprint_2_source_totals_{args.kind}_{args.year}_{args.month or 'all'}.csv")
    _write_csv(detail, audit_dir / f"sprint_2_source_detail_{args.kind}_{args.year}_{args.month or 'all'}.csv")
    return summary, detail


def sprint_3_bronze(args: argparse.Namespace, audit_dir: Path, csv_path: Path, source_summary: pd.DataFrame) -> pd.DataFrame:
    con = duckdb.connect()
    try:
        mapping = _column_map(con, csv_path)
        typed = _typed_csv_cte(csv_path, args.kind.upper(), args.year, mapping)
        duck_rows = con.execute(f"WITH {typed} SELECT COUNT(*) FROM typed").fetchone()[0]
        strict_read_status = "ok"
        try:
            con.execute(
                f"""
                SELECT COUNT(*)
                FROM read_csv_auto(
                  '{_csv_quote(csv_path)}',
                  HEADER=TRUE,
                  IGNORE_ERRORS=FALSE,
                  SAMPLE_SIZE=-1,
                  ALL_VARCHAR=TRUE
                )
                """
            ).fetchone()
        except Exception as exc:
            strict_read_status = str(exc).splitlines()[0][:300]

        where = _filters(args, year_col="nr_ano", month_col="nr_mes")
        bronze_summary = con.execute(
            f"""
            WITH {typed}
            SELECT
              tp_carga,
              nr_ano,
              nr_mes,
              sg_uf,
              {_metric_select()}
            FROM typed
            {where}
            GROUP BY 1, 2, 3, 4
            ORDER BY 1, 2, 3, 4
            """
        ).fetchdf()
        parsing = con.execute(
            f"""
            WITH {typed}
            SELECT
              SUM(CASE WHEN nr_ano IS NULL THEN 1 ELSE 0 END) AS missing_year,
              SUM(CASE WHEN nr_mes IS NULL THEN 1 ELSE 0 END) AS missing_month,
              SUM(CASE WHEN cd_ncm IS NULL THEN 1 ELSE 0 END) AS missing_ncm,
              SUM(CASE WHEN sg_uf IS NULL THEN 1 ELSE 0 END) AS missing_uf,
              SUM(CASE WHEN vl_fob IS NULL THEN 1 ELSE 0 END) AS missing_vl_fob,
              SUM(CASE WHEN qt_kilo_liquido IS NULL THEN 1 ELSE 0 END) AS missing_kg_liquido
            FROM typed
            """
        ).fetchdf()
    finally:
        con.close()

    compare = _compare_frames(source_summary, bronze_summary, ["tp_carga", "nr_ano", "nr_mes", "sg_uf"], "source", "bronze")
    state = _read_state(args.kind.upper(), args.year)
    meta = pd.DataFrame(
        [
            {
                "file": str(csv_path),
                "file_size_bytes": csv_path.stat().st_size,
                "csv_data_rows": _data_rows_count(csv_path),
                "duckdb_ignore_errors_rows": duck_rows,
                "row_count_diff_duckdb_minus_csv": duck_rows - _data_rows_count(csv_path),
                "sha256_actual": _sha256_file(csv_path),
                "sha256_state": state.get("sha256", ""),
                "sha256_matches_state": bool(state.get("sha256")) and state.get("sha256") == _sha256_file(csv_path),
                "strict_read_status": strict_read_status,
            }
        ]
    )
    out = pd.concat(
        [
            meta,
            parsing.add_prefix("parse_"),
            pd.DataFrame({"comparison_rows": [len(compare)]}),
        ],
        axis=1,
    )
    _write_csv(compare, audit_dir / "sprint_3_bronze_vs_source.csv")
    _write_csv(out, audit_dir / "sprint_3_bronze_integrity.csv")
    return out


def _read_state(kind: str, year: int) -> dict[str, str]:
    if not STATE_PATH.exists():
        return {}
    with STATE_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("kind") == kind and int(row.get("year", "0")) == year:
                return row
    return {}


def sprint_4_normalization(args: argparse.Namespace, audit_dir: Path, csv_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    con = duckdb.connect()
    try:
        mapping = _column_map(con, csv_path)
        typed = _typed_csv_cte(csv_path, args.kind.upper(), args.year, mapping)
        where = _filters(args, year_col="nr_ano", month_col="nr_mes")
        summary = con.execute(
            f"""
            WITH {typed}
            SELECT
              COUNT(*) AS rows_before,
              COUNT(*) AS rows_after,
              0 AS rows_dropped,
              COALESCE(SUM(vl_fob), 0) AS vl_fob_before,
              COALESCE(SUM(vl_fob), 0) AS vl_fob_after,
              0 AS vl_fob_dropped,
              COALESCE(SUM(qt_kilo_liquido), 0) AS kg_before,
              COALESCE(SUM(qt_kilo_liquido), 0) AS kg_after,
              0 AS kg_dropped,
              COALESCE(SUM(qt_estatistica), 0) AS qt_estat_before,
              COALESCE(SUM(qt_estatistica), 0) AS qt_estat_after,
              0 AS qt_estat_dropped
            FROM typed
            {where}
            """
        ).fetchdf()
        dropped = pd.DataFrame(
            columns=[
                "source_row_id",
                "tp_carga",
                "nr_ano",
                "nr_mes",
                "sg_uf",
                "cd_ncm",
                "cd_pais",
                "cd_unidade",
                "cd_via",
                "cd_unidade_receita_federal",
                "qt_estatistica",
                "qt_kilo_liquido",
                "vl_fob",
                "_rn",
            ]
        )
    finally:
        con.close()
    _write_csv(summary, audit_dir / "sprint_4_normalization_dedupe_summary.csv")
    _write_csv(dropped, audit_dir / "sprint_4_normalization_dropped_examples.csv")
    return summary, dropped


def _gold_totals(con: duckdb.DuckDBPyConnection, path: Path, args: argparse.Namespace) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    where = _filters(args, year_col="nr_ano", month_col="nr_mes", kind_col="tp_carga")
    return con.execute(
        f"""
        SELECT
          tp_carga,
          nr_ano,
          nr_mes,
          sg_uf,
          cd_ncm,
          {_metric_select()}
        FROM read_parquet('{_csv_quote(path)}', union_by_name=true)
        {where}
        GROUP BY 1, 2, 3, 4, 5
        ORDER BY vl_fob_sum DESC
        """
    ).fetchdf()


def sprint_5_gold(args: argparse.Namespace, audit_dir: Path, source_detail: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    con = duckdb.connect()
    try:
        gold_all = _gold_totals(con, ALL_GOLD_PATH, args)
        gold_sc = _gold_totals(con, SC_GOLD_PATH, args)
        source_keys = ["tp_carga", "nr_ano", "nr_mes", "sg_uf", "cd_ncm"]
        source_by_ncm = (
            source_detail.groupby(source_keys, dropna=False)[METRICS]
            .sum(numeric_only=True)
            .reset_index()
            if not source_detail.empty
            else pd.DataFrame(columns=source_keys + METRICS)
        )
        gold_compare = _compare_frames(source_by_ncm, gold_all, source_keys, "source", "gold")
        sc_source = source_by_ncm[source_by_ncm["sg_uf"].astype(str).str.upper() == args.uf.upper()] if args.uf else source_by_ncm
        sc_compare = _compare_frames(sc_source, gold_sc, source_keys, "source", "sc_gold")

        unmatched_ncm = pd.DataFrame()
        unmatched_country = pd.DataFrame()
        if SC_GOLD_PATH.exists():
            year_filter = f"AND nr_ano = {int(args.year)}" if args.year is not None else ""
            unmatched_ncm = con.execute(
                f"""
                SELECT cd_ncm, COUNT(*) AS rows, SUM(vl_fob) AS vl_fob_sum
                FROM read_parquet('{_csv_quote(SC_GOLD_PATH)}', union_by_name=true)
                WHERE tp_carga = '{args.kind.upper()}'
                  {year_filter}
                  AND ds_produto = cd_ncm
                GROUP BY 1
                ORDER BY rows DESC
                LIMIT {int(args.detail_limit)}
                """
            ).fetchdf()
            unmatched_country = con.execute(
                f"""
                SELECT cd_pais, COUNT(*) AS rows, SUM(vl_fob) AS vl_fob_sum
                FROM read_parquet('{_csv_quote(SC_GOLD_PATH)}', union_by_name=true)
                WHERE tp_carga = '{args.kind.upper()}'
                  {year_filter}
                  AND ds_pais IS NULL
                GROUP BY 1
                ORDER BY rows DESC
                LIMIT {int(args.detail_limit)}
                """
            ).fetchdf()
    finally:
        con.close()

    _write_csv(gold_compare, audit_dir / "sprint_5_gold_comparison.csv")
    _write_csv(sc_compare, audit_dir / "sprint_5_sc_gold_comparison.csv")
    _write_csv(unmatched_ncm, audit_dir / "sprint_5_unmatched_ncm.csv")
    _write_csv(unmatched_country, audit_dir / "sprint_5_unmatched_country.csv")
    return gold_compare, sc_compare, unmatched_ncm, unmatched_country


def sprint_6_report_grain(args: argparse.Namespace, audit_dir: Path) -> pd.DataFrame:
    if not SC_GOLD_PATH.exists():
        df = pd.DataFrame([{"status": "blocked", "reason": f"Missing {SC_GOLD_PATH}"}])
        _write_csv(df, audit_dir / "sprint_6_product_mapping.csv")
        return df

    con = duckdb.connect()
    try:
        where = _filters(args, year_col="nr_ano", month_col="nr_mes", kind_col="tp_carga")
        df = con.execute(
            f"""
            WITH base AS (
              SELECT
                COALESCE(ds_produto, nm_ncm_produto_sh6, ds_ncm, cd_ncm) AS product_label,
                cd_ncm,
                vl_fob,
                qt_kilo_liquido,
                qt_estatistica
              FROM read_parquet('{_csv_quote(SC_GOLD_PATH)}', union_by_name=true)
              {where}
            )
            SELECT
              product_label,
              COUNT(DISTINCT cd_ncm) AS ncm8_count,
              COUNT(*) AS row_count,
              COALESCE(SUM(vl_fob), 0) AS vl_fob_sum,
              COALESCE(SUM(qt_kilo_liquido), 0) AS kg_liquido_sum,
              COALESCE(SUM(qt_estatistica), 0) AS qt_estat_sum
            FROM base
            GROUP BY 1
            ORDER BY ncm8_count DESC, vl_fob_sum DESC
            LIMIT {int(args.detail_limit)}
            """
        ).fetchdf()
    finally:
        con.close()
    _write_csv(df, audit_dir / "sprint_6_product_mapping.csv")
    return df


def sprint_7_excel(args: argparse.Namespace, audit_dir: Path) -> pd.DataFrame:
    report_path = Path(args.report_path)
    if not report_path.exists():
        df = pd.DataFrame([{"status": "blocked", "reason": f"Missing report workbook: {report_path}"}])
        _write_csv(df, audit_dir / "sprint_7_excel_values.csv")
        return df
    try:
        sheets = pd.read_excel(report_path, sheet_name=None, header=None, nrows=int(args.excel_rows))
    except Exception as exc:
        df = pd.DataFrame([{"status": "blocked", "reason": str(exc)}])
        _write_csv(df, audit_dir / "sprint_7_excel_values.csv")
        return df

    rows: list[dict[str, object]] = []
    for sheet_name, frame in sheets.items():
        if args.excel_sheet and sheet_name != args.excel_sheet:
            continue
        for row_idx, row in frame.iterrows():
            for col_idx, value in row.items():
                if pd.api.types.is_number(value):
                    rows.append(
                        {
                            "sheet": sheet_name,
                            "excel_row": int(row_idx) + 1,
                            "excel_col": int(col_idx) + 1,
                            "value": value,
                        }
                    )
    df = pd.DataFrame(rows[: int(args.detail_limit)])
    _write_csv(df, audit_dir / "sprint_7_excel_values.csv")
    return df


def sprint_8_root_cause(audit_dir: Path, dedupe: pd.DataFrame, bronze: pd.DataFrame, product_map: pd.DataFrame, excel_values: pd.DataFrame) -> pd.DataFrame:
    findings: list[dict[str, str]] = []
    if not dedupe.empty:
        rows_dropped = float(dedupe.iloc[0].get("rows_dropped", 0) or 0)
        vl_dropped = float(dedupe.iloc[0].get("vl_fob_dropped", 0) or 0)
        if rows_dropped or vl_dropped:
            findings.append(
                {
                    "stage": "gold_normalization",
                    "severity": "high",
                    "finding": f"Dedupe removed {rows_dropped:g} rows and {vl_dropped:g} VL_FOB.",
                    "recommendation": "Remove dedupe or include all source dimensions that make a row unique.",
                }
            )
    if not bronze.empty:
        status = str(bronze.iloc[0].get("strict_read_status", "ok"))
        row_diff = float(bronze.iloc[0].get("row_count_diff_duckdb_minus_csv", 0) or 0)
        if status != "ok" or row_diff:
            findings.append(
                {
                    "stage": "bronze_read",
                    "severity": "medium",
                    "finding": f"Strict CSV read status: {status}; row diff: {row_diff:g}.",
                    "recommendation": "Add fail-fast or explicit skipped-row diagnostics before gold build.",
                }
            )
    if not product_map.empty and "ncm8_count" in product_map.columns:
        max_ncm = product_map["ncm8_count"].max()
        if pd.notna(max_ncm) and max_ncm > 1:
            findings.append(
                {
                    "stage": "report_aggregation",
                    "severity": "info",
                    "finding": f"At least one product label groups {int(max_ncm)} NCM8 codes.",
                    "recommendation": "Compare report values at product-label grain, or add an NCM8 audit tab.",
                }
            )
    if not excel_values.empty and "status" in excel_values.columns:
        findings.append(
            {
                "stage": "excel_report",
                "severity": "medium",
                "finding": str(excel_values.iloc[0].get("reason", "Excel validation blocked.")),
                "recommendation": "Generate or provide the final workbook before cell-level reconciliation.",
            }
        )
    if not findings:
        findings.append(
            {
                "stage": "all_checked_stages",
                "severity": "none",
                "finding": "No divergence was detected in available local inputs.",
                "recommendation": "Run again with the exact discrepant year/month/product and the final workbook.",
            }
        )
    df = pd.DataFrame(findings)
    _write_csv(df, audit_dir / "sprint_8_root_cause_summary.csv")
    return df


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run sprint-based Comex report validation audits.")
    parser.add_argument("--kind", choices=["EXP", "IMP"], default="EXP")
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument("--month", type=int, default=None)
    parser.add_argument("--uf", default="SC")
    parser.add_argument("--ncm", default=None)
    parser.add_argument("--country", type=int, default=None)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--excel-sheet", default=None)
    parser.add_argument("--excel-rows", type=int, default=80)
    parser.add_argument("--detail-limit", type=int, default=100)
    parser.add_argument("--audit-dir", type=Path, default=AUDIT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.kind = args.kind.upper()
    detected_year, detected_month, csv_path = discover_case(args.kind, args.year, args.month)
    args.year = args.year or detected_year
    args.month = args.month or detected_month

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    audit_dir = args.audit_dir / f"validation_{args.kind}_{args.year or 'unknown'}_{args.month or 'all'}_{run_id}"
    audit_dir.mkdir(parents=True, exist_ok=True)

    report: list[str] = [
        "# Comex Report Validation\n",
        f"- Generated at: {datetime.now().isoformat(timespec='seconds')}",
        f"- Audit dir: `{audit_dir}`",
        f"- Case: kind={args.kind}, year={args.year}, month={args.month}, uf={args.uf}, ncm={args.ncm}, country={args.country}",
    ]

    print(f"[audit] writing outputs to {audit_dir}")

    pipeline_map = sprint_1(args, audit_dir)
    print("[sprint 1] pipeline map")
    print(pipeline_map.to_string(index=False))
    _append_report(report, "Sprint 1 - Pipeline Map", pipeline_map)

    if csv_path is None or args.year is None:
        blocked = pd.DataFrame([{"status": "blocked", "reason": f"No bronze CSV found for {args.kind}_{args.year or '*'}"}])
        for name in [
            "sprint_2_source_totals_blocked.csv",
            "sprint_3_bronze_integrity_blocked.csv",
            "sprint_4_normalization_dedupe_summary_blocked.csv",
        ]:
            _write_csv(blocked, audit_dir / name)
        _append_report(report, "Blocked", blocked, "Bronze source data is required for sprints 2-4.")
        (audit_dir / "validation_report.md").write_text("\n".join(report), encoding="utf-8")
        print(f"[audit] blocked: no bronze CSV found. Report: {audit_dir / 'validation_report.md'}")
        return

    source_summary, source_detail = sprint_2_source(args, audit_dir, csv_path)
    print("[sprint 2] source totals")
    print(source_summary.to_string(index=False))
    _append_report(report, "Sprint 2 - Source Totals", source_summary)

    bronze = sprint_3_bronze(args, audit_dir, csv_path, source_summary)
    print("[sprint 3] bronze integrity")
    print(bronze.to_string(index=False))
    _append_report(report, "Sprint 3 - Bronze Integrity", bronze)

    dedupe, dropped = sprint_4_normalization(args, audit_dir, csv_path)
    print("[sprint 4] normalization dedupe")
    print(dedupe.to_string(index=False))
    _append_report(report, "Sprint 4 - Normalization Dedupe", dedupe)
    _append_report(report, "Sprint 4 - Dropped Row Examples", dropped.head(20))

    gold_compare, sc_compare, unmatched_ncm, unmatched_country = sprint_5_gold(args, audit_dir, source_detail)
    print("[sprint 5] gold comparison")
    print(gold_compare.head(20).to_string(index=False) if not gold_compare.empty else "blocked: gold parquet missing")
    _append_report(report, "Sprint 5 - Gold Comparison", gold_compare.head(20))
    _append_report(report, "Sprint 5 - SC Gold Comparison", sc_compare.head(20))
    _append_report(report, "Sprint 5 - Unmatched NCM", unmatched_ncm.head(20))
    _append_report(report, "Sprint 5 - Unmatched Countries", unmatched_country.head(20))

    product_map = sprint_6_report_grain(args, audit_dir)
    print("[sprint 6] product-label grain")
    print(product_map.head(20).to_string(index=False))
    _append_report(report, "Sprint 6 - Product Mapping", product_map.head(20))

    excel_values = sprint_7_excel(args, audit_dir)
    print("[sprint 7] excel values")
    print(excel_values.head(20).to_string(index=False))
    _append_report(report, "Sprint 7 - Excel Values", excel_values.head(20))

    root_cause = sprint_8_root_cause(audit_dir, dedupe, bronze, product_map, excel_values)
    print("[sprint 8] root cause summary")
    print(root_cause.to_string(index=False))
    _append_report(report, "Sprint 8 - Root Cause Summary", root_cause)

    report_path = audit_dir / "validation_report.md"
    report_path.write_text("\n".join(report), encoding="utf-8")
    print(f"[audit] report written: {report_path}")


if __name__ == "__main__":
    main()
