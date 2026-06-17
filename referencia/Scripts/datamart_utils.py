from pathlib import Path
import duckdb
from paths import DADOS, GOLD_DIR, MARTS_DIR, gold_glob_for, gold_single_path  # import from above

def slug_ascii(s: str | None) -> str:
    if not s: return "all"
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^\w]+", "_", s).strip("_")[:80] or "all"

def mart_out_path(
    marts_dir: Path,
    flow_kind: str,
    year,
    month,
    label: str,
    tag: str | None = None,
) -> Path:
    y = int(year)
    m = int(month)
    out_dir = marts_dir / f"{y:04d}" / f"{m:02d}"
    out_dir.mkdir(parents=True, exist_ok=True)

    file_label = slug_ascii(label)
    tag_slug   = slug_ascii(tag)

    # omit the tag segment when empty
    tag_part = f"_{tag_slug}" if tag_slug else ""

    fname = f"mart_{flow_kind}_{file_label}{tag_part}_{y:04d}{m:02d}.parquet"
    return (out_dir / fname).resolve()

def build_mart_top_products_report(
    ref_year: int | None = None,
    ref_month: int | None = None,
    kind: str = "EXP",
):
    flow_kind = (kind or "EXP").upper()
    if flow_kind not in ("EXP", "IMP"):
        raise ValueError("kind must be 'EXP' or 'IMP'")

    con = duckdb.connect()
    #gold_glob = f"{GOLD_DIR.as_posix()}/kind={flow_kind}/year=*/*.parquet"
    gold_glob = gold_single_path()
    # Detect latest month if not provided
    if ref_year is None or ref_month is None:
        d_curr = con.execute(f"""
            SELECT MAX(MAKE_DATE(CAST(year AS INTEGER), CAST(co_mes AS INTEGER), 1))
            FROM read_parquet('{gold_glob}', union_by_name=true)
        """).fetchone()[0]
        if d_curr is None:
            con.close()
            raise RuntimeError("No data found in Gold to determine reference month.")
        ref_year, ref_month = d_curr.year, d_curr.month

    # Portuguese month label helpers
    meses_pt = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
    mes_nome = meses_pt[ref_month - 1]
    prev_label_val = f"{mes_nome} {ref_year-1} (em US$ FOB)"
    curr_label_val = f"{mes_nome} {ref_year} (em US$ FOB)"
    curr_label_kg  = f"{mes_nome} {ref_year} (em quilogramas líquidos)"

    def ident(s: str) -> str:
        return '"' + s.replace('"', '""') + '"'

    final_sql = f"""
    WITH base AS (
      SELECT
        kind,
        CAST(year AS INTEGER)     AS yr,
        CAST(co_mes AS INTEGER)   AS mo,
        co_ncm,
        ncm8,
        co_pais,
        -- Use dimension name when present
        CAST(nm_pais_dim AS VARCHAR) AS pais_nome,
        produto,
        UPPER(TRIM(produto))      AS produto_norm,
        TRIM(produto)             AS produto_clean,
        sc_competitiva,
        cnae_divisao,
        CAST(vl_fob     AS DECIMAL(20,4)) AS vl_fob,
        CAST(kg_liquido AS DECIMAL(20,6)) AS kg_liquido,
        CAST(qt_estat   AS DECIMAL(20,6)) AS qt_estat,
        MAKE_DATE(CAST(year AS INTEGER), CAST(co_mes AS INTEGER), 1) AS d
      FROM read_parquet('{gold_glob}', union_by_name=true)
      WHERE (vl_fob IS NULL OR vl_fob >= 0)
        AND (kg_liquido IS NULL OR kg_liquido >= 0)
    ),
    latest AS (
      SELECT MAKE_DATE({int(ref_year)}, {int(ref_month)}, 1) AS d_max
    ),
    win_12m AS (
      SELECT
        b.*,
        DATE_TRUNC('month', l.d_max)                     AS dmax_m,
        DATE_TRUNC('month', l.d_max) - INTERVAL 11 MONTH AS dmin_m
      FROM base b CROSS JOIN latest l
    ),
    in_12m AS (
      SELECT * FROM win_12m
      WHERE d BETWEEN dmin_m AND dmax_m
    ),
    month_scope AS (
      SELECT
        DATE_TRUNC('month', d_max)                    AS d_curr,
        DATE_TRUNC('month', d_max) - INTERVAL 1 YEAR  AS d_prev
      FROM latest
    ),
    flow_12m AS (
      SELECT * FROM in_12m
      WHERE kind = '{flow_kind}' AND produto_norm IS NOT NULL AND produto_norm <> ''
    ),
    -- Rank Top-20 products by 12m value
    prod_rank AS (
      SELECT
        produto_norm,
        MIN(produto_clean) AS produto_display,
        SUM(vl_fob)        AS vl_fob_12m
      FROM flow_12m
      GROUP BY 1
    ),
    top20_prod AS (
      SELECT *
      FROM (
        SELECT *,
               ROW_NUMBER() OVER (ORDER BY vl_fob_12m DESC, produto_norm) AS rn
        FROM prod_rank
      ) WHERE rn <= 20
    ),
    -- Main destination per product (sum by product & country, then rank per product)
    main_dest AS (
      SELECT
        b.produto_norm,
        b.co_pais,
        MIN(b.pais_nome) AS pais_nome,            -- display label for that country code
        SUM(b.vl_fob)    AS vl_fob_dest_curr,
        ROW_NUMBER() OVER (
          PARTITION BY b.produto_norm
          ORDER BY SUM(b.vl_fob) DESC, b.co_pais
        ) AS rnk
      FROM base b
      JOIN month_scope m
        ON b.d = m.d_curr                          -- << only the selected month
      JOIN top20_prod t
        ON UPPER(TRIM(b.produto)) = t.produto_norm -- limit to the ranked products
      WHERE b.kind = '{flow_kind}'
      GROUP BY b.produto_norm, b.co_pais
    ),
    main_dest_pick AS (
      SELECT
        produto_norm,
        pais_nome AS principal_destino
      FROM main_dest
      WHERE rnk = 1
    ),
    -- Current vs previous same month (YoY) metrics by product
    curr_m AS (
      SELECT
        UPPER(TRIM(b.produto)) AS produto_norm,
        SUM(b.vl_fob)          AS vl_fob_curr,
        SUM(b.kg_liquido)      AS kg_curr,
        SUM(b.qt_estat)        AS qt_curr
      FROM base b
      JOIN month_scope m ON b.d = m.d_curr
      WHERE b.kind = '{flow_kind}' AND b.produto IS NOT NULL AND TRIM(b.produto) <> ''
      GROUP BY 1
    ),
    prev_m AS (
      SELECT
        UPPER(TRIM(b.produto)) AS produto_norm,
        SUM(b.vl_fob)          AS vl_fob_prev,
        SUM(b.kg_liquido)      AS kg_prev,
        SUM(b.qt_estat)        AS qt_prev
      FROM base b
      JOIN month_scope m ON b.d = m.d_prev
      WHERE b.kind = '{flow_kind}' AND b.produto IS NOT NULL AND TRIM(b.produto) <> ''
      GROUP BY 1
    )
    SELECT
      t.produto_display                                        AS {ident('Produtos Valor FOB US$')},
      COALESCE( CAST(p.vl_fob_prev AS DECIMAL(20,2)), 0 )      AS {ident(prev_label_val)},
      COALESCE( CAST(c.vl_fob_curr AS DECIMAL(20,2)), 0 )      AS {ident(curr_label_val)},
      COALESCE( CAST(c.kg_curr     AS DECIMAL(20,3)), 0 )      AS {ident(curr_label_kg)},
      CASE
        WHEN p.vl_fob_prev IS NULL OR p.vl_fob_prev = 0 THEN NULL
        ELSE (c.vl_fob_curr - p.vl_fob_prev) / p.vl_fob_prev
      END                                                     AS {ident('Variação do valor(US$) em relação ao mesmo mês do ano anterior(em %)')},
      CASE
        WHEN p.kg_prev IS NULL OR p.kg_prev = 0 THEN NULL
        ELSE (c.kg_curr - p.kg_prev) / p.kg_prev
      END                                                     AS {ident('Variação de Quantidade Exportada - Quilograma Líquido (em %)')},
      CASE
        WHEN (p.kg_prev IS NULL OR p.kg_prev = 0) THEN NULL
        WHEN (c.kg_curr IS NULL OR c.kg_curr = 0) THEN NULL
        ELSE
          ((c.vl_fob_curr / NULLIF(c.kg_curr, 0)) - (p.vl_fob_prev / NULLIF(p.kg_prev, 0)))
          / NULLIF((p.vl_fob_prev / NULLIF(p.kg_prev, 0)), 0)
      END                                                     AS {ident('Variação do Preço Médio')},
      CASE
        WHEN p.qt_prev IS NULL OR p.qt_prev = 0 THEN NULL
        ELSE (c.qt_curr - p.qt_prev) / p.qt_prev
      END                                                     AS {ident('Variação da Quantidade Estatística')},
      md.principal_destino                                    AS {ident('Principal destino dos produtos mais exportados por SC')}
    FROM top20_prod t
    LEFT JOIN main_dest_pick md ON md.produto_norm = t.produto_norm
    LEFT JOIN curr_m c          ON c.produto_norm  = t.produto_norm
    LEFT JOIN prev_m p          ON p.produto_norm  = t.produto_norm
    ORDER BY t.rn
    """

    #out_path = MARTS_DIR / f"{ref_year}" / f"{ref_month}" / f"mart_{flow_kind}_produtos_report_{ref_year:04d}{ref_month:02d}.parquet"
    #out_path = MARTS_DIR  / f"mart_{flow_kind}_produtos_report_{ref_year:04d}{ref_month:02d}.parquet"
    out_path = mart_out_path(MARTS_DIR, flow_kind, ref_year, ref_month, label="produtos")


    con.execute(f"""
      COPY ({final_sql})
      TO '{out_path.as_posix()}'
      (FORMAT PARQUET, OVERWRITE_OR_IGNORE 1)
    """)

    # quick peek
    con.close()
    print(f"mart ✔ {out_path}")


