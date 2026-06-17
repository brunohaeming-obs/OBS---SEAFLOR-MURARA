from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

import duckdb
import pandas as pd

try:
    from .paths import DADOS
except ImportError:
    from paths import DADOS

BRONZE_DIR = DADOS / "bronze"
GOLD_DIR = DADOS / "gold"
TEMP_NORMALIZED_DIR = GOLD_DIR / "_tmp_report_gold"
TEMP_OUTPUT_DIR = TEMP_NORMALIZED_DIR / "_out"

DICT_DIR = DADOS / "silver" / "DICT"
DICT_NCM_XLSX = DICT_DIR / "NCM_SH4 - atualizado 07.04.2026.xlsx"
DICT_NCM_SHEET = "Dim_ncm_cnae_sh4"
DICT_PAIS_CSV = DICT_DIR / "PAIS.csv"

ALL_GOLD_PATH = GOLD_DIR / "comexstat_ncm_all.parquet"
SC_GOLD_PATH = GOLD_DIR / "comexstat_ncm_sc.parquet"

TARGET_COLUMNS = [
    "nr_competencia",
    "nr_ano",
    "nr_mes",
    "tp_carga",
    "cd_ncm",
    "ds_ncm",
    "cd_cuci_secao",
    "ds_cuci_secao",
    "cd_cuci_grupo",
    "ds_cuci_grupo",
    "cd_unidade",
    "ds_unindade",
    "sg_unindade",
    "cd_pais",
    "ds_pais",
    "sg_uf",
    "cd_via",
    "ds_via",
    "cd_unidade_receita_federal",
    "ds_unidade_receita_federal",
    "qt_estatistica",
    "qt_kilo_liquido",
    "vl_fob",
    "vl_frete",
    "vl_seguro",
    "cd_cgce_n3",
    "ds_cgce_n3",
    "ds_cgce_n3_ingles",
    "ds_cgce_n3_espanhol",
    "ds_cgce_n2",
    "ds_cgce_n2_ingles",
    "ds_cgce_n2_espanhol",
    "ds_cgce_n1",
    "ds_cgce_n1_ingles",
    "ds_cgce_n1_espanhol",
    "cd_cuci_item",
    "ds_cuci_item",
    "cd_cuci_sub",
    "ds_cuci_sub",
    "cd_cuci_divisao",
    "ds_cuci_divisao",
    "cd_cuci_sec",
    "ds_cuci_sec",
    "cd_fator_agregado",
    "ds_fator_agregado",
    "ds_fator_agregado_gp",
    "cd_isic_classe",
    "ds_isic_classe",
    "ds_isic_classe_ingles",
    "ds_isic_classe_espanhol",
    "cd_isic_grupo",
    "ds_isic_grupo",
    "ds_isic_grupo_ingles",
    "ds_isic_grupo_espanhol",
    "cd_isic_divisao",
    "ds_isic_divisao",
    "ds_isic_divisao_ingles",
    "ds_isic_divisao_espanhol",
    "cd_isic_secao",
    "ds_isic_secao",
    "ds_isic_secao_ingles",
    "ds_isic_secao_espanhol",
    "cd_ppe",
    "ds_ppe",
    "ds_ppe_ingles",
    "cd_ppi",
    "ds_ppi",
    "ds_ppi_ingles",
    "cd_sh6",
    "ds_sh6_portugues",
    "ds_sh6_espanhol",
    "ds_sh6_ingles",
    "cd_sh4",
    "ds_sh4_portugues",
    "ds_sh4_espanhol",
    "ds_sh4_ingles",
    "cd_sh2",
    "ds_sh2_portugues",
    "ds_sh2_espanhol",
    "ds_sh2_ingles",
    "cd_ncm_secrom",
    "ds_sec_portugues",
    "ds_sec_espanhol",
    "ds_sec_ingles",
    "cd_siit",
    "ds_siit",
    "nm_ncm_sh8",
    "nm_ncm_sh4",
    "cd_ncm_sh6",
    "nm_ncm_produto_sh6",
]

EXTRA_COLUMNS = [
    "ds_produto",
    "sc_competitiva",
]


def _pick(cols: set[str], *candidates: str) -> str | None:
    for candidate in candidates:
        if candidate in cols:
            return candidate
    return None


def _q(column: str | None) -> str | None:
    return f'"{column}"' if column else None


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


