"""
Reconstrói todos os datamarts com métricas de crescimento YoY.
"""
import duckdb
import numpy as np
import pandas as pd
from pathlib import Path

GOLD = r"c:\Users\bruno.haeming\Desktop\Demandas\OBS - SEAFLOR MURARA\referencia\Dados\gold\comexstat_ncm_sc.parquet"
OUT  = Path(r"c:\Users\bruno.haeming\Desktop\Demandas\OBS - SEAFLOR MURARA\data\processed")

FLORESTAIS = "('Madeira e Móveis', 'Papel e Celulose', 'Produção Florestal')"

SETORES_CNAE = {
    "Madeira (CNAE 16)":          "cd_cgce_n3 = '16'",
    "Moveis (CNAE 31)":           "cd_cgce_n3 = '31'",
    "Base Florestal (CNAE 2)":    "cd_cgce_n3 = '2'",
    "Papel e Celulose (CNAE 17)": "cd_cgce_n3 = '17'",
}

con = duckdb.connect()


def q(sql):
    return con.execute(sql).fetchdf()


def yoy(df, col_val, col_ano, col_grupo=None):
    """Adiciona coluna de variação YoY (%) a um DataFrame já ordenado."""
    df = df.copy()
    if col_grupo:
        prev = (df.groupby(col_grupo)[col_val]
                  .shift(1)
                  .rename("_prev"))
    else:
        prev = df[col_val].shift(1).rename("_prev")
    df["Var YoY (%)"] = ((df[col_val] - prev) / prev.abs() * 100).round(1)
    return df


def var_pp(df, col_val, col_ano, col_grupo=None):
    """Adiciona variação em pontos percentuais."""
    df = df.copy()
    if col_grupo:
        prev = df.groupby(col_grupo)[col_val].shift(1).rename("_prev")
    else:
        prev = df[col_val].shift(1).rename("_prev")
    df["Var pp"] = (df[col_val] - prev).round(2)
    return df


def fmt_pct(v):
    if pd.isna(v):
        return ""
    s = f"+{v:.1f}%" if v > 0 else f"{v:.1f}%"
    return s


# ── 1. Série histórica com YoY ────────────────────────────────────────────────
def dm_serie():
    df = q(f"""
        SELECT nr_ano AS Ano, tp_carga AS Fluxo, sc_competitiva AS Categoria,
               SUM(vl_fob) AS Exportacoes_USD
        FROM read_parquet('{GOLD}')
        WHERE nr_ano BETWEEN 2015 AND 2025
          AND sc_competitiva IN {FLORESTAIS}
        GROUP BY nr_ano, tp_carga, sc_competitiva
        ORDER BY Categoria, Fluxo, Ano
    """)
    df = yoy(df, "Exportacoes_USD", "Ano", col_grupo=["Categoria", "Fluxo"])
    return df


# ── 2. Saldo comercial com YoY ────────────────────────────────────────────────
def dm_saldo():
    df = q(f"""
        SELECT nr_ano AS Ano,
            SUM(CASE WHEN tp_carga='EXP' THEN vl_fob ELSE 0 END) AS Exportacoes_USD,
            SUM(CASE WHEN tp_carga='IMP' THEN vl_fob ELSE 0 END) AS Importacoes_USD,
            SUM(CASE WHEN tp_carga='EXP' THEN vl_fob ELSE -vl_fob END) AS Saldo_USD
        FROM read_parquet('{GOLD}')
        WHERE nr_ano BETWEEN 2015 AND 2025
          AND sc_competitiva IN {FLORESTAIS}
        GROUP BY Ano ORDER BY Ano
    """)
    for col in ["Exportacoes_USD", "Importacoes_USD", "Saldo_USD"]:
        prev = df[col].shift(1)
        label = col.replace("_USD", "")
        df[f"Var {label} YoY (%)"] = ((df[col] - prev) / prev.abs() * 100).round(1)
    return df


