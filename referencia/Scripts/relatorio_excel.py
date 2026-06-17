from pathlib import Path
import pandas as pd
from datetime import datetime, date
from paths import DADOS, GOLD_DIR, MARTS_DIR, gold_glob_for, gold_single_path  # import from above

# ---- NEW helpers for dynamic discovery & safe sheet names ----
import re

_INVALID_XLSX_CHARS = r'[\[\]\:\*\?\/\\]'

# ---------- helpers ----------

def _is_var_col(name: str) -> bool:
    n = str(name).lower()
    return n.startswith("yoy_") or ("variação" in n) or ("variacao" in n)

def _is_numbery_column_name(col: str) -> bool:
    """Heuristic: columns that should be numeric even if read as object/Decimal."""
    c = str(col).strip().lower()
    # dynamic headers created in the reports
    if c.endswith("(em us$ fob)") or c.endswith("(em quilogramas líquidos)"):
        return True
    # common fixed metric columns
    number_cols = {
        "vl_fob_sum_last12m","vl_fob_12m","vl_fob_curr","vl_fob_prev","vl_fob",
        "kg_liquido","kg_curr","kg_prev",
        "qt_estat","qt_curr","qt_prev",
        "main_dest_vl_fob_last12m","main_prod_vl_fob_last12m",
        "rank_12m",  # optional: include if you want coloring on ranks
    }
    return c in number_cols

def _load_parquet(p: Path) -> pd.DataFrame:
    df = pd.read_parquet(p)

    # Dates
    if "ref_month" in df.columns:
        df["ref_month"] = pd.to_datetime(df["ref_month"], errors="coerce")

    # Explicit: variation/YoY columns -> float
    for c in df.columns:
        if _is_var_col(c):
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Heuristic: coerce numeric-like columns (handles Decimal/object/string)
    for c in df.columns:
        if _is_numbery_column_name(c):
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Fallback: if still nothing is numeric (all object/strings), try a safe sniff:
    if not any(pd.api.types.is_numeric_dtype(df[d]) for d in df.columns):
        for c in df.columns:
            if df[c].dtype == "object":
                probe = pd.to_numeric(df[c], errors="coerce")
                # adopt if at least 80% of non-nulls convert
                non_null = probe.notna().sum()
                total    = (~df[c].isna()).sum()
                if total > 0 and (non_null / total) >= 0.8:
                    df[c] = probe

    return df

def _autowidth(ws, df, wb, start_col=0, extra_pad=2, max_width=35):
    # Slight cap on width so headers actually wrap
    for i, col in enumerate(df.columns):
        max_len = max(len(str(col)), *(len(str(x)) for x in df[col].head(500)))
        ws.set_column(start_col + i, start_col + i, min(max_len + extra_pad, max_width))

def _apply_content_base(ws, df, wb, start_col=0):
    # Base content font for the whole table (overridden later per-type)
    fmt_content = wb.add_format({"font_name": "Aptos Narrow", "font_size": 11})
    ws.set_column(start_col, start_col + len(df.columns) - 1, None, fmt_content)

def _apply_number_formats(ws, df, wb, header_row, start_col=0):
    """
    Make all numeric columns integers (#,##0), except variação/yoy columns (percent).
    Dates keep yyyy-mm. Uses Aptos Narrow 11 everywhere.
    """
    import pandas as pd

    common = {"font_name": "Aptos Narrow", "font_size": 11}
    fmt_int  = wb.add_format({**common, "num_format": "#,##0"})   # integers
    fmt_pct  = wb.add_format({**common, "num_format": "0.0%"})    # percents
    fmt_date = wb.add_format({**common, "num_format": "yyyy-mm"})

    # detect columns
    pct_cols  = [c for c in df.columns if _is_var_col(c)]  # variação/yoy
    date_cols = [c for c in df.columns if c == "ref_month"]

    # numeric columns by dtype
    numeric_cols = list(df.select_dtypes(include="number").columns)

    # integers for numeric columns EXCEPT percent + date index columns
    int_cols = [c for c in numeric_cols if c not in pct_cols]

    # apply formats
    idx = {c: i for i, c in enumerate(df.columns)}

    for c in int_cols:
        j = idx.get(c, None)
        if j is not None:
            ws.set_column(start_col + j, start_col + j, None, fmt_int)

    for c in pct_cols:
        j = idx.get(c, None)
        if j is not None:
            ws.set_column(start_col + j, start_col + j, None, fmt_pct)

    for c in date_cols:
        j = idx.get(c, None)
        if j is not None:
            ws.set_column(start_col + j, start_col + j, 12, fmt_date)