def load_ncm_dimension() -> pd.DataFrame:
    usecols = [
        "COD_SH4",
        "Código NCM 8 dígitos",
        "SH6",
        "NO_NCM_POR",
        "NO_SH4",
        "Produto",
        "CNAE grupo",
        "Descrição CNAE grupo",
        "CNAE divisão",
        "Descrição CNAE divisão",
        "SC Competitiva",
        "GRANDE SETOR",
    ]
    dim = pd.read_excel(
        DICT_NCM_XLSX,
        sheet_name=DICT_NCM_SHEET,
        usecols=usecols,
        dtype={"Código NCM 8 dígitos": "string"},
    )

    dim["cd_ncm"] = (
        dim["Código NCM 8 dígitos"]
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
        .str.zfill(8)
    )
    dim["cod_sh4"] = (
        dim["COD_SH4"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip().str.zfill(4)
    )
    dim["sh6"] = dim["SH6"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip().str.zfill(6)

    dim = dim.rename(
        columns={
            "NO_NCM_POR": "ds_ncm",
            "NO_SH4": "nm_ncm_sh4",
            "Produto": "nm_ncm_produto_sh6",
            "CNAE grupo": "cd_cnae_grupo",
            "Descrição CNAE grupo": "ds_cnae_grupo",
            "CNAE divisão": "cd_cnae_divisao",
            "Descrição CNAE divisão": "ds_cnae_divisao",
            "SC Competitiva": "sc_competitiva",
            "GRANDE SETOR": "grande_setor",
        }
    )
    dim = dim.dropna(subset=["cd_ncm"]).drop_duplicates(subset=["cd_ncm"], keep="first")
    return dim[
        [
            "cd_ncm",
            "ds_ncm",
            "cod_sh4",
            "sh6",
            "nm_ncm_sh4",
            "nm_ncm_produto_sh6",
            "cd_cnae_grupo",
            "ds_cnae_grupo",
            "cd_cnae_divisao",
            "ds_cnae_divisao",
            "sc_competitiva",
            "grande_setor",
        ]
    ]


def load_country_dimension() -> pd.DataFrame:
    dim = pd.read_csv(
        DICT_PAIS_CSV,
        sep=";",
        encoding="latin1",
        usecols=["CO_PAIS", "NO_PAIS"],
    )
    dim = dim.rename(columns={"CO_PAIS": "cd_pais", "NO_PAIS": "ds_pais"})
    dim["cd_pais"] = pd.to_numeric(dim["cd_pais"], errors="coerce").astype("Int64")
    dim["ds_pais"] = dim["ds_pais"].astype("string").str.strip()
    dim = dim.dropna(subset=["cd_pais"]).drop_duplicates(subset=["cd_pais"], keep="first")
    return dim


def bronze_files(start_year: int | None, end_year: int | None, kinds: list[str]) -> list[tuple[str, int, Path]]:
    found: list[tuple[str, int, Path]] = []
    for kind in kinds:
        for src in sorted((BRONZE_DIR / kind).glob(f"{kind}_*.csv")):
            match = re.match(rf"{kind}_(\d{{4}})\.csv$", src.name, flags=re.IGNORECASE)
            if not match:
                continue
            year = int(match.group(1))
            if start_year is not None and year < start_year:
                continue
            if end_year is not None and year > end_year:
                continue
            found.append((kind.upper(), year, src.resolve()))
    return found


def touched_years(files: list[tuple[str, int, Path]]) -> list[int]:
    return sorted({year for _, year, _ in files})


def normalize_bronze_file(con: duckdb.DuckDBPyConnection, kind: str, file_year: int, src: Path) -> Path:
    out_path = TEMP_NORMALIZED_DIR / f"{kind}_{file_year}.parquet"

    header_df = con.execute(
        f"""
        SELECT *
        FROM read_csv_auto(
            '{src.as_posix()}',
            HEADER=TRUE,
            IGNORE_ERRORS=TRUE,
            SAMPLE_SIZE=1,
            ALL_VARCHAR=TRUE
        )
        LIMIT 1
        """
    ).fetchdf()
    cols = set(header_df.columns)

    co_ano = _pick(cols, "CO_ANO", "co_ano")
    co_mes = _pick(cols, "CO_MES", "co_mes")
    co_ncm = _pick(cols, "CO_NCM", "co_ncm")
    co_pais = _pick(cols, "CO_PAIS", "co_pais")
    co_unid = _pick(cols, "CO_UNID", "co_unid")
    co_via = _pick(cols, "CO_VIA", "co_via")
    co_urf = _pick(cols, "CO_URF", "co_urf")
    qt_estat = _pick(cols, "QT_ESTAT", "qt_estat")
    kg_liquido = _pick(cols, "KG_LIQUIDO", "kg_liquido", "KG_LIQ", "kg_liq")
    vl_fob = _pick(cols, "VL_FOB", "vl_fob", "VL_VALOR", "vl_valor")
    sg_uf = _pick(cols, "SG_UF_NCM", "sg_uf_ncm", "SG_UF", "sg_uf")

    sql = f"""
    COPY (
      WITH typed AS (
        SELECT
          '{kind}'::VARCHAR AS tp_carga,
          {file_year}::INTEGER AS arquivo_ano,
          {_num_int(_q(co_ano))} AS nr_ano,
          {_num_int(_q(co_mes))} AS nr_mes,
          {_clean_code(_q(co_ncm), 8)} AS cd_ncm,
          {_num_int(_q(co_pais))} AS cd_pais,
          {_clean_code(_q(co_unid))} AS cd_unidade,
          {_clean_code(_q(co_via), 2)} AS cd_via,
          {_clean_code(_q(co_urf), 7)} AS cd_unidade_receita_federal,
          {_num_double(_q(qt_estat))} AS qt_estatistica,
          {_num_double(_q(kg_liquido))} AS qt_kilo_liquido,
          {_num_double(_q(vl_fob))} AS vl_fob,
          {_clean_text(_q(sg_uf))} AS sg_uf
        FROM read_csv_auto(
          '{src.as_posix()}',
          HEADER=TRUE,
          IGNORE_ERRORS=TRUE,
          SAMPLE_SIZE=-1,
          ALL_VARCHAR=TRUE
        )
      )
      SELECT *
      FROM typed
    )
    TO '{out_path.as_posix()}'
    (FORMAT PARQUET, OVERWRITE_OR_IGNORE 1);
    """
    con.execute(sql)
    return out_path


def build_gold_select(normalized_glob: str) -> str:
    return f"""
    WITH fact AS (
      SELECT
        *,
        CASE
          WHEN nr_ano IS NULL OR nr_mes IS NULL THEN NULL
          ELSE (nr_ano * 100) + nr_mes
        END AS nr_competencia
      FROM read_parquet('{normalized_glob}', union_by_name=true)
      WHERE (vl_fob IS NULL OR vl_fob >= 0)
        AND (qt_kilo_liquido IS NULL OR qt_kilo_liquido >= 0)
    )
    SELECT
      f.nr_competencia,
      f.nr_ano,
      f.nr_mes,
      f.tp_carga,
      f.cd_ncm,
      COALESCE(d.ds_ncm, d.nm_ncm_produto_sh6, f.cd_ncm) AS ds_ncm,
      CAST(NULL AS VARCHAR) AS cd_cuci_secao,
      CAST(NULL AS VARCHAR) AS ds_cuci_secao,
      CAST(NULL AS VARCHAR) AS cd_cuci_grupo,
      CAST(NULL AS VARCHAR) AS ds_cuci_grupo,
      f.cd_unidade,
      f.cd_unidade AS ds_unindade,
      f.cd_unidade AS sg_unindade,
      f.cd_pais,
      p.ds_pais,
      f.sg_uf,
      f.cd_via,
      CAST(NULL AS VARCHAR) AS ds_via,
      f.cd_unidade_receita_federal,
      CAST(NULL AS VARCHAR) AS ds_unidade_receita_federal,
      f.qt_estatistica,
      f.qt_kilo_liquido,
      f.vl_fob,
      CAST(NULL AS DOUBLE) AS vl_frete,
      CAST(NULL AS DOUBLE) AS vl_seguro,
      CAST(d.cd_cnae_divisao AS VARCHAR) AS cd_cgce_n3,
      d.ds_cnae_divisao AS ds_cgce_n3,
      CAST(NULL AS VARCHAR) AS ds_cgce_n3_ingles,
      CAST(NULL AS VARCHAR) AS ds_cgce_n3_espanhol,
      d.ds_cnae_grupo AS ds_cgce_n2,
      CAST(NULL AS VARCHAR) AS ds_cgce_n2_ingles,
      CAST(NULL AS VARCHAR) AS ds_cgce_n2_espanhol,
      d.grande_setor AS ds_cgce_n1,
      CAST(NULL AS VARCHAR) AS ds_cgce_n1_ingles,
      CAST(NULL AS VARCHAR) AS ds_cgce_n1_espanhol,
      CAST(NULL AS VARCHAR) AS cd_cuci_item,
      CAST(NULL AS VARCHAR) AS ds_cuci_item,
      CAST(NULL AS VARCHAR) AS cd_cuci_sub,
      CAST(NULL AS VARCHAR) AS ds_cuci_sub,
      CAST(NULL AS VARCHAR) AS cd_cuci_divisao,
      CAST(NULL AS VARCHAR) AS ds_cuci_divisao,
      CAST(NULL AS VARCHAR) AS cd_cuci_sec,
      CAST(NULL AS VARCHAR) AS ds_cuci_sec,
      CAST(NULL AS VARCHAR) AS cd_fator_agregado,
      CAST(NULL AS VARCHAR) AS ds_fator_agregado,
      CAST(NULL AS VARCHAR) AS ds_fator_agregado_gp,
      CAST(NULL AS VARCHAR) AS cd_isic_classe,
      CAST(NULL AS VARCHAR) AS ds_isic_classe,
      CAST(NULL AS VARCHAR) AS ds_isic_classe_ingles,
      CAST(NULL AS VARCHAR) AS ds_isic_classe_espanhol,
      CAST(NULL AS VARCHAR) AS cd_isic_grupo,
      CAST(NULL AS VARCHAR) AS ds_isic_grupo,
      CAST(NULL AS VARCHAR) AS ds_isic_grupo_ingles,
      CAST(NULL AS VARCHAR) AS ds_isic_grupo_espanhol,
      CAST(NULL AS VARCHAR) AS cd_isic_divisao,
      CAST(NULL AS VARCHAR) AS ds_isic_divisao,
      CAST(NULL AS VARCHAR) AS ds_isic_divisao_ingles,
      CAST(NULL AS VARCHAR) AS ds_isic_divisao_espanhol,
      CAST(NULL AS VARCHAR) AS cd_isic_secao,
      CAST(NULL AS VARCHAR) AS ds_isic_secao,
      CAST(NULL AS VARCHAR) AS ds_isic_secao_ingles,
      CAST(NULL AS VARCHAR) AS ds_isic_secao_espanhol,
      CAST(NULL AS VARCHAR) AS cd_ppe,
      CAST(NULL AS VARCHAR) AS ds_ppe,
      CAST(NULL AS VARCHAR) AS ds_ppe_ingles,
      CAST(NULL AS VARCHAR) AS cd_ppi,
      CAST(NULL AS VARCHAR) AS ds_ppi,
      CAST(NULL AS VARCHAR) AS ds_ppi_ingles,
      d.sh6 AS cd_sh6,
      CAST(NULL AS VARCHAR) AS ds_sh6_portugues,
      CAST(NULL AS VARCHAR) AS ds_sh6_espanhol,
      CAST(NULL AS VARCHAR) AS ds_sh6_ingles,
      d.cod_sh4 AS cd_sh4,
      d.nm_ncm_sh4 AS ds_sh4_portugues,
      CAST(NULL AS VARCHAR) AS ds_sh4_espanhol,
      CAST(NULL AS VARCHAR) AS ds_sh4_ingles,
      CASE
        WHEN f.cd_ncm IS NULL THEN NULL
        ELSE SUBSTR(f.cd_ncm, 1, 2)
      END AS cd_sh2,
      CAST(NULL AS VARCHAR) AS ds_sh2_portugues,
      CAST(NULL AS VARCHAR) AS ds_sh2_espanhol,
      CAST(NULL AS VARCHAR) AS ds_sh2_ingles,
      CAST(NULL AS VARCHAR) AS cd_ncm_secrom,
      CAST(NULL AS VARCHAR) AS ds_sec_portugues,
      CAST(NULL AS VARCHAR) AS ds_sec_espanhol,
      CAST(NULL AS VARCHAR) AS ds_sec_ingles,
      CAST(NULL AS VARCHAR) AS cd_siit,
      CAST(NULL AS VARCHAR) AS ds_siit,
      COALESCE(d.ds_ncm, d.nm_ncm_produto_sh6, f.cd_ncm) AS nm_ncm_sh8,
      d.nm_ncm_sh4,
      d.sh6 AS cd_ncm_sh6,
      d.nm_ncm_produto_sh6,
      COALESCE(d.nm_ncm_produto_sh6, d.ds_ncm, f.cd_ncm) AS ds_produto,
      d.sc_competitiva
    FROM fact f
    LEFT JOIN dim_ncm AS d
      ON f.cd_ncm = d.cd_ncm
    LEFT JOIN dim_pais AS p
      ON f.cd_pais = p.cd_pais
    """


def _write_query_to_parquet(con: duckdb.DuckDBPyConnection, query: str, out_path: Path) -> None:
    con.execute(
        f"""
        COPY (
          {query}
        )
        TO '{out_path.as_posix()}'
        (FORMAT PARQUET, OVERWRITE_OR_IGNORE 1);
        """
    )


def _merge_existing_gold(
    con: duckdb.DuckDBPyConnection,
    *,
    existing_path: Path,
    partial_path: Path,
    output_path: Path,
    years_to_replace: list[int],
) -> None:
    if not existing_path.exists():
        shutil.copyfile(partial_path, output_path)
        return

    years_csv = ", ".join(str(year) for year in years_to_replace)
    temp_output = output_path.with_name(output_path.stem + "_merged_tmp.parquet")
    _write_query_to_parquet(
        con,
        f"""
        SELECT *
        FROM read_parquet('{existing_path.as_posix()}')
        WHERE nr_ano NOT IN ({years_csv})
        UNION ALL
        SELECT *
        FROM read_parquet('{partial_path.as_posix()}')
        """,
        temp_output,
    )
    temp_output.replace(output_path)


def build_gold(
    out_all: Path,
    out_sc: Path,
    start_year: int | None,
    end_year: int | None,
    *,
    incremental_merge: bool = False,
) -> None:
    files = bronze_files(start_year, end_year, ["EXP", "IMP"])
    if not files:
        raise RuntimeError("No bronze CSV files matched the requested filters.")

    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()
    con.register("dim_ncm", load_ncm_dimension())
    con.register("dim_pais", load_country_dimension())

    try:
        print(f"Normalizing {len(files)} bronze files...")
        for index, (kind, year, src) in enumerate(files, start=1):
            print(f"[{index:>3}/{len(files)}] {kind}_{year} -> normalized parquet")
            normalize_bronze_file(con, kind, year, src)

        normalized_glob = (TEMP_NORMALIZED_DIR / "*.parquet").as_posix()
        gold_select = build_gold_select(normalized_glob)
        years_to_replace = touched_years(files)

        partial_all = TEMP_OUTPUT_DIR / "_partial_all.parquet"
        partial_sc = TEMP_OUTPUT_DIR / "_partial_sc.parquet"
        _write_query_to_parquet(con, gold_select, partial_all)
        _write_query_to_parquet(
            con,
            f"""
            SELECT *
            FROM ({gold_select}) AS gold_all
            WHERE sg_uf = 'SC'
            """,
            partial_sc,
        )

        if incremental_merge:
            print(f"Merging years {years_to_replace} into full gold -> {out_all}")
            _merge_existing_gold(
                con,
                existing_path=out_all,
                partial_path=partial_all,
                output_path=out_all,
                years_to_replace=years_to_replace,
            )
            print(f"Merging years {years_to_replace} into SC gold -> {out_sc}")
            _merge_existing_gold(
                con,
                existing_path=out_sc,
                partial_path=partial_sc,
                output_path=out_sc,
                years_to_replace=years_to_replace,
            )
        else:
            print(f"Writing full gold parquet -> {out_all}")
            shutil.copyfile(partial_all, out_all)
            print(f"Writing SC-only gold parquet -> {out_sc}")
            shutil.copyfile(partial_sc, out_sc)

        schema = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{out_sc.as_posix()}')").fetchdf()
        actual_columns = schema["column_name"].tolist()
        missing = [column for column in TARGET_COLUMNS if column not in actual_columns]
        if missing:
            raise RuntimeError("SC gold parquet is missing target columns: " + ", ".join(missing))
        missing_extra = [column for column in EXTRA_COLUMNS if column not in actual_columns]
        if missing_extra:
            raise RuntimeError("SC gold parquet is missing extra columns: " + ", ".join(missing_extra))

        rows_all = con.execute(f"SELECT COUNT(*) FROM read_parquet('{out_all.as_posix()}')").fetchone()[0]
        rows_sc = con.execute(f"SELECT COUNT(*) FROM read_parquet('{out_sc.as_posix()}')").fetchone()[0]
        print(f"gold ok all rows: {rows_all:,}")
        print(f"gold ok sc  rows: {rows_sc:,}")
        print("gold ok report-compatible schema ready")
    finally:
        con.close()
        shutil.rmtree(TEMP_NORMALIZED_DIR, ignore_errors=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build local gold parquets compatible with the Databricks report schema."
    )
    parser.add_argument("--start-year", type=int, default=None)
    parser.add_argument("--end-year", type=int, default=None)
    parser.add_argument("--out-all", type=Path, default=ALL_GOLD_PATH)
    parser.add_argument("--out-sc", type=Path, default=SC_GOLD_PATH)
    parser.add_argument("--incremental-merge", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_gold(
        out_all=args.out_all.resolve(),
        out_sc=args.out_sc.resolve(),
        start_year=args.start_year,
        end_year=args.end_year,
        incremental_merge=args.incremental_merge,
    )


if __name__ == "__main__":
    main()
