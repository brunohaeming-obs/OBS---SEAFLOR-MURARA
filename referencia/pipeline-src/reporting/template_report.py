from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from comex.project import DEFAULT_STATE_CODE, Project

MONTH_NAMES_PT = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}

MONTH_ABBR_PT = {
    1: "Jan",
    2: "Fev",
    3: "Mar",
    4: "Abr",
    5: "Mai",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Set",
    10: "Out",
    11: "Nov",
    12: "Dez",
}

PRODUCT_MONTHLY_FIRST_COLUMN = "Produtos Valor FOB US$"
COUNTRY_MONTHLY_FIRST_COLUMN = "Destinos Valor FOB US$"
PRODUCT_MAIN_COUNTERPART = "Principal destino dos produtos mais exportados por SC"
COUNTRY_MAIN_COUNTERPART = "Produto mais exportados por  país"

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


@dataclass(frozen=True)
class TemplateWorkbookData:
    sheet_frames: dict[str, pd.DataFrame]
    titles: dict[str, str]
    reference_year: int
    reference_month: int


def should_filter_state(state_code: str | None) -> bool:
    return bool(state_code and state_code.upper() != "ALL")


def missing_required_columns(columns: list[str] | tuple[str, ...]) -> list[str]:
    return [column for column in REQUIRED_GOLD_COLUMNS if column not in columns]


def prepare_gold_dataframe(dataframe: pd.DataFrame, state_code: str = DEFAULT_STATE_CODE) -> pd.DataFrame:
    gold_df = dataframe.copy()

    missing_columns = missing_required_columns(tuple(gold_df.columns))
    if missing_columns:
        raise RuntimeError(
            "Gold source file is missing required columns: " + ", ".join(sorted(missing_columns))
        )

    for column in NUMERIC_COLUMNS:
        if column in gold_df.columns:
            gold_df[column] = pd.to_numeric(gold_df[column], errors="coerce")

    if should_filter_state(state_code):
        gold_df = gold_df.loc[gold_df["sg_uf"] == state_code].copy()

    if gold_df.empty:
        raise RuntimeError(f"Gold source returned zero rows for state filter {state_code!r}.")

    return gold_df


def monthly_sheet_name(flow_kind: str, entity: str, month: int) -> str:
    return f"{flow_kind}_{entity}_{MONTH_ABBR_PT[month]}"


def ytd_sheet_name(flow_kind: str, entity: str, year: int) -> str:
    return f"{flow_kind}_{entity}_{year}"


def month_period_label(month: int, year: int) -> str:
    return f"{MONTH_NAMES_PT[month]}. {year}"


def ytd_period_label(month: int, year: int) -> str:
    return f"Jan-{MONTH_ABBR_PT[month]}. {year}"


def monthly_title(flow_label: str, entity_label: str, month: int, year: int) -> str:
    return f"{flow_label} - {entity_label} ({MONTH_NAMES_PT[month]}/{year})"


def ytd_title(flow_label: str, entity_label: str, month: int, year: int) -> str:
    return f"{flow_label} - {entity_label} (Jan-{MONTH_ABBR_PT[month]}/{year})"


def _safe_variation(current: float, previous: float) -> float | None:
    if previous is None or pd.isna(previous) or previous == 0:
        return None
    if current is None or pd.isna(current):
        return None
    return (current - previous) / previous


def _safe_price_variation(curr_value: float, curr_qty: float, prev_value: float, prev_qty: float) -> float | None:
    if any(pd.isna(value) for value in [curr_value, curr_qty, prev_value, prev_qty]):
        return None
    if curr_qty == 0 or prev_qty == 0 or prev_value == 0:
        return None

    previous_price = prev_value / prev_qty
    if previous_price == 0:
        return None
    current_price = curr_value / curr_qty
    return (current_price - previous_price) / previous_price


def _aggregate_period(
    gold_df: pd.DataFrame,
    *,
    flow_kind: str,
    period_year: int,
    period_months: list[int],
) -> pd.DataFrame:
    mask = (gold_df["tp_carga"] == flow_kind) & (gold_df["nr_ano"] == period_year) & (
        gold_df["nr_mes"].isin(period_months)
    )
    return gold_df.loc[mask].copy()