# ── 3. Top produtos com YoY ───────────────────────────────────────────────────
def dm_top_produtos():
    df = q(f"""
        WITH base AS (
            SELECT ds_produto AS Produto, sc_competitiva AS Categoria,
                   nr_ano AS Ano,
                   SUM(vl_fob)          AS Exportacoes_USD,
                   SUM(qt_kilo_liquido) AS Kg,
                   COUNT(DISTINCT ds_pais) AS Nr_Destinos
            FROM read_parquet('{GOLD}')
            WHERE tp_carga='EXP' AND nr_ano IN (2023,2024,2025)
              AND sc_competitiva IN {FLORESTAIS}
            GROUP BY Produto, Categoria, Ano
        ),
        rank25 AS (
            SELECT Produto FROM base WHERE Ano=2025
            ORDER BY Exportacoes_USD DESC LIMIT 20
        )
        SELECT b.Produto, b.Categoria, b.Ano,
               b.Exportacoes_USD, b.Kg, b.Nr_Destinos
        FROM base b JOIN rank25 r ON b.Produto = r.Produto
        ORDER BY b.Produto, b.Ano
    """)
    df = df.sort_values(["Produto", "Ano"])
    prev = df.groupby("Produto")["Exportacoes_USD"].shift(1)
    df["Var YoY (%)"] = ((df["Exportacoes_USD"] - prev) / prev.abs() * 100).round(1)
    prev_kg = df.groupby("Produto")["Kg"].shift(1)
    df["Var Kg YoY (%)"] = ((df["Kg"] - prev_kg) / prev_kg.abs() * 100).round(1)
    total_ano = df.groupby("Ano")["Exportacoes_USD"].transform("sum")
    df["Share Total (%)"] = (df["Exportacoes_USD"] / total_ano * 100).round(1)
    return df.sort_values(["Ano", "Exportacoes_USD"], ascending=[True, False])


# ── 4. Top destinos com YoY ───────────────────────────────────────────────────
def dm_top_destinos():
    df = q(f"""
        WITH base AS (
            SELECT ds_pais AS Pais, nr_ano AS Ano,
                   SUM(vl_fob) AS Exportacoes_USD,
                   COUNT(DISTINCT ds_produto) AS Nr_Produtos
            FROM read_parquet('{GOLD}')
            WHERE tp_carga='EXP' AND nr_ano IN (2023,2024,2025)
              AND sc_competitiva IN {FLORESTAIS}
              AND ds_pais IS NOT NULL
            GROUP BY Pais, Ano
        ),
        rank25 AS (
            SELECT Pais FROM base WHERE Ano=2025
            ORDER BY Exportacoes_USD DESC LIMIT 15
        )
        SELECT b.Pais, b.Ano, b.Exportacoes_USD, b.Nr_Produtos
        FROM base b JOIN rank25 r ON b.Pais = r.Pais
        ORDER BY b.Pais, b.Ano
    """)
    prev = df.groupby("Pais")["Exportacoes_USD"].shift(1)
    df["Var YoY (%)"] = ((df["Exportacoes_USD"] - prev) / prev.abs() * 100).round(1)
    total = df.groupby("Ano")["Exportacoes_USD"].transform("sum")
    df["Share Total (%)"] = (df["Exportacoes_USD"] / total * 100).round(1)
    return df.sort_values(["Ano", "Exportacoes_USD"], ascending=[True, False])


# ── 5. Participação SC com YoY ────────────────────────────────────────────────
def dm_participacao():
    df = q(f"""
        SELECT nr_ano AS Ano,
            SUM(CASE WHEN sc_competitiva IN {FLORESTAIS} THEN vl_fob ELSE 0 END) AS Florestal_USD,
            SUM(vl_fob) AS Total_SC_USD,
            SUM(CASE WHEN sc_competitiva IN {FLORESTAIS} THEN vl_fob ELSE 0 END)
              / SUM(vl_fob) * 100 AS Participacao_Pct
        FROM read_parquet('{GOLD}')
        WHERE tp_carga='EXP' AND nr_ano BETWEEN 2015 AND 2025
        GROUP BY Ano ORDER BY Ano
    """)
    df["Var Florestal YoY (%)"]   = ((df["Florestal_USD"] - df["Florestal_USD"].shift(1))
                                      / df["Florestal_USD"].shift(1).abs() * 100).round(1)
    df["Var Total SC YoY (%)"]    = ((df["Total_SC_USD"] - df["Total_SC_USD"].shift(1))
                                      / df["Total_SC_USD"].shift(1).abs() * 100).round(1)
    df["Var Participacao pp"]     = (df["Participacao_Pct"] - df["Participacao_Pct"].shift(1)).round(2)
    return df