def _style_headers(ws, df, wb, header_row, start_col=0):
    # Two header styles; wrap text; correct fonts/sizes
    hdr_main = wb.add_format({
        "font_name": "Aptos Narrow", "font_size": 12, "bold": True,
        "font_color": "white", "bg_color": "#0E2841", "border": 1,
        "text_wrap": True, "align": "center", "valign": "vcenter"
    })
    hdr_var  = wb.add_format({
        "font_name": "Aptos Narrow", "font_size": 12, "bold": True,
        "font_color": "white", "bg_color": "#215C98", "border": 1,
        "text_wrap": True, "align": "center", "valign": "vcenter"
    })
    # Give the header row some height to breathe for wrapping
    ws.set_row(header_row, 36)
    # Write each header with the right color
    for j, name in enumerate(df.columns):
        fmt = hdr_var if _is_var_col(name) else hdr_main
        ws.write(header_row, start_col + j, name, fmt)

def _apply_conditional_formats(ws, df, wb, data_first_row, data_last_row, start_col=0):
    """
    Apply conditional colors ONLY to 'Variação' columns (yoy_* or names containing 'Variação').
    Green fill+font for > 0, red fill+font for < 0. No zebra banding here.
    """
    if data_last_row < data_first_row:
        return

    # target only variation columns
    var_cols = [c for c in df.columns if _is_var_col(c)]
    if not var_cols:
        return

    fmt_green = wb.add_format({
        "font_name": "Aptos Narrow", "font_size": 11,
        "bg_color": "#C6EFCE", "font_color": "#006100"
    })
    fmt_red = wb.add_format({
        "font_name": "Aptos Narrow", "font_size": 11,
        "bg_color": "#FFC7CE", "font_color": "#9C0006"
    })

    for col in var_cols:
        j = start_col + df.columns.get_loc(col)
        # > 0 => green
        ws.conditional_format(data_first_row, j, data_last_row, j, {
            "type": "cell", "criteria": ">", "value": 0, "format": fmt_green
        })
        # < 0 => red
        ws.conditional_format(data_first_row, j, data_last_row, j, {
            "type": "cell", "criteria": "<", "value": 0, "format": fmt_red
        })

def _write_title(ws, title_text, wb, n_cols, start_col=0, row=0):
    title_fmt = wb.add_format({"bold": True, "font_size": 22, "font_name": "Aptos Narrow",
                               "font_color": "#0E2841", "valign": "vcenter"})
    ws.merge_range(row, start_col, row, start_col + n_cols - 1, title_text, title_fmt)


def _pretty_sheet_name_from_path(p: Path) -> str:
    """Derive a readable sheet name from a parquet path."""
    stem = p.stem  # e.g., mart_EXP_top_products_report_202509
    # drop trailing _YYYYMM if present
    stem = re.sub(r'_(20\d{2})(0[1-9]|1[0-2])$', '', stem)
    # drop common prefixes/suffixes
    stem = re.sub(r'^mart[_\-]+', '', stem, flags=re.IGNORECASE)
    stem = re.sub(r'[_\-]+report$', '', stem, flags=re.IGNORECASE)
    # normalize tokens
    tokens = stem.replace('__','_').split('_')
    pretty = ' '.join(t.capitalize() for t in tokens if t)
    pretty = re.sub(r'\bExp\b', 'EXP', pretty)
    pretty = re.sub(r'\bImp\b', 'IMP', pretty)
    # remove invalid chars and trim length to Excel's 31-char limit
    pretty = re.sub(_INVALID_XLSX_CHARS, ' ', pretty).strip()
    return pretty[:31] or p.stem[:31]

def _dedupe_sheet_name(name: str, used: dict[str,int]) -> str:
    """Ensure sheet names are unique (Excel requirement)."""
    if name not in used:
        used[name] = 1
        return name
    used[name] += 1
    # append (2), (3), ... within 31-char limit
    suffix = f" ({used[name]})"
    base = name[: max(0, 31 - len(suffix))].rstrip()
    return f"{base}{suffix}"

# # ---------- UPDATED main exporter (auto-discovers all .parquet) ----------
# def create_excel_report(
#     marts_dir: Path = MARTS_DIR,
#     out_path: Path = MARTS_DIR / "comex_datamarts.xlsx",
#     include_charts: bool = False,              # not used here, kept for API stability
#     recursive: bool = False,                   # set True to include subfolders
#     limit_rows_per_sheet: int | None = None,   # optionally cap very large sheets
# ):
#     # 1) discover parquet files
#     paths = sorted(
#         (marts_dir.rglob("*.parquet") if recursive else marts_dir.glob("*.parquet")),
#         key=lambda p: p.name.lower()
#     )
#     if not paths:
#         raise FileNotFoundError(f"No .parquet files found in {marts_dir}")