def build_mart_exp_top_destinations_report(
    ref_year: int | None = None,
    ref_month: int | None = None,
    kind: str = "EXP",
):
    """
    Produces a Top-20 destinations report (for EXP/IMP; default EXP) with columns:
      1) 'Destinos Valor FOB US$'                                  -- destination name
      2) '<Mês YYYY-1> (em US$ FOB)'                               -- prev year same month value
      3) '<Mês YYYY> (em US$ FOB)'                                 -- current month value
      4) '<Mês YYYY> (em quilogramas líquidos)'                    -- current month kg
      5) 'Variação do valor(US$) em relação ao mesmo mês do ano anterior(em %)'
      6) 'Variação de Quantidade Exportada - Quilograma Líquido (em %)'
      7) 'Variação do Preço Médio'
      8) 'Variação da Quantidade Estatística'
      9) 'Produto mais exportado para o destino'                   -- top product in last 12m
    Ranking basis: sum(vl_fob) over the last 12 months ending at the reference month.
    """

    flow_kind = (kind or "EXP").upper()
    if flow_kind not in ("EXP", "IMP"):
        raise ValueError("kind must be 'EXP' or 'IMP'")

    con = duckdb.connect()
    gold_glob = gold_single_path()

    # Detect latest month if not provided
    if ref_year is None or ref_month is None:
        d_curr = con.execute(f"""
            SELECT MAX(MAKE_DATE(CAST(year AS INTEGER), CAST(co_mes AS INTEGER), 1))
            FROM read_parquet('{gold_glob}', union_by_name=true)
        """).fetchone()[0]
        if d_curr is None:
            con.close()
            raise RuntimeError("No data found in Gold to determine reference month.")
        ref_year, ref_month = d_curr.year, d_curr.month

    # Month labels (pt-BR)
    meses_pt = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
    mes_nome = meses_pt[ref_month - 1]
    prev_label_val = f"{mes_nome} {ref_year-1} (em US$ FOB)"
    curr_label_val = f"{mes_nome} {ref_year} (em US$ FOB)"
    curr_label_kg  = f"{mes_nome} {ref_year} (em quilogramas líquidos)"

    def ident(s: str) -> str:
        return '"' + s.replace('"', '""') + '"'

    final_sql = f"""
    WITH base AS (
      SELECT
        kind,
        CAST(year AS INTEGER)     AS yr,
        CAST(co_mes AS INTEGER)   AS mo,
        co_pais,
        -- prefer dimension country name if available
        CAST(nm_pais_dim AS VARCHAR) AS pais_nome,
        produto,
        UPPER(TRIM(produto))      AS produto_norm,
        TRIM(produto)             AS produto_clean,
        CAST(vl_fob     AS DECIMAL(20,4)) AS vl_fob,
        CAST(kg_liquido AS DECIMAL(20,6)) AS kg_liquido,
        CAST(qt_estat   AS DECIMAL(20,6)) AS qt_estat,
        MAKE_DATE(CAST(year AS INTEGER), CAST(co_mes AS INTEGER), 1) AS d
      FROM read_parquet('{gold_glob}', union_by_name=true)
      WHERE (vl_fob IS NULL OR vl_fob >= 0)
        AND (kg_liquido IS NULL OR kg_liquido >= 0)
    ),
    latest AS (
      SELECT MAKE_DATE({int(ref_year)}, {int(ref_month)}, 1) AS d_max
    ),
    win_12m AS (
      SELECT
        b.*,
        DATE_TRUNC('month', l.d_max)                     AS dmax_m,
        DATE_TRUNC('month', l.d_max) - INTERVAL 11 MONTH AS dmin_m
      FROM base b CROSS JOIN latest l
    ),
    in_12m AS (
      SELECT * FROM win_12m
      WHERE d BETWEEN dmin_m AND dmax_m
    ),
    month_scope AS (
      SELECT
        DATE_TRUNC('month', d_max)                    AS d_curr,
        DATE_TRUNC('month', d_max) - INTERVAL 1 YEAR  AS d_prev
      FROM latest
    ),

    -- Use last 12 months for ranking (only kind filter here)
    flow_12m AS (
      SELECT * FROM in_12m
      WHERE kind = '{flow_kind}'
    ),

    -- 1) Rank destinations (group by code; carry display name)
    dest_rank AS (
      SELECT
        co_pais,
        MIN(pais_nome) AS pais_nome,
        SUM(vl_fob)    AS vl_fob_12m
      FROM flow_12m
      GROUP BY 1
    ),
    top20_dest AS (
      SELECT *
      FROM (
        SELECT *,
               ROW_NUMBER() OVER (ORDER BY vl_fob_12m DESC, co_pais) AS rn
        FROM dest_rank
      ) WHERE rn <= 20
    ),

    -- 2) Top product per destination over same 12m window
    main_prod AS (
      SELECT
        e.co_pais,
        e.produto_norm,
        MIN(e.produto_clean) AS produto,
        SUM(e.vl_fob)        AS vl_fob_prod_12m,
        ROW_NUMBER() OVER (
          PARTITION BY e.co_pais
          ORDER BY SUM(e.vl_fob) DESC, e.produto_norm
        ) AS rnk
      FROM flow_12m e
      JOIN top20_dest t ON e.co_pais = t.co_pais
      WHERE e.produto_norm IS NOT NULL AND e.produto_norm <> ''
      GROUP BY e.co_pais, e.produto_norm
    ),
    main_prod_pick AS (
      SELECT
        co_pais,
        produto AS top_produto
      FROM main_prod
      WHERE rnk = 1
    ),

    -- 3) YoY for the destination (current vs same month last year)
    curr_m AS (
      SELECT
        b.co_pais,
        SUM(b.vl_fob)     AS vl_fob_curr,
        SUM(b.kg_liquido) AS kg_curr,
        SUM(b.qt_estat)   AS qt_curr
      FROM base b
      JOIN month_scope m ON b.d = m.d_curr
      WHERE b.kind = '{flow_kind}'
      GROUP BY 1
    ),
    prev_m AS (
      SELECT
        b.co_pais,
        SUM(b.vl_fob)     AS vl_fob_prev,
        SUM(b.kg_liquido) AS kg_prev,
        SUM(b.qt_estat)   AS qt_prev
      FROM base b
      JOIN month_scope m ON b.d = m.d_prev
      WHERE b.kind = '{flow_kind}'
      GROUP BY 1
    )

    -- Final: exactly the requested columns and order
    SELECT
      t.pais_nome                                            AS {ident('Destinos Valor FOB US$')},
      COALESCE( CAST(p.vl_fob_prev AS DECIMAL(20,2)), 0 )    AS {ident(prev_label_val)},
      COALESCE( CAST(c.vl_fob_curr AS DECIMAL(20,2)), 0 )    AS {ident(curr_label_val)},
      COALESCE( CAST(c.kg_curr     AS DECIMAL(20,3)), 0 )    AS {ident(curr_label_kg)},
      CASE
        WHEN p.vl_fob_prev IS NULL OR p.vl_fob_prev = 0 THEN NULL
        ELSE (c.vl_fob_curr - p.vl_fob_prev) / p.vl_fob_prev
      END                                                   AS {ident('Variação do valor(US$) em relação ao mesmo mês do ano anterior(em %)')},
      CASE
        WHEN p.kg_prev IS NULL OR p.kg_prev = 0 THEN NULL
        ELSE (c.kg_curr - p.kg_prev) / p.kg_prev
      END                                                   AS {ident('Variação de Quantidade Exportada - Quilograma Líquido (em %)')},
      CASE
        WHEN (p.kg_prev IS NULL OR p.kg_prev = 0) THEN NULL
        WHEN (c.kg_curr IS NULL OR c.kg_curr = 0) THEN NULL
        ELSE
          ((c.vl_fob_curr / NULLIF(c.kg_curr, 0)) - (p.vl_fob_prev / NULLIF(p.kg_prev, 0)))
          / NULLIF((p.vl_fob_prev / NULLIF(p.kg_prev, 0)), 0)
      END                                                   AS {ident('Variação do Preço Médio')},
      CASE
        WHEN p.qt_prev IS NULL OR p.qt_prev = 0 THEN NULL
        ELSE (c.qt_curr - p.qt_prev) / p.qt_prev
      END                                                   AS {ident('Variação da Quantidade Estatística')},
      mp.top_produto                                        AS {ident('Produto mais exportado para o destino')}
    FROM top20_dest t
    LEFT JOIN main_prod_pick mp ON mp.co_pais = t.co_pais
    LEFT JOIN curr_m c          ON c.co_pais  = t.co_pais
    LEFT JOIN prev_m p          ON p.co_pais  = t.co_pais
    ORDER BY t.rn
    """
    
    #out_path = MARTS_DIR / f"{ref_year}" / f"{ref_month}" / f"mart_{flow_kind}_países_report_{ref_year:04d}{ref_month:02d}.parquet"
    #out_path = MARTS_DIR / f"mart_{flow_kind}_países_report_{ref_year:04d}{ref_month:02d}.parquet"
    out_path = mart_out_path(MARTS_DIR, flow_kind, ref_year, ref_month, label="paises")

    con.execute(f"""
      COPY ({final_sql})
      TO '{out_path.as_posix()}'
      (FORMAT PARQUET, OVERWRITE_OR_IGNORE 1)
    """)

    con.close()
    print(f"mart ✔ {out_path}")