# ── 6. YoY produtos detalhado ─────────────────────────────────────────────────
def dm_yoy_produtos():
    df = q(f"""
        SELECT ds_produto AS Produto, sc_competitiva AS Categoria,
            SUM(CASE WHEN nr_ano=2023 THEN vl_fob END) AS Exp_2023_USD,
            SUM(CASE WHEN nr_ano=2024 THEN vl_fob END) AS Exp_2024_USD,
            SUM(CASE WHEN nr_ano=2025 THEN vl_fob END) AS Exp_2025_USD,
            SUM(CASE WHEN nr_ano=2023 THEN qt_kilo_liquido END) AS Kg_2023,
            SUM(CASE WHEN nr_ano=2024 THEN qt_kilo_liquido END) AS Kg_2024,
            SUM(CASE WHEN nr_ano=2025 THEN qt_kilo_liquido END) AS Kg_2025
        FROM read_parquet('{GOLD}')
        WHERE tp_carga='EXP' AND nr_ano IN (2023,2024,2025)
          AND sc_competitiva IN {FLORESTAIS}
        GROUP BY Produto, Categoria
        HAVING SUM(CASE WHEN nr_ano=2025 THEN vl_fob END) > 1000000
        ORDER BY Exp_2025_USD DESC
        LIMIT 20
    """)
    df["Var 23→24 (%)"] = ((df["Exp_2024_USD"] - df["Exp_2023_USD"])
                            / df["Exp_2023_USD"].abs() * 100).round(1)
    df["Var 24→25 (%)"] = ((df["Exp_2025_USD"] - df["Exp_2024_USD"])
                            / df["Exp_2024_USD"].abs() * 100).round(1)
    df["Var Kg 24→25 (%)"] = ((df["Kg_2025"] - df["Kg_2024"])
                               / df["Kg_2024"].abs() * 100).round(1)
    df["Delta USD 24→25"] = (df["Exp_2025_USD"] - df["Exp_2024_USD"]).round(0)
    return df


# ── 7. Destinos por categoria com YoY ────────────────────────────────────────
def dm_destinos_categoria():
    df = q(f"""
        WITH base AS (
            SELECT sc_competitiva AS Categoria, ds_pais AS Pais,
                   nr_ano AS Ano, SUM(vl_fob) AS Exportacoes_USD
            FROM read_parquet('{GOLD}')
            WHERE tp_carga='EXP' AND nr_ano IN (2023,2024,2025)
              AND sc_competitiva IN {FLORESTAIS} AND ds_pais IS NOT NULL
            GROUP BY Categoria, Pais, Ano
        ),
        rank AS (
            SELECT Categoria, Pais,
                   ROW_NUMBER() OVER (PARTITION BY Categoria ORDER BY SUM(Exportacoes_USD) DESC) AS rn
            FROM base WHERE Ano=2025 GROUP BY Categoria, Pais
        )
        SELECT b.Categoria, b.Pais, b.Ano, b.Exportacoes_USD
        FROM base b JOIN rank r ON b.Categoria=r.Categoria AND b.Pais=r.Pais
        WHERE r.rn <= 10
        ORDER BY b.Categoria, b.Pais, b.Ano
    """)
    prev = df.groupby(["Categoria", "Pais"])["Exportacoes_USD"].shift(1)
    df["Var YoY (%)"] = ((df["Exportacoes_USD"] - prev) / prev.abs() * 100).round(1)
    total = df.groupby(["Categoria", "Ano"])["Exportacoes_USD"].transform("sum")
    df["Share Categoria (%)"] = (df["Exportacoes_USD"] / total * 100).round(1)
    return df.sort_values(["Categoria", "Ano", "Exportacoes_USD"], ascending=[True, True, False])


# ── 8. Concentração EUA com YoY ──────────────────────────────────────────────
def dm_concentracao_eua():
    df = q(f"""
        SELECT nr_ano AS Ano,
            SUM(CASE WHEN ds_pais='Estados Unidos' THEN vl_fob END) AS Exp_EUA_USD,
            SUM(vl_fob) AS Exp_Total_Florestal_USD,
            SUM(CASE WHEN ds_pais='Estados Unidos' THEN vl_fob END)
              / SUM(vl_fob) * 100 AS Share_EUA_Pct
        FROM read_parquet('{GOLD}')
        WHERE tp_carga='EXP' AND nr_ano BETWEEN 2015 AND 2025
          AND sc_competitiva IN {FLORESTAIS}
        GROUP BY Ano ORDER BY Ano
    """)
    df["Var Exp EUA YoY (%)"]    = ((df["Exp_EUA_USD"] - df["Exp_EUA_USD"].shift(1))
                                     / df["Exp_EUA_USD"].shift(1).abs() * 100).round(1)
    df["Var Total YoY (%)"]      = ((df["Exp_Total_Florestal_USD"] - df["Exp_Total_Florestal_USD"].shift(1))
                                     / df["Exp_Total_Florestal_USD"].shift(1).abs() * 100).round(1)
    df["Var Share pp"]           = (df["Share_EUA_Pct"] - df["Share_EUA_Pct"].shift(1)).round(2)
    return df