#     # 2) load them all
#     items: list[tuple[str, pd.DataFrame, Path]] = []
#     for p in paths:
#         try:
#             df = _load_parquet(p)
#         except Exception as e:
#             # skip unreadable file but keep going
#             print(f"[warn] Skipping {p.name}: {e}")
#             continue
#         sheet = _pretty_sheet_name_from_path(p)
#         items.append((sheet, df, p))

#     if not items:
#         raise RuntimeError("No readable Parquet files to include.")

#     # 3) compute a global ref_month (first file that has it)
#     ref_month = None
#     for _, df, _ in items:
#         if "ref_month" in df.columns and not df["ref_month"].isna().all():
#             ref_month = pd.to_datetime(df["ref_month"].max()).date()
#             break

#     # 4) write Excel
#     with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
#         wb = writer.book

#         # Cover
#         cover = pd.DataFrame({
#             "Item": ["Generated at", "Reference month", "Marts included"],
#             "Value": [
#                 datetime.now().strftime("%Y-%m-%d %H:%M"),
#                 str(ref_month) if ref_month else "—",
#                 ", ".join(sorted({p.name for _,_,p in items}))
#             ]
#         })
#         cover.to_excel(writer, sheet_name="Cover", index=False)
#         ws_cover = writer.sheets["Cover"]
#         _autowidth(ws_cover, cover, wb)
#         cover_fmt = wb.add_format({"font_name": "Aptos Narrow", "font_size": 11})
#         ws_cover.set_column(0, cover.shape[1]-1, None, cover_fmt)
#         ws_cover.freeze_panes(1, 0)
#         ws_cover.autofilter(0, 0, cover.shape[0], cover.shape[1]-1)

#         # Data sheets
#         used_names: dict[str,int] = {}
#         for sheet_name, df, p in items:
#             # unique & safe sheet name
#             safe_name = _dedupe_sheet_name(sheet_name, used_names)

#             # optional row cap (Excel limit 1,048,576 rows anyway)
#             df_out = df if not limit_rows_per_sheet else df.head(limit_rows_per_sheet).copy()

#             # Optional: reorder common keys first
#             preferred_first = [c for c in [
#                 "rank_12m","produto","ncm8","co_ncm","no_pais","co_pais",
#                 "main_produto","main_no_pais","main_co_pais","vl_fob_sum_last12m"
#             ] if c in df_out.columns]
#             other_cols = [c for c in df_out.columns if c not in preferred_first]
#             if preferred_first:
#                 df_out = df_out[preferred_first + other_cols]

#             # Write table (title row 0, header row 1)
#             startrow = 1
#             df_out.to_excel(writer, sheet_name=safe_name, index=False, startrow=startrow)
#             ws = writer.sheets[safe_name]

#             # Title (use pretty name; include original file name in smaller note if you want)
#             _write_title(ws, sheet_name, wb, n_cols=df_out.shape[1], start_col=0, row=0)

#             # Styling & formats
#             _apply_content_base(ws, df_out, wb, start_col=0)
#             _style_headers(ws, df_out, wb, header_row=startrow, start_col=0)
#             _autowidth(ws, df_out, wb, start_col=0, max_width=35)
#             _apply_number_formats(ws, df_out, wb, header_row=startrow, start_col=0)

#             # Conditional formats for "variação"/YoY columns
#             data_first_row = startrow + 1
#             data_last_row  = startrow + len(df_out)
#             _apply_conditional_formats(ws, df_out, wb, data_first_row, data_last_row, start_col=0)

#             ws.freeze_panes(startrow + 1, 0)
#             ws.autofilter(startrow, 0, startrow + df_out.shape[0], df_out.shape[1]-1)

#     print(f"Excel report ✔  {out_path}")