def _build_product_frame(
    current_df: pd.DataFrame,
    previous_df: pd.DataFrame,
    *,
    first_column_label: str,
    prev_value_label: str,
    curr_value_label: str,
    curr_qty_label: str,
    value_variation_label: str,
    qty_variation_label: str,
    price_variation_label: str,
    stat_variation_label: str,
    main_counterpart_label: str,
    top_n: int = 10,
) -> pd.DataFrame:
    ranking = (
        current_df.groupby(["cd_ncm", "ds_ncm"], dropna=False)[["vl_fob", "qt_kilo_liquido", "qt_estatistica"]]
        .sum()
        .reset_index()
        .sort_values(["vl_fob", "cd_ncm"], ascending=[False, True])
        .head(top_n)
        .reset_index(drop=True)
    )

    current_metrics = (
        current_df.groupby(["cd_ncm", "ds_ncm"], dropna=False)[["vl_fob", "qt_kilo_liquido", "qt_estatistica"]]
        .sum()
        .reset_index()
    )
    previous_metrics = (
        previous_df.groupby(["cd_ncm", "ds_ncm"], dropna=False)[["vl_fob", "qt_kilo_liquido", "qt_estatistica"]]
        .sum()
        .reset_index()
    )

    main_country = (
        current_df.groupby(["cd_ncm", "ds_ncm", "ds_pais"], dropna=False)[["vl_fob"]]
        .sum()
        .reset_index()
        .sort_values(["cd_ncm", "vl_fob", "ds_pais"], ascending=[True, False, True])
        .drop_duplicates(subset=["cd_ncm", "ds_ncm"], keep="first")
        .rename(columns={"ds_pais": main_counterpart_label})
        .drop(columns=["vl_fob"])
    )

    merged = ranking[["cd_ncm", "ds_ncm"]].merge(
        current_metrics.rename(
            columns={
                "vl_fob": curr_value_label,
                "qt_kilo_liquido": curr_qty_label,
                "qt_estatistica": "_curr_qt_estatistica",
            }
        ),
        on=["cd_ncm", "ds_ncm"],
        how="left",
    ).merge(
        previous_metrics.rename(
            columns={
                "vl_fob": prev_value_label,
                "qt_kilo_liquido": "_prev_qt_kilo_liquido",
                "qt_estatistica": "_prev_qt_estatistica",
            }
        ),
        on=["cd_ncm", "ds_ncm"],
        how="left",
    ).merge(main_country, on=["cd_ncm", "ds_ncm"], how="left")

    merged[value_variation_label] = merged.apply(
        lambda row: _safe_variation(row[curr_value_label], row[prev_value_label]), axis=1
    )
    merged[qty_variation_label] = merged.apply(
        lambda row: _safe_variation(row[curr_qty_label], row["_prev_qt_kilo_liquido"]), axis=1
    )
    merged[price_variation_label] = merged.apply(
        lambda row: _safe_price_variation(
            row[curr_value_label],
            row[curr_qty_label],
            row[prev_value_label],
            row["_prev_qt_kilo_liquido"],
        ),
        axis=1,
    )
    merged[stat_variation_label] = merged.apply(
        lambda row: _safe_variation(row["_curr_qt_estatistica"], row["_prev_qt_estatistica"]),
        axis=1,
    )

    merged = merged.rename(columns={"ds_ncm": first_column_label})
    ordered_columns = [
        first_column_label,
        prev_value_label,
        curr_value_label,
        curr_qty_label,
        value_variation_label,
        qty_variation_label,
        price_variation_label,
        stat_variation_label,
        main_counterpart_label,
    ]

    return merged[ordered_columns]