# ── 9. Mensal EUA com YoY ─────────────────────────────────────────────────────
def dm_mensal_eua():
    df = q(f"""
        SELECT nr_ano AS Ano, nr_mes AS Mes,
            SUM(CASE WHEN ds_pais='Estados Unidos' THEN vl_fob ELSE 0 END) AS Exp_EUA_USD,
            SUM(CASE WHEN ds_pais<>'Estados Unidos' THEN vl_fob ELSE 0 END) AS Exp_Outros_USD,
            SUM(vl_fob) AS Exp_Total_USD
        FROM read_parquet('{GOLD}')
        WHERE tp_carga='EXP' AND nr_ano IN (2023,2024,2025)
          AND sc_competitiva IN {FLORESTAIS}
        GROUP BY Ano, Mes ORDER BY Ano, Mes
    """)
    df["Share_EUA_Pct"] = (df["Exp_EUA_USD"] / df["Exp_Total_USD"] * 100).round(1)
    # YoY por mês (mesmo mês ano anterior)
    df_sorted = df.sort_values(["Mes", "Ano"])
    prev_eua   = df_sorted.groupby("Mes")["Exp_EUA_USD"].shift(1)
    prev_total = df_sorted.groupby("Mes")["Exp_Total_USD"].shift(1)
    prev_share = df_sorted.groupby("Mes")["Share_EUA_Pct"].shift(1)
    df_sorted["Var EUA vs mesmo mes ano ant (%)"]   = ((df_sorted["Exp_EUA_USD"] - prev_eua)
                                                        / prev_eua.abs() * 100).round(1)
    df_sorted["Var Total vs mesmo mes ano ant (%)"] = ((df_sorted["Exp_Total_USD"] - prev_total)
                                                        / prev_total.abs() * 100).round(1)
    df_sorted["Var Share pp"]                       = (df_sorted["Share_EUA_Pct"] - prev_share).round(2)
    return df_sorted.sort_values(["Ano", "Mes"])


# ── 10. Queda produtos EUA com métricas extras ────────────────────────────────
def dm_queda_eua():
    return q(f"""
        SELECT ds_produto AS Produto, sc_competitiva AS Categoria,
            SUM(CASE WHEN nr_ano=2023 THEN vl_fob END) AS Exp_EUA_2023_USD,
            SUM(CASE WHEN nr_ano=2024 THEN vl_fob END) AS Exp_EUA_2024_USD,
            SUM(CASE WHEN nr_ano=2025 THEN vl_fob END) AS Exp_EUA_2025_USD,
            SUM(CASE WHEN nr_ano=2025 THEN vl_fob END)
              - SUM(CASE WHEN nr_ano=2024 THEN vl_fob END) AS Delta_24_25_USD,
            (SUM(CASE WHEN nr_ano=2025 THEN vl_fob END)
              - SUM(CASE WHEN nr_ano=2024 THEN vl_fob END))
              / NULLIF(SUM(CASE WHEN nr_ano=2024 THEN vl_fob END), 0) * 100 AS Var_24_25_Pct,
            (SUM(CASE WHEN nr_ano=2024 THEN vl_fob END)
              - SUM(CASE WHEN nr_ano=2023 THEN vl_fob END))
              / NULLIF(SUM(CASE WHEN nr_ano=2023 THEN vl_fob END), 0) * 100 AS Var_23_24_Pct
        FROM read_parquet('{GOLD}')
        WHERE tp_carga='EXP' AND nr_ano IN (2023,2024,2025)
          AND ds_pais='Estados Unidos'
          AND sc_competitiva IN {FLORESTAIS}
        GROUP BY Produto, Categoria
        HAVING SUM(vl_fob) > 500000
        ORDER BY Delta_24_25_USD ASC
        LIMIT 15
    """)