def create_excel_report(
    marts_dir: Path = MARTS_DIR,                 # root, e.g. Dados/marts
    ref_year: int | None = None,
    ref_month: int | None = None,
    out_path: Path | None = None,
    include_charts: bool = False,                # kept for API stability
    recursive: bool = True,                      # search subfolders under YYYY/MM
    limit_rows_per_sheet: int | None = None,
):
    # ---- resolve target folder YYYY/MM ----
    y, m = ref_year, ref_month
    if y is None or m is None:
        # autodetect latest YYYY/MM under marts_dir
        years = sorted([int(p.name) for p in marts_dir.iterdir() if p.is_dir() and re.fullmatch(r"\d{4}", p.name)])
        if not years:
            raise FileNotFoundError(f"No year folders under {marts_dir}")
        y = years[-1]
        months_dir = marts_dir / f"{y:04d}"
        months = sorted([int(p.name) for p in months_dir.iterdir() if p.is_dir() and re.fullmatch(r"\d{2}", p.name)])
        if not months:
            raise FileNotFoundError(f"No month folders under {months_dir}")
        m = months[-1]

    target_dir = marts_dir / f"{y:04d}" / f"{m:02d}"
    if not target_dir.exists():
        raise FileNotFoundError(f"Target marts folder not found: {target_dir}")

    # default output path: reports/comex_datamarts_YYYYMM.xlsx
    if out_path is None:
        out_path = MARTS_DIR / f"comex_datamarts_{y:04d}{m:02d}.xlsx"

    # ---- discover parquet files in the target folder ----
    paths = sorted(
        (target_dir.rglob("*.parquet") if recursive else target_dir.glob("*.parquet")),
        key=lambda p: p.name.lower()
    )
    if not paths:
        raise FileNotFoundError(f"No .parquet files found in {target_dir} (recursive={recursive})")

    # ---- load them all ----
    items: list[tuple[str, pd.DataFrame, Path]] = []
    for p in paths:
        try:
            df = _load_parquet(p)
        except Exception as e:
            print(f"[warn] Skipping {p.name}: {e}")
            continue
        sheet = _pretty_sheet_name_from_path(p)
        items.append((sheet, df, p))
    if not items:
        raise RuntimeError("No readable Parquet files to include.")

    # ---- compute reference date for cover ----
    ref_dt = None
    for _, df, _ in items:
        if "ref_month" in df.columns and not df["ref_month"].isna().all():
            ref_dt = pd.to_datetime(df["ref_month"].max()).date()
            break
    ref_dt = ref_dt or date(y, m, 1)

    # ---- write Excel ----
    with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
        wb = writer.book

        cover = pd.DataFrame({
            "Item": ["Generated at", "Reference month", "Target folder", "Marts included"],
            "Value": [
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                str(ref_dt),
                str(target_dir),
                ", ".join(sorted({p.name for _,_,p in items}))
            ]
        })
        cover.to_excel(writer, sheet_name="Cover", index=False)
        ws_cover = writer.sheets["Cover"]
        _autowidth(ws_cover, cover, wb)
        cover_fmt = wb.add_format({"font_name": "Aptos Narrow", "font_size": 11})
        ws_cover.set_column(0, cover.shape[1]-1, None, cover_fmt)
        ws_cover.freeze_panes(1, 0)
        ws_cover.autofilter(0, 0, cover.shape[0], cover.shape[1]-1)

        used_names: dict[str,int] = {}
        for sheet_name, df, p in items:
            safe_name = _dedupe_sheet_name(sheet_name, used_names)
            df_out = df if not limit_rows_per_sheet else df.head(limit_rows_per_sheet).copy()

            preferred_first = [c for c in [
                "rank_12m","produto","ncm8","co_ncm","no_pais","co_pais",
                "main_produto","main_no_pais","main_co_pais","vl_fob_sum_last12m"
            ] if c in df_out.columns]
            other_cols = [c for c in df_out.columns if c not in preferred_first]
            if preferred_first:
                df_out = df_out[preferred_first + other_cols]

            startrow = 1
            df_out.to_excel(writer, sheet_name=safe_name, index=False, startrow=startrow)
            ws = writer.sheets[safe_name]

            _write_title(ws, sheet_name, wb, n_cols=df_out.shape[1], start_col=0, row=0)
            _apply_content_base(ws, df_out, wb, start_col=0)
            _style_headers(ws, df_out, wb, header_row=startrow, start_col=0)
            _autowidth(ws, df_out, wb, start_col=0, max_width=35)
            _apply_number_formats(ws, df_out, wb, header_row=startrow, start_col=0)

            data_first_row = startrow + 1
            data_last_row  = startrow + len(df_out)
            _apply_conditional_formats(ws, df_out, wb, data_first_row, data_last_row, start_col=0)

            ws.freeze_panes(startrow + 1, 0)
            ws.autofilter(startrow, 0, startrow + df_out.shape[0], df_out.shape[1]-1)

    print(f"Excel report ✔  {out_path}")


create_excel_report(marts_dir=MARTS_DIR,
                    recursive=False)