# ----------------------- DESTINATIONS by SC Competitiva -----------------------


# ------------------------------ helpers ------------------------------
import re, unicodedata

def _slugify_tag(value) -> str:
    """Turn a category (str or list) into a safe short tag for filenames."""
    if value is None:
        return "all"
    if isinstance(value, (list, tuple, set)):
        value = "_".join(map(str, value))
    s = unicodedata.normalize("NFKD", str(value))
    s = "".join(c for c in s if not unicodedata.combining(c))   # strip accents
    s = re.sub(r"[^\w]+", "_", s, flags=re.ASCII).strip("_")     # keep [A-Za-z0-9_]
    return s[:80] or "all"  

def _month_labels_pt(ref_year: int, ref_month: int):
    meses_pt = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
    nome = meses_pt[ref_month - 1]
    prev_label_val = f"{nome} {ref_year-1} (em US$ FOB)"
    curr_label_val = f"{nome} {ref_year} (em US$ FOB)"
    curr_label_kg  = f"{nome} {ref_year} (em quilogramas líquidos)"
    return nome, prev_label_val, curr_label_val, curr_label_kg

def _ident(s: str) -> str:
    return '"' + s.replace('"','""') + '"'

def _sql_in_list(values):
    """Return SQL IN list for UPPER(TRIM(sc_competitiva)) filtering."""
    if values is None:
        return None
    if isinstance(values, str):
        values = [values]
    cleaned = []
    for v in values:
        if v is None: 
            continue
        s = str(v).strip()
        if not s:
            continue
        s = s.replace("'", "''")  # escape single quotes
        cleaned.append(f"'{s.upper()}'")
    if not cleaned:
        return None
    return ", ".join(cleaned)