# ── 11. Desvio de comércio com crescimento ────────────────────────────────────
def dm_desvio():
    df = q(f"""
        WITH h1 AS (
            SELECT ds_pais AS Pais, SUM(vl_fob) AS Exp_H1
            FROM read_parquet('{GOLD}')
            WHERE tp_carga='EXP' AND nr_ano=2025 AND nr_mes BETWEEN 1 AND 6
              AND sc_competitiva IN {FLORESTAIS}
            GROUP BY Pais
        ),
        h2 AS (
            SELECT ds_pais AS Pais, SUM(vl_fob) AS Exp_H2
            FROM read_parquet('{GOLD}')
            WHERE tp_carga='EXP' AND nr_ano=2025 AND nr_mes BETWEEN 7 AND 12
              AND sc_competitiva IN {FLORESTAIS}
            GROUP BY Pais
        ),
        h1_24 AS (
            SELECT ds_pais AS Pais, SUM(vl_fob) AS Exp_H1_2024
            FROM read_parquet('{GOLD}')
            WHERE tp_carga='EXP' AND nr_ano=2024 AND nr_mes BETWEEN 7 AND 12
              AND sc_competitiva IN {FLORESTAIS}
            GROUP BY Pais
        )
        SELECT h1.Pais,
               h1.Exp_H1 AS Exp_H1_2025_USD,
               h2.Exp_H2 AS Exp_H2_2025_USD,
               h2.Exp_H2 - h1.Exp_H1 AS Delta_H1_H2_USD,
               (h2.Exp_H2 - h1.Exp_H1) / NULLIF(h1.Exp_H1, 0) * 100 AS Var_H1_H2_Pct,
               h124.Exp_H1_2024 AS Exp_H2_2024_USD,
               (h2.Exp_H2 - h124.Exp_H1_2024) / NULLIF(h124.Exp_H1_2024, 0) * 100 AS Var_YoY_H2_Pct
        FROM h1 JOIN h2 ON h1.Pais=h2.Pais
        LEFT JOIN h1_24 h124 ON h1.Pais=h124.Pais
        WHERE h1.Exp_H1 > 3000000
        ORDER BY Delta_H1_H2_USD DESC
        LIMIT 15
    """)
    return df


# ── 12-14. Gini ───────────────────────────────────────────────────────────────
def gini(values):
    arr = np.array(sorted(values), dtype=float)
    n = len(arr)
    if n == 0 or arr.sum() == 0:
        return None
    idx = np.arange(1, n + 1)
    return (2 * (idx * arr).sum()) / (n * arr.sum()) - (n + 1) / n