def _build_country_frame(
    current_df: pd.DataFrame,
    previous_df: pd.DataFrame,
    *,
    first_column_label: str,
    prev_value_label: str,
    curr_value_label: str,
    curr_qty_label: str,
    value_variation_label: str,
    qty_variation_label: str,
    price_variation_label: str,
    stat_variation_label: str,
    main_counterpart_label: str,
    top_n: int = 10,
) -> pd.DataFrame:
    ranking = (
        current_df.groupby(["cd_pais", "ds_pais"], dropna=False)[["vl_fob", "qt_kilo_liquido", "qt_estatistica"]]
        .sum()
        .reset_index()
        .sort_values(["vl_fob", "cd_pais"], ascending=[False, True])
        .head(top_n)
        .reset_index(drop=True)
    )

    current_metrics = (
        current_df.groupby(["cd_pais", "ds_pais"], dropna=False)[["vl_fob", "qt_kilo_liquido", "qt_estatistica"]]
        .sum()
        .reset_index()
    )
    previous_metrics = (
        previous_df.groupby(["cd_pais", "ds_pais"], dropna=False)[["vl_fob", "qt_kilo_liquido", "qt_estatistica"]]
        .sum()
        .reset_index()
    )

    main_product = (
        current_df.groupby(["cd_pais", "ds_pais", "ds_ncm"], dropna=False)[["vl_fob"]]
        .sum()
        .reset_index()
        .sort_values(["cd_pais", "vl_fob", "ds_ncm"], ascending=[True, False, True])
        .drop_duplicates(subset=["cd_pais", "ds_pais"], keep="first")
        .rename(columns={"ds_ncm": main_counterpart_label})
        .drop(columns=["vl_fob"])
    )

    merged = ranking[["cd_pais", "ds_pais"]].merge(
        current_metrics.rename(
            columns={
                "vl_fob": curr_value_label,
                "qt_kilo_liquido": curr_qty_label,
                "qt_estatistica": "_curr_qt_estatistica",
            }
        ),
        on=["cd_pais", "ds_pais"],
        how="left",
    ).merge(
        previous_metrics.rename(
            columns={
                "vl_fob": prev_value_label,
                "qt_kilo_liquido": "_prev_qt_kilo_liquido",
                "qt_estatistica": "_prev_qt_estatistica",
            }
        ),
        on=["cd_pais", "ds_pais"],
        how="left",
    ).merge(main_product, on=["cd_pais", "ds_pais"], how="left")

    merged[value_variation_label] = merged.apply(
        lambda row: _safe_variation(row[curr_value_label], row[prev_value_label]), axis=1
    )
    merged[qty_variation_label] = merged.apply(
        lambda row: _safe_variation(row[curr_qty_label], row["_prev_qt_kilo_liquido"]), axis=1
    )
    merged[price_variation_label] = merged.apply(
        lambda row: _safe_price_variation(
            row[curr_value_label],
            row[curr_qty_label],
            row[prev_value_label],
            row["_prev_qt_kilo_liquido"],
        ),
        axis=1,
    )
    merged[stat_variation_label] = merged.apply(
        lambda row: _safe_variation(row["_curr_qt_estatistica"], row["_prev_qt_estatistica"]),
        axis=1,
    )

    merged = merged.rename(columns={"ds_pais": first_column_label})
    ordered_columns = [
        first_column_label,
        prev_value_label,
        curr_value_label,
        curr_qty_label,
        value_variation_label,
        qty_variation_label,
        price_variation_label,
        stat_variation_label,
        main_counterpart_label,
    ]

    return merged[ordered_columns]


def _report_frame(
    gold_df: pd.DataFrame,
    *,
    flow_kind: str,
    current_year: int,
    current_months: list[int],
    previous_year: int,
    previous_months: list[int],
    by: str,
) -> pd.DataFrame:
    current_df = _aggregate_period(
        gold_df, flow_kind=flow_kind, period_year=current_year, period_months=current_months
    )
    previous_df = _aggregate_period(
        gold_df, flow_kind=flow_kind, period_year=previous_year, period_months=previous_months
    )

    current_label = month_period_label(current_months[-1], current_year) if len(current_months) == 1 else ytd_period_label(current_months[-1], current_year)
    previous_label = month_period_label(previous_months[-1], previous_year) if len(previous_months) == 1 else ytd_period_label(previous_months[-1], previous_year)

    if len(current_months) == 1:
        value_variation_label = "Variação do valor(US$) em relação ao mesmo mês do ano anterior(em %)"
        qty_variation_label = "Variação de Quantidade Exportada - Quilograma Líquido em relação ao mesmo mês do ano anterior(em %)"
    else:
        value_variation_label = "Variação do valor(US$) em relação ao mesmo período do ano anterior(em %)"
        qty_variation_label = "Variação de Quantidade Exportada - Quilograma Líquido em relação ao mesmo período do ano anterior(em %)"

    if by == "product":
        return _build_product_frame(
            current_df,
            previous_df,
            first_column_label=PRODUCT_MONTHLY_FIRST_COLUMN,
            prev_value_label=f"{previous_label}( em US$ FOB)",
            curr_value_label=f"{current_label}( em US$ FOB)",
            curr_qty_label=f"Quilograma Líquido \n{current_label}",
            value_variation_label=value_variation_label,
            qty_variation_label=qty_variation_label,
            price_variation_label="Variação do Preço Médio",
            stat_variation_label="Variação da Quantidade Estatística",
            main_counterpart_label=PRODUCT_MAIN_COUNTERPART,
        )

    return _build_country_frame(
        current_df,
        previous_df,
        first_column_label=COUNTRY_MONTHLY_FIRST_COLUMN,
        prev_value_label=f"{previous_label}( em US$ FOB)",
        curr_value_label=f"{current_label}( em US$ FOB)",
        curr_qty_label=f"Quilograma Líquido \n{current_label}",
        value_variation_label=value_variation_label,
        qty_variation_label=qty_variation_label,
        price_variation_label="Variação do Preço Médio",
        stat_variation_label="Variação da Quantidade Estatística",
        main_counterpart_label=COUNTRY_MAIN_COUNTERPART,
    )