def _detect_ref_month(con, gold_glob):
    d_curr = con.execute(f"""
        SELECT MAX(MAKE_DATE(CAST(year AS INTEGER), CAST(co_mes AS INTEGER), 1))
        FROM read_parquet('{gold_glob}', union_by_name=true)
    """).fetchone()[0]
    if d_curr is None:
        raise RuntimeError("No data found in Gold to determine reference month.")
    return d_curr.year, d_curr.month

def build_mart_products_by_sc_competitiva_report(
    sc_competitiva,                       # str or list[str] (case-insensitive)
    ref_year: int | None = None,
    ref_month: int | None = None,
    kind: str = "EXP",
    top_n: int = 20,             # None => ALL products in the category
):
    """
    One row per product in the selected sc_competitiva category (or categories).
    Columns:
      'Produtos Valor FOB US$', '<M-1> (em US$ FOB)', '<M> (em US$ FOB)',
      '<M> (em quilogramas líquidos)',
      'Variação do valor(US$) em relação ao mesmo mês do ano anterior(em %)',
      'Variação de Quantidade Exportada - Quilograma Líquido (em %)',
      'Variação do Preço Médio',
      'Variação da Quantidade Estatística',
      'Principal destino dos produtos mais exportados por SC'
    Ranking basis (for optional top_n): 12m sum of vl_fob within the category.
    """
    flow_kind = (kind or "EXP").upper()
    if flow_kind not in ("EXP","IMP"):
        raise ValueError("kind must be 'EXP' or 'IMP'")

    con = duckdb.connect()
    #gold_glob = f"{GOLD_DIR.as_posix()}/kind={flow_kind}/year=*/*.parquet"
    gold_glob = gold_single_path()

    if ref_year is None or ref_month is None:
        ref_year, ref_month = _detect_ref_month(con, gold_glob)

    _, prev_label_val, curr_label_val, curr_label_kg = _month_labels_pt(ref_year, ref_month)
    in_list = _sql_in_list(sc_competitiva)
    cat_filter = f"AND sc_competitiva_norm IN ({in_list})" if in_list else ""

    limit_clause = f"WHERE rn <= {int(top_n)}" if (isinstance(top_n, int) and top_n > 0) else ""

    final_sql = f"""
    WITH base AS (
      SELECT
        kind,
        CAST(year AS INTEGER)     AS yr,
        CAST(co_mes AS INTEGER)   AS mo,
        co_pais,
        CAST(nm_pais_dim AS VARCHAR) AS pais_nome,
        produto,
        UPPER(TRIM(produto))      AS produto_norm,
        TRIM(produto)             AS produto_clean,
        sc_competitiva,
        UPPER(TRIM(sc_competitiva)) AS sc_competitiva_norm,
        CAST(vl_fob     AS DECIMAL(20,4)) AS vl_fob,
        CAST(kg_liquido AS DECIMAL(20,6)) AS kg_liquido,
        CAST(qt_estat   AS DECIMAL(20,6)) AS qt_estat,
        MAKE_DATE(CAST(year AS INTEGER), CAST(co_mes AS INTEGER), 1) AS d
      FROM read_parquet('{gold_glob}', union_by_name=true)
      WHERE (vl_fob IS NULL OR vl_fob >= 0)
        AND (kg_liquido IS NULL OR kg_liquido >= 0)
    ),
    latest AS (SELECT MAKE_DATE({int(ref_year)}, {int(ref_month)}, 1) AS d_max),
    win_12m AS (
      SELECT b.*, DATE_TRUNC('month', l.d_max) AS dmax_m,
             DATE_TRUNC('month', l.d_max) - INTERVAL 11 MONTH AS dmin_m
      FROM base b CROSS JOIN latest l
    ),
    in_12m AS (SELECT * FROM win_12m WHERE d BETWEEN dmin_m AND dmax_m),

    -- category-filtered last 12 months
    cat_12m AS (
      SELECT * FROM in_12m
      WHERE kind = '{flow_kind}'
        AND produto_norm IS NOT NULL AND produto_norm <> ''
        {cat_filter}
    ),

    -- rank products inside the category by 12m vl_fob
    prod_rank AS (
      SELECT
        produto_norm,
        MIN(produto_clean) AS produto_display,
        MIN(sc_competitiva) AS sc_competitiva,      -- representative label
        SUM(vl_fob)        AS vl_fob_12m
      FROM cat_12m
      GROUP BY 1
    ),
    ordered_prod AS (
      SELECT *,
             ROW_NUMBER() OVER (ORDER BY vl_fob_12m DESC, produto_norm) AS rn
      FROM prod_rank
    ),
    prod_set AS (
      SELECT * FROM ordered_prod
      {limit_clause}
    ),

    -- main destination (within category window) per product
    main_dest AS (
      SELECT
        e.produto_norm,
        e.pais_nome,
        SUM(e.vl_fob) AS vl_fob_dest_12m,
        ROW_NUMBER() OVER (
          PARTITION BY e.produto_norm
          ORDER BY SUM(e.vl_fob) DESC, e.pais_nome
        ) AS rnk
      FROM cat_12m e
      JOIN prod_set t ON e.produto_norm = t.produto_norm
      GROUP BY e.produto_norm, e.pais_nome
    ),
    main_dest_pick AS (
      SELECT produto_norm, pais_nome AS principal_destino
      FROM main_dest WHERE rnk = 1
    ),

    -- YoY for the selected product set (current vs prev same month)
    curr_m AS (
      SELECT
        UPPER(TRIM(b.produto)) AS produto_norm,
        SUM(b.vl_fob)          AS vl_fob_curr,
        SUM(b.kg_liquido)      AS kg_curr,
        SUM(b.qt_estat)        AS qt_curr
      FROM base b
      JOIN prod_set s ON UPPER(TRIM(b.produto)) = s.produto_norm
      JOIN (SELECT DATE_TRUNC('month', d_max) AS d_curr FROM latest) m
        ON b.d = m.d_curr
      WHERE b.kind = '{flow_kind}'
      GROUP BY 1
    ),
    prev_m AS (
      SELECT
        UPPER(TRIM(b.produto)) AS produto_norm,
        SUM(b.vl_fob)          AS vl_fob_prev,
        SUM(b.kg_liquido)      AS kg_prev,
        SUM(b.qt_estat)        AS qt_prev
      FROM base b
      JOIN prod_set s ON UPPER(TRIM(b.produto)) = s.produto_norm
      JOIN (SELECT DATE_TRUNC('month', d_max) - INTERVAL 1 YEAR AS d_prev FROM latest) m
        ON b.d = m.d_prev
      WHERE b.kind = '{flow_kind}'
      GROUP BY 1
    )

    SELECT
      t.produto_display                                        AS {_ident('Produtos Valor FOB US$')},
      COALESCE(CAST(p.vl_fob_prev AS DECIMAL(20,2)), 0)        AS {_ident(prev_label_val)},
      COALESCE(CAST(c.vl_fob_curr AS DECIMAL(20,2)), 0)        AS {_ident(curr_label_val)},
      COALESCE(CAST(c.kg_curr     AS DECIMAL(20,3)), 0)        AS {_ident(curr_label_kg)},
      CASE WHEN p.vl_fob_prev IS NULL OR p.vl_fob_prev = 0 THEN NULL
           ELSE (c.vl_fob_curr - p.vl_fob_prev) / p.vl_fob_prev END
                                                              AS {_ident('Variação do valor(US$) em relação ao mesmo mês do ano anterior(em %)')},
      CASE WHEN p.kg_prev IS NULL OR p.kg_prev = 0 THEN NULL
           ELSE (c.kg_curr - p.kg_prev) / p.kg_prev END
                                                              AS {_ident('Variação de Quantidade Exportada - Quilograma Líquido (em %)')},
      CASE WHEN (p.kg_prev IS NULL OR p.kg_prev = 0) THEN NULL
           WHEN (c.kg_curr IS NULL OR c.kg_curr = 0) THEN NULL
           ELSE ((c.vl_fob_curr / NULLIF(c.kg_curr, 0)) - (p.vl_fob_prev / NULLIF(p.kg_prev, 0)))
                / NULLIF((p.vl_fob_prev / NULLIF(p.kg_prev, 0)), 0) END
                                                              AS {_ident('Variação do Preço Médio')},
      CASE WHEN p.qt_prev IS NULL OR p.qt_prev = 0 THEN NULL
           ELSE (c.qt_curr - p.qt_prev) / p.qt_prev END
                                                              AS {_ident('Variação da Quantidade Estatística')},
      md.principal_destino                                    AS {_ident('Principal destino dos produtos mais exportados por SC')}
    FROM prod_set t
    LEFT JOIN main_dest_pick md ON md.produto_norm = t.produto_norm
    LEFT JOIN curr_m c          ON c.produto_norm  = t.produto_norm
    LEFT JOIN prev_m p          ON p.produto_norm  = t.produto_norm
    ORDER BY t.rn
    """

    tag = _slugify_tag(sc_competitiva)  # one categoria when you run with --each
    #out_path = (MARTS_DIR / f"{ref_year}" / f"{ref_month}" / f"mart_{flow_kind}_produtos_{tag}_report_{ref_year:04d}{ref_month:02d}.parquet").resolve()
    #out_path = (MARTS_DIR / f"mart_{flow_kind}_produtos_{tag}_report_{ref_year:04d}{ref_month:02d}.parquet").resolve()
    out_path = mart_out_path(MARTS_DIR, flow_kind, ref_year, ref_month, label="produtos", tag=tag)

    con.execute(f"""
      COPY ({final_sql})
      TO '{out_path.as_posix()}'
      (FORMAT PARQUET, OVERWRITE_OR_IGNORE 1)
    """)
    con.close()