def dm_gini():
    res, lorenz_rows, detalhe_rows = [], [], []
    for setor, filtro in SETORES_CNAE.items():
        for ano in [2023, 2024, 2025]:
            df = q(f"""
                SELECT ds_pais AS Pais, SUM(vl_fob) AS Exp_USD
                FROM read_parquet('{GOLD}')
                WHERE tp_carga='EXP' AND nr_ano={ano}
                  AND {filtro} AND ds_pais IS NOT NULL
                GROUP BY Pais ORDER BY Exp_USD DESC
            """)
            if df.empty:
                continue
            total  = df["Exp_USD"].sum()
            n_p    = len(df)
            g      = gini(df["Exp_USD"].values)
            shares = df["Exp_USD"] / total
            hhi    = (shares ** 2).sum() * 10000
            res.append({
                "Setor": setor, "Ano": ano,
                "Gini": round(g, 4),
                "Nr Paises": n_p,
                "Exportacoes USD": round(total, 0),
                "HHI": round(hhi, 0),
                "1 Pais": df.iloc[0]["Pais"],
                "Share 1 Pais (%)": round(df.iloc[0]["Exp_USD"] / total * 100, 1),
                "Share Top 3 (%)": round(df.head(3)["Exp_USD"].sum() / total * 100, 1),
                "Share Top 5 (%)": round(df.head(5)["Exp_USD"].sum() / total * 100, 1),
            })
            for rank, row in enumerate(df.head(10).itertuples(), 1):
                detalhe_rows.append({
                    "Setor": setor, "Ano": ano, "Rank": rank,
                    "Pais": row.Pais,
                    "Exportacoes USD": round(row.Exp_USD, 0),
                    "Share (%)": round(row.Exp_USD / total * 100, 1),
                    "Share Acumulado (%)": round(df.head(rank)["Exp_USD"].sum() / total * 100, 1),
                })
            vals = np.sort(df["Exp_USD"].values)
            cum_pop = np.arange(1, n_p + 1) / n_p * 100
            cum_val = np.cumsum(vals) / total * 100
            step = max(1, n_p // 20)
            for pop, val in zip(cum_pop[::step], cum_val[::step]):
                lorenz_rows.append({"Setor": setor, "Ano": ano,
                                    "% Paises acum": round(pop, 1),
                                    "% Exportacoes acum": round(val, 1)})
            lorenz_rows.append({"Setor": setor, "Ano": ano,
                                 "% Paises acum": 100.0, "% Exportacoes acum": 100.0})

    res_df = pd.DataFrame(res)
    # YoY para Gini e HHI
    res_df = res_df.sort_values(["Setor", "Ano"])
    res_df["Var Gini YoY"] = res_df.groupby("Setor")["Gini"].diff().round(4)
    res_df["Var HHI YoY"]  = res_df.groupby("Setor")["HHI"].diff().round(0)
    res_df["Var Exp YoY (%)"] = (res_df.groupby("Setor")["Exportacoes USD"]
                                        .pct_change() * 100).round(1)
    return (res_df,
            pd.DataFrame(lorenz_rows).drop_duplicates(),
            pd.DataFrame(detalhe_rows))


# ── 15. Resumo de crescimento por atividade (nova aba) ───────────────────────
def dm_crescimento_atividade():
    """Painel único com crescimento YoY de todos os CNAE florestais, 2019-2025."""
    df = q(f"""
        SELECT cd_cgce_n3 AS CNAE, ds_cgce_n3 AS Descricao_CNAE,
               sc_competitiva AS Categoria_SC,
               nr_ano AS Ano,
               SUM(CASE WHEN tp_carga='EXP' THEN vl_fob ELSE 0 END) AS EXP_USD,
               SUM(CASE WHEN tp_carga='IMP' THEN vl_fob ELSE 0 END) AS IMP_USD,
               SUM(CASE WHEN tp_carga='EXP' THEN vl_fob ELSE -vl_fob END) AS Saldo_USD,
               SUM(CASE WHEN tp_carga='EXP' THEN qt_kilo_liquido ELSE 0 END) AS EXP_Kg,
               COUNT(DISTINCT CASE WHEN tp_carga='EXP' THEN ds_pais END) AS Nr_Destinos_EXP,
               COUNT(DISTINCT CASE WHEN tp_carga='EXP' THEN cd_ncm END) AS Nr_NCMs_EXP
        FROM read_parquet('{GOLD}')
        WHERE nr_ano BETWEEN 2019 AND 2025
          AND cd_cgce_n3 IN ('2','16','17','31')
        GROUP BY CNAE, Descricao_CNAE, Categoria_SC, Ano
        ORDER BY CNAE, Ano
    """)
    for col in ["EXP_USD", "IMP_USD", "Saldo_USD", "EXP_Kg"]:
        prev = df.groupby("CNAE")[col].shift(1)
        label = col.replace("_USD", "").replace("_", " ")
        df[f"Var {label} YoY (%)"] = ((df[col] - prev) / prev.abs() * 100).round(1)
    prev_dest = df.groupby("CNAE")["Nr_Destinos_EXP"].shift(1)
    df["Var Nr Destinos"]  = (df["Nr_Destinos_EXP"] - prev_dest).astype("Int64")
    return df


# ── Execução ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Construindo datamarts v2...")
    datamarts = {
        "01_serie_historica_v2":          dm_serie(),
        "02_saldo_comercial_v2":          dm_saldo(),
        "03_top_produtos_v2":             dm_top_produtos(),
        "04_top_destinos_v2":             dm_top_destinos(),
        "05_participacao_sc_v2":          dm_participacao(),
        "06_yoy_produtos_v2":             dm_yoy_produtos(),
        "07_destinos_categoria_v2":       dm_destinos_categoria(),
        "08_concentracao_eua_v2":         dm_concentracao_eua(),
        "09_mensal_eua_v2":               dm_mensal_eua(),
        "10_queda_eua_v2":                dm_queda_eua(),
        "11_desvio_comercio_v2":          dm_desvio(),
        "15_crescimento_por_atividade":   dm_crescimento_atividade(),
    }
    gini_res, lorenz_df, detalhe_df = dm_gini()
    datamarts["12_gini_resumo_v2"]  = gini_res
    datamarts["13_gini_top10_v2"]   = detalhe_df
    datamarts["14_gini_lorenz_v2"]  = lorenz_df

    for nome, df in datamarts.items():
        p = OUT / f"{nome}.csv"
        df.to_csv(p, index=False, encoding="utf-8-sig")
        print(f"  {nome}: {df.shape[0]} linhas x {df.shape[1]} colunas")

    print("Datamarts v2 prontos.")
    con.close()