def build_template_workbook_data(
    project: Project,
    gold_df: pd.DataFrame,
) -> TemplateWorkbookData:
    prepared = prepare_gold_dataframe(gold_df, project.state_code)
    reference_competencia = int(prepared["nr_competencia"].max())
    reference_year = reference_competencia // 100
    reference_month = reference_competencia % 100

    monthly_sheets = {
        monthly_sheet_name("Exp", "Prod", reference_month): (
            monthly_title("Exportações", "Produto", reference_month, reference_year),
            _report_frame(
                prepared,
                flow_kind="EXP",
                current_year=reference_year,
                current_months=[reference_month],
                previous_year=reference_year - 1,
                previous_months=[reference_month],
                by="product",
            ),
        ),
        monthly_sheet_name("Exp", "País", reference_month): (
            monthly_title("Exportações", "País", reference_month, reference_year),
            _report_frame(
                prepared,
                flow_kind="EXP",
                current_year=reference_year,
                current_months=[reference_month],
                previous_year=reference_year - 1,
                previous_months=[reference_month],
                by="country",
            ),
        ),
        monthly_sheet_name("Imp", "Prod", reference_month): (
            monthly_title("Importações", "Produto", reference_month, reference_year),
            _report_frame(
                prepared,
                flow_kind="IMP",
                current_year=reference_year,
                current_months=[reference_month],
                previous_year=reference_year - 1,
                previous_months=[reference_month],
                by="product",
            ),
        ),
        monthly_sheet_name("Imp", "País", reference_month): (
            monthly_title("Importações", "País", reference_month, reference_year),
            _report_frame(
                prepared,
                flow_kind="IMP",
                current_year=reference_year,
                current_months=[reference_month],
                previous_year=reference_year - 1,
                previous_months=[reference_month],
                by="country",
            ),
        ),
    }

    ytd_months = list(range(1, reference_month + 1))
    ytd_sheets = {
        ytd_sheet_name("Exp", "Prod", reference_year): (
            ytd_title("Exportações", "Produto", reference_month, reference_year),
            _report_frame(
                prepared,
                flow_kind="EXP",
                current_year=reference_year,
                current_months=ytd_months,
                previous_year=reference_year - 1,
                previous_months=ytd_months,
                by="product",
            ),
        ),
        ytd_sheet_name("Exp", "País", reference_year): (
            ytd_title("Exportações", "País", reference_month, reference_year),
            _report_frame(
                prepared,
                flow_kind="EXP",
                current_year=reference_year,
                current_months=ytd_months,
                previous_year=reference_year - 1,
                previous_months=ytd_months,
                by="country",
            ),
        ),
        ytd_sheet_name("Imp", "Prod", reference_year): (
            ytd_title("Importações", "Produto", reference_month, reference_year),
            _report_frame(
                prepared,
                flow_kind="IMP",
                current_year=reference_year,
                current_months=ytd_months,
                previous_year=reference_year - 1,
                previous_months=ytd_months,
                by="product",
            ),
        ),
        ytd_sheet_name("Imp", "País", reference_year): (
            ytd_title("Importações", "País", reference_month, reference_year),
            _report_frame(
                prepared,
                flow_kind="IMP",
                current_year=reference_year,
                current_months=ytd_months,
                previous_year=reference_year - 1,
                previous_months=ytd_months,
                by="country",
            ),
        ),
    }

    ordered_names = [
        monthly_sheet_name("Exp", "Prod", reference_month),
        monthly_sheet_name("Exp", "País", reference_month),
        monthly_sheet_name("Imp", "Prod", reference_month),
        monthly_sheet_name("Imp", "País", reference_month),
        ytd_sheet_name("Exp", "Prod", reference_year),
        ytd_sheet_name("Exp", "País", reference_year),
        ytd_sheet_name("Imp", "Prod", reference_year),
        ytd_sheet_name("Imp", "País", reference_year),
    ]

    combined = {**monthly_sheets, **ytd_sheets}
    sheet_frames = {name: combined[name][1] for name in ordered_names}
    titles = {name: combined[name][0] for name in ordered_names}
    return TemplateWorkbookData(
        sheet_frames=sheet_frames,
        titles=titles,
        reference_year=reference_year,
        reference_month=reference_month,
    )


def default_template_output_path(gold_file: Path, state_code: str) -> Path:
    suffix = state_code.lower() if should_filter_state(state_code) else "all"
    return gold_file.with_name(f"{gold_file.stem}_template_report_{suffix}.xlsx")
