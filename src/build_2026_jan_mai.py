"""
Planilha comparativa Jan-Mai 2025 vs Jan-Mai 2026
Complexo Florestal SC — mesmo estilo visual da entrega anterior.

Fontes:
  - Gold SC parquet  → Jan-Mai 2025 (SC)
  - Gold ALL parquet → Jan-Mai 2025 (Brasil)
  - EXP/IMP_2026.csv (bronze) + dims NCM/PAIS → Jan-Mai 2026 (SC e Brasil)
"""
import duckdb
import pandas as pd
import numpy as np
from pathlib import Path

# ── Caminhos ─────────────────────────────────────────────────────────────────
ROOT       = Path(r"c:\Users\bruno.haeming\Desktop\Demandas\OBS - SEAFLOR MURARA")
BRONZE_EXP = str(ROOT / r"referencia\Dados\bronze\EXP\EXP_2026.csv")
BRONZE_IMP = str(ROOT / r"referencia\Dados\bronze\IMP\IMP_2026.csv")
GOLD_SC    = str(ROOT / r"referencia\Dados\gold\comexstat_ncm_sc.parquet")
GOLD_ALL   = str(ROOT / r"referencia\Dados\gold\comexstat_ncm_all.parquet")
NCM_DICT   = str(ROOT / r"referencia\Dados\silver\DICT\NCM_SH4 - atualizado 07.04.2026.xlsx")
PAIS_CSV   = str(ROOT / r"referencia\Dados\silver\DICT\PAIS.csv")
OUT        = ROOT / "data" / "processed" / "SEAFLOR_2026_JanMai_2025vs2026.xlsx"

MAX_MES    = 5
FLORESTAIS = "('Madeira e Móveis', 'Papel e Celulose', 'Produção Florestal')"
COMPLEXO_FILTRO = "cd_cgce_n3 IN ('2','16','17','31')"
SETORES    = {
    "Madeira (CNAE 16)":          "sc_competitiva = 'Madeira e Móveis' AND cd_cgce_n3 = '16'",
    "Moveis (CNAE 31)":           "sc_competitiva = 'Madeira e Móveis' AND cd_cgce_n3 = '31'",
    "Madeira e Moveis (16+31)":   "sc_competitiva = 'Madeira e Móveis' AND cd_cgce_n3 IN ('16','31')",
    "Papel e Celulose (CNAE 17)": "sc_competitiva = 'Papel e Celulose' AND cd_cgce_n3 = '17'",
    "Base Florestal (CNAE 2)":    "sc_competitiva = 'Produção Florestal' AND cd_cgce_n3 = '2'",
    "Complexo Florestal":         "cd_cgce_n3 IN ('2','16','17','31')",
}

MESES_NOME = {1:"Jan",2:"Fev",3:"Mar",4:"Abr",5:"Mai"}

# ── Cores ─────────────────────────────────────────────────────────────────────
AZUL_ESC = "1F4E79"
AZUL_MED = "2E75B6"
AZUL_CL  = "DEEAF1"
VERDE    = "375623"
VERMELHO = "C00000"
BRANCO   = "FFFFFF"
CINZA    = "595959"

# ── DuckDB setup ──────────────────────────────────────────────────────────────
con = duckdb.connect()

# Carregar dimensões
ncm_df = pd.read_excel(NCM_DICT, dtype=str)
ncm_df.columns = [c.strip() for c in ncm_df.columns]
# normalizar coluna de código NCM
cod_col = [c for c in ncm_df.columns if "NCM" in c.upper() and "8" in c][0]
ncm_df = ncm_df.rename(columns={
    cod_col: "cd_ncm",
    "SC Competitiva": "sc_competitiva",
    "CNAE divisão": "cd_cgce_n3",
    "NO_NCM_POR": "ds_produto",
})
ncm_df["cd_ncm"] = ncm_df["cd_ncm"].astype(str).str.strip()
# normalizar cd_cgce_n3: '02' → '2', '16' → '16' etc.
ncm_df["cd_cgce_n3"] = (
    pd.to_numeric(ncm_df["cd_cgce_n3"], errors="coerce")
    .fillna(0).astype(int).astype(str)
    .replace("0", "")
)
con.register("ncm_dim", ncm_df)

pais_df = pd.read_csv(PAIS_CSV, sep=";", encoding="latin-1", dtype=str)
pais_df.columns = [c.strip() for c in pais_df.columns]
pais_df = pais_df.rename(columns={"CO_PAIS": "co_pais", "NO_PAIS": "ds_pais"})
pais_df["co_pais"] = pais_df["co_pais"].astype(str).str.strip()
con.register("pais_dim", pais_df)


def q(sql):
    return con.execute(sql).fetchdf()


# ── View 2026 enriquecida ─────────────────────────────────────────────────────
# Une EXP + IMP 2026 bronze com NCM e PAIS, mantém Jan-Mai
VIEW_2026 = f"""
CREATE OR REPLACE VIEW v2026 AS
WITH raw AS (
    SELECT
        CAST(CO_ANO AS INTEGER)  AS nr_ano,
        CAST(CO_MES AS INTEGER)  AS nr_mes,
        CAST(CO_NCM AS VARCHAR)  AS cd_ncm,
        CAST(CO_PAIS AS VARCHAR) AS co_pais,
        CAST(SG_UF_NCM AS VARCHAR) AS sg_uf,
        CAST(VL_FOB AS DOUBLE)   AS vl_fob,
        CAST(KG_LIQUIDO AS DOUBLE) AS qt_kilo_liquido,
        'EXP' AS tp_carga
    FROM read_csv_auto('{BRONZE_EXP}', sep=';', ignore_errors=true)
    WHERE CAST(CO_MES AS INTEGER) BETWEEN 1 AND {MAX_MES}

    UNION ALL

    SELECT
        CAST(CO_ANO AS INTEGER),
        CAST(CO_MES AS INTEGER),
        CAST(CO_NCM AS VARCHAR),
        CAST(CO_PAIS AS VARCHAR),
        CAST(SG_UF_NCM AS VARCHAR),
        CAST(VL_FOB AS DOUBLE),
        CAST(KG_LIQUIDO AS DOUBLE),
        'IMP'
    FROM read_csv_auto('{BRONZE_IMP}', sep=';', ignore_errors=true)
    WHERE CAST(CO_MES AS INTEGER) BETWEEN 1 AND {MAX_MES}
)
SELECT
    r.*,
    COALESCE(n.sc_competitiva, 'Outros') AS sc_competitiva,
    COALESCE(CAST(n.cd_cgce_n3 AS VARCHAR), '') AS cd_cgce_n3,
    COALESCE(n.ds_produto, r.cd_ncm) AS ds_produto,
    COALESCE(p.ds_pais, 'Outros') AS ds_pais
FROM raw r
LEFT JOIN ncm_dim n ON r.cd_ncm = n.cd_ncm
LEFT JOIN pais_dim p ON r.co_pais = p.co_pais
"""
con.execute(VIEW_2026)

# ── Helpers de variação ───────────────────────────────────────────────────────
def var_pct(new, old):
    """Element-wise % variation."""
    return ((new - old) / old.abs() * 100).round(1)


def add_var(df, col_25, col_26, label):
    df[label] = var_pct(df[col_26], df[col_25])
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# DATAMART 1 — Resumo geral por setor
# ═══════════════════════════════════════════════════════════════════════════════
def dm_resumo():
    rows = []
    for setor, f_sc in SETORES.items():
        for periodo, (src, uf_filt) in {
            "Jan-Mai 2025": (f"read_parquet('{GOLD_SC}')", "TRUE"),
            "Jan-Mai 2026": ("v2026", "sg_uf = 'SC'"),
        }.items():
            r = q(f"""
                SELECT
                    SUM(CASE WHEN tp_carga='EXP' THEN vl_fob       ELSE 0 END) AS EXP_USD,
                    SUM(CASE WHEN tp_carga='IMP' THEN vl_fob       ELSE 0 END) AS IMP_USD,
                    SUM(CASE WHEN tp_carga='EXP' THEN qt_kilo_liquido ELSE 0 END) AS EXP_Kg,
                    COUNT(DISTINCT CASE WHEN tp_carga='EXP' THEN ds_pais END)  AS Nr_Destinos,
                    COUNT(DISTINCT CASE WHEN tp_carga='EXP' THEN cd_ncm END)   AS Nr_NCMs
                FROM {src}
                WHERE nr_mes <= {MAX_MES}
                  AND {("nr_ano=2025" if "2025" in periodo else "nr_ano=2026")}
                  AND {f_sc} AND {uf_filt}
            """).iloc[0]
            rows.append({
                "Setor": setor,
                "Periodo": periodo,
                "EXP_USD":      round(r["EXP_USD"] or 0, 0),
                "IMP_USD":      round(r["IMP_USD"] or 0, 0),
                "Saldo_USD":    round((r["EXP_USD"] or 0) - (r["IMP_USD"] or 0), 0),
                "EXP_Kg":       round(r["EXP_Kg"] or 0, 0),
                "Nr_Destinos":  int(r["Nr_Destinos"] or 0),
                "Nr_NCMs":      int(r["Nr_NCMs"] or 0),
            })
    df = pd.DataFrame(rows)
    p25 = df[df["Periodo"].str.contains("2025")].set_index("Setor")
    p26 = df[df["Periodo"].str.contains("2026")].set_index("Setor")
    out = p25[["EXP_USD","IMP_USD","Saldo_USD","EXP_Kg","Nr_Destinos","Nr_NCMs"]].copy()
    out.columns = [f"{c}_2025" for c in out.columns]
    out2 = p26[["EXP_USD","IMP_USD","Saldo_USD","EXP_Kg","Nr_Destinos","Nr_NCMs"]].copy()
    out2.columns = [f"{c}_2026" for c in out2.columns]
    out = out.join(out2).reset_index()
    for m in ["EXP_USD","IMP_USD","Saldo_USD","EXP_Kg"]:
        out[f"Var_{m}_Pct"] = var_pct(out[f"{m}_2026"], out[f"{m}_2025"])
    for m in ["Nr_Destinos","Nr_NCMs"]:
        out[f"Var_{m}_pp"] = out[f"{m}_2026"] - out[f"{m}_2025"]
    return out


# ═══════════════════════════════════════════════════════════════════════════════
# DATAMART 2 — Comparativo mensal — complexo florestal
# ═══════════════════════════════════════════════════════════════════════════════
def dm_mensal_total():
    rows = []
    for mes in range(1, MAX_MES + 1):
        r25 = q(f"""
            SELECT SUM(CASE WHEN tp_carga='EXP' THEN vl_fob ELSE 0 END) AS EXP_USD,
                   SUM(CASE WHEN tp_carga='IMP' THEN vl_fob ELSE 0 END) AS IMP_USD,
                   SUM(CASE WHEN tp_carga='EXP' THEN qt_kilo_liquido ELSE 0 END) AS EXP_Kg
            FROM read_parquet('{GOLD_SC}')
            WHERE nr_ano=2025 AND nr_mes={mes}
              AND {COMPLEXO_FILTRO}
        """).iloc[0]
        r26 = q(f"""
            SELECT SUM(CASE WHEN tp_carga='EXP' THEN vl_fob ELSE 0 END) AS EXP_USD,
                   SUM(CASE WHEN tp_carga='IMP' THEN vl_fob ELSE 0 END) AS IMP_USD,
                   SUM(CASE WHEN tp_carga='EXP' THEN qt_kilo_liquido ELSE 0 END) AS EXP_Kg
            FROM v2026
            WHERE nr_ano=2026 AND nr_mes={mes} AND sg_uf='SC'
              AND {COMPLEXO_FILTRO}
        """).iloc[0]
        rows.append({
            "Mes": mes, "Mes_Nome": MESES_NOME[mes],
            "EXP_USD_2025": round(r25["EXP_USD"] or 0, 0),
            "IMP_USD_2025": round(r25["IMP_USD"] or 0, 0),
            "EXP_Kg_2025":  round(r25["EXP_Kg"]  or 0, 0),
            "EXP_USD_2026": round(r26["EXP_USD"] or 0, 0),
            "IMP_USD_2026": round(r26["IMP_USD"] or 0, 0),
            "EXP_Kg_2026":  round(r26["EXP_Kg"]  or 0, 0),
        })
    df = pd.DataFrame(rows)
    df["Var_EXP_USD_Pct"] = var_pct(df["EXP_USD_2026"], df["EXP_USD_2025"])
    df["Var_IMP_USD_Pct"] = var_pct(df["IMP_USD_2026"], df["IMP_USD_2025"])
    df["Var_EXP_Kg_Pct"]  = var_pct(df["EXP_Kg_2026"],  df["EXP_Kg_2025"])
    # total linha
    tot = {c: df[c].sum() for c in df.columns if "_USD" in c or "_Kg" in c}
    tot["Mes"] = 0; tot["Mes_Nome"] = "TOTAL Jan-Mai"
    tot["Var_EXP_USD_Pct"] = var_pct(
        pd.Series([tot["EXP_USD_2026"]]), pd.Series([tot["EXP_USD_2025"]])).iloc[0]
    tot["Var_IMP_USD_Pct"] = var_pct(
        pd.Series([tot["IMP_USD_2026"]]), pd.Series([tot["IMP_USD_2025"]])).iloc[0]
    tot["Var_EXP_Kg_Pct"] = var_pct(
        pd.Series([tot["EXP_Kg_2026"]]), pd.Series([tot["EXP_Kg_2025"]])).iloc[0]
    df = pd.concat([df, pd.DataFrame([tot])], ignore_index=True)
    return df[["Mes_Nome","EXP_USD_2025","EXP_USD_2026","Var_EXP_USD_Pct",
               "IMP_USD_2025","IMP_USD_2026","Var_IMP_USD_Pct",
               "EXP_Kg_2025","EXP_Kg_2026","Var_EXP_Kg_Pct"]]


# ═══════════════════════════════════════════════════════════════════════════════
# DATAMART 3 — Mensal por setor SC
# ═══════════════════════════════════════════════════════════════════════════════
def dm_mensal_setor():
    rows = []
    for setor, f_sc in SETORES.items():
        for mes in range(1, MAX_MES + 1):
            for ano, src, uf_f in [
                (2025, f"read_parquet('{GOLD_SC}')", "TRUE"),
                (2026, "v2026", "sg_uf='SC'"),
            ]:
                r = q(f"""
                    SELECT SUM(CASE WHEN tp_carga='EXP' THEN vl_fob ELSE 0 END) AS EXP_USD,
                           SUM(CASE WHEN tp_carga='EXP' THEN qt_kilo_liquido ELSE 0 END) AS EXP_Kg
                    FROM {src}
                    WHERE nr_ano={ano} AND nr_mes={mes} AND {f_sc} AND {uf_f}
                """).iloc[0]
                rows.append({
                    "Setor": setor, "Mes": mes, "Mes_Nome": MESES_NOME[mes],
                    "Ano": ano,
                    "EXP_USD": round(r["EXP_USD"] or 0, 0),
                    "EXP_Kg":  round(r["EXP_Kg"]  or 0, 0),
                })
    df = pd.DataFrame(rows)
    df25 = df[df["Ano"] == 2025].rename(columns={"EXP_USD":"EXP_USD_2025","EXP_Kg":"EXP_Kg_2025"})
    df26 = df[df["Ano"] == 2026].rename(columns={"EXP_USD":"EXP_USD_2026","EXP_Kg":"EXP_Kg_2026"})
    out = df25[["Setor","Mes","Mes_Nome","EXP_USD_2025","EXP_Kg_2025"]].merge(
          df26[["Setor","Mes","EXP_USD_2026","EXP_Kg_2026"]], on=["Setor","Mes"])
    out["Var_EXP_USD_Pct"] = var_pct(out["EXP_USD_2026"], out["EXP_USD_2025"])
    out["Var_EXP_Kg_Pct"]  = var_pct(out["EXP_Kg_2026"],  out["EXP_Kg_2025"])
    return out.sort_values(["Setor","Mes"])


# ═══════════════════════════════════════════════════════════════════════════════
# DATAMART 4 — Top produtos Jan-Mai 2026 vs 2025
# ═══════════════════════════════════════════════════════════════════════════════
def dm_top_produtos():
    # Join por cd_ncm (código 8 dígitos) — chave única e inequívoca entre as fontes.
    # ds_produto vem do gold parquet como nome canônico.
    p26 = q(f"""
        SELECT cd_ncm, sc_competitiva AS Setor,
               SUM(vl_fob) AS EXP_USD_2026,
               SUM(qt_kilo_liquido) AS EXP_Kg_2026,
               COUNT(DISTINCT ds_pais) AS Nr_Destinos_2026
        FROM v2026
        WHERE tp_carga='EXP' AND nr_ano=2026 AND sg_uf='SC'
          AND {COMPLEXO_FILTRO}
        GROUP BY cd_ncm, Setor
        ORDER BY EXP_USD_2026 DESC
        LIMIT 30
    """)
    p25 = q(f"""
        SELECT cd_ncm, ds_produto AS Produto,
               SUM(vl_fob) AS EXP_USD_2025,
               SUM(qt_kilo_liquido) AS EXP_Kg_2025,
               COUNT(DISTINCT ds_pais) AS Nr_Destinos_2025
        FROM read_parquet('{GOLD_SC}')
        WHERE tp_carga='EXP' AND nr_ano=2025 AND nr_mes<={MAX_MES}
          AND {COMPLEXO_FILTRO}
        GROUP BY cd_ncm, Produto
    """)
    df = p26.merge(p25, on="cd_ncm", how="left").fillna(0)
    # usar nome do gold como canônico; fallback para cd_ncm se não houver match
    df["Produto"] = df["Produto"].replace("", np.nan).fillna(df["cd_ncm"])
    df["Var_EXP_USD_Pct"] = var_pct(df["EXP_USD_2026"], df["EXP_USD_2025"])
    df["Var_EXP_Kg_Pct"]  = var_pct(df["EXP_Kg_2026"],  df["EXP_Kg_2025"])
    df["Preco_Med_2025"]   = (df["EXP_USD_2025"] / df["EXP_Kg_2025"].replace(0, np.nan)).round(2)
    df["Preco_Med_2026"]   = (df["EXP_USD_2026"] / df["EXP_Kg_2026"].replace(0, np.nan)).round(2)
    df["Var_Preco_Med_Pct"]= var_pct(df["Preco_Med_2026"], df["Preco_Med_2025"])
    df["Rank_2026"] = range(1, len(df) + 1)
    return df[["Rank_2026","Produto","Setor",
               "EXP_USD_2025","EXP_USD_2026","Var_EXP_USD_Pct",
               "EXP_Kg_2025","EXP_Kg_2026","Var_EXP_Kg_Pct",
               "Preco_Med_2025","Preco_Med_2026","Var_Preco_Med_Pct",
               "Nr_Destinos_2025","Nr_Destinos_2026"]]


# ═══════════════════════════════════════════════════════════════════════════════
# DATAMART 5 — Top destinos Jan-Mai 2026 vs 2025
# ═══════════════════════════════════════════════════════════════════════════════
def dm_top_destinos():
    d26 = q(f"""
        SELECT ds_pais AS Pais,
               SUM(vl_fob) AS EXP_USD_2026,
               SUM(qt_kilo_liquido) AS EXP_Kg_2026,
               COUNT(DISTINCT cd_ncm) AS Nr_NCMs_2026
        FROM v2026
        WHERE tp_carga='EXP' AND nr_ano=2026 AND sg_uf='SC'
          AND {COMPLEXO_FILTRO}
        GROUP BY Pais
        ORDER BY EXP_USD_2026 DESC
        LIMIT 25
    """)
    d25 = q(f"""
        SELECT ds_pais AS Pais,
               SUM(vl_fob) AS EXP_USD_2025,
               SUM(qt_kilo_liquido) AS EXP_Kg_2025,
               COUNT(DISTINCT cd_ncm) AS Nr_NCMs_2025
        FROM read_parquet('{GOLD_SC}')
        WHERE tp_carga='EXP' AND nr_ano=2025 AND nr_mes<={MAX_MES}
          AND {COMPLEXO_FILTRO}
        GROUP BY Pais
    """)
    total_26 = d26["EXP_USD_2026"].sum()
    total_25 = d25["EXP_USD_2025"].sum()
    df = d26.merge(d25, on="Pais", how="left").fillna(0)
    df["Share_2026_Pct"]   = (df["EXP_USD_2026"] / total_26 * 100).round(2)
    df["Share_2025_Pct"]   = (df["EXP_USD_2025"] / total_25 * 100).round(2)
    df["Var_Share_pp"]     = (df["Share_2026_Pct"] - df["Share_2025_Pct"]).round(2)
    df["Var_EXP_USD_Pct"]  = var_pct(df["EXP_USD_2026"], df["EXP_USD_2025"])
    df["Rank_2026"] = range(1, len(df) + 1)
    return df[["Rank_2026","Pais",
               "EXP_USD_2025","EXP_USD_2026","Var_EXP_USD_Pct",
               "Share_2025_Pct","Share_2026_Pct","Var_Share_pp",
               "EXP_Kg_2025","EXP_Kg_2026",
               "Nr_NCMs_2025","Nr_NCMs_2026"]]


# ═══════════════════════════════════════════════════════════════════════════════
# DATAMART 6 — EUA: exposição tarifária Jan-Mai 2025 vs 2026
# ═══════════════════════════════════════════════════════════════════════════════
def dm_eua():
    rows = []
    for mes in range(1, MAX_MES + 1):
        r25 = q(f"""
            SELECT
                SUM(CASE WHEN ds_pais='Estados Unidos' THEN vl_fob ELSE 0 END) AS EXP_EUA_2025,
                SUM(vl_fob) AS EXP_Total_2025
            FROM read_parquet('{GOLD_SC}')
            WHERE tp_carga='EXP' AND nr_ano=2025 AND nr_mes={mes}
              AND {COMPLEXO_FILTRO}
        """).iloc[0]
        r26 = q(f"""
            SELECT
                SUM(CASE WHEN ds_pais ILIKE '%Estados Unidos%' THEN vl_fob ELSE 0 END) AS EXP_EUA_2026,
                SUM(vl_fob) AS EXP_Total_2026
            FROM v2026
            WHERE tp_carga='EXP' AND nr_ano=2026 AND nr_mes={mes} AND sg_uf='SC'
              AND {COMPLEXO_FILTRO}
        """).iloc[0]
        rows.append({
            "Mes_Nome": MESES_NOME[mes],
            "EXP_EUA_2025":    round(r25["EXP_EUA_2025"] or 0, 0),
            "EXP_Total_2025":  round(r25["EXP_Total_2025"] or 0, 0),
            "EXP_EUA_2026":    round(r26["EXP_EUA_2026"] or 0, 0),
            "EXP_Total_2026":  round(r26["EXP_Total_2026"] or 0, 0),
        })
    df = pd.DataFrame(rows)
    df["Share_EUA_2025_Pct"] = (df["EXP_EUA_2025"] / df["EXP_Total_2025"] * 100).round(2)
    df["Share_EUA_2026_Pct"] = (df["EXP_EUA_2026"] / df["EXP_Total_2026"] * 100).round(2)
    df["Var_Share_EUA_pp"]   = (df["Share_EUA_2026_Pct"] - df["Share_EUA_2025_Pct"]).round(2)
    df["Var_EXP_EUA_Pct"]    = var_pct(df["EXP_EUA_2026"], df["EXP_EUA_2025"])
    df["Var_EXP_Total_Pct"]  = var_pct(df["EXP_Total_2026"], df["EXP_Total_2025"])
    # total
    tot_eua25  = df["EXP_EUA_2025"].sum();  tot_t25 = df["EXP_Total_2025"].sum()
    tot_eua26  = df["EXP_EUA_2026"].sum();  tot_t26 = df["EXP_Total_2026"].sum()
    tot = {
        "Mes_Nome": "TOTAL Jan-Mai",
        "EXP_EUA_2025": tot_eua25, "EXP_Total_2025": tot_t25,
        "EXP_EUA_2026": tot_eua26, "EXP_Total_2026": tot_t26,
        "Share_EUA_2025_Pct": round(tot_eua25/tot_t25*100,2) if tot_t25 else None,
        "Share_EUA_2026_Pct": round(tot_eua26/tot_t26*100,2) if tot_t26 else None,
        "Var_Share_EUA_pp":   round(tot_eua26/tot_t26*100 - tot_eua25/tot_t25*100, 2) if (tot_t25 and tot_t26) else None,
        "Var_EXP_EUA_Pct":    round((tot_eua26-tot_eua25)/abs(tot_eua25)*100,1) if tot_eua25 else None,
        "Var_EXP_Total_Pct":  round((tot_t26-tot_t25)/abs(tot_t25)*100,1) if tot_t25 else None,
    }
    df = pd.concat([df, pd.DataFrame([tot])], ignore_index=True)
    return df[["Mes_Nome","EXP_EUA_2025","EXP_EUA_2026","Var_EXP_EUA_Pct",
               "EXP_Total_2025","EXP_Total_2026","Var_EXP_Total_Pct",
               "Share_EUA_2025_Pct","Share_EUA_2026_Pct","Var_Share_EUA_pp"]]


# ═══════════════════════════════════════════════════════════════════════════════
# DATAMART 7 — Participação SC/Brasil Jan-Mai 2025 vs 2026
# ═══════════════════════════════════════════════════════════════════════════════
def dm_participacao_sc_br():
    rows = []
    for setor, f_sc in SETORES.items():
        for periodo, ano, src_sc, src_br, uf_f in [
            ("Jan-Mai 2025", 2025,
             f"read_parquet('{GOLD_SC}')", f"read_parquet('{GOLD_ALL}')", "TRUE"),
            ("Jan-Mai 2026", 2026,
             "v2026", "v2026", "sg_uf='SC'"),
        ]:
            br_src = f"read_parquet('{GOLD_ALL}')" if ano == 2025 else "v2026"
            uf_all = "TRUE" if ano == 2025 else "TRUE"
            sc_q = q(f"""
                SELECT SUM(CASE WHEN tp_carga='EXP' THEN vl_fob ELSE 0 END) AS sc_exp
                FROM {src_sc}
                WHERE nr_ano={ano} AND nr_mes<={MAX_MES} AND {f_sc} AND {uf_f}
            """).iloc[0]["sc_exp"] or 0
            br_q = q(f"""
                SELECT SUM(CASE WHEN tp_carga='EXP' THEN vl_fob ELSE 0 END) AS br_exp
                FROM {br_src}
                WHERE nr_ano={ano} AND nr_mes<={MAX_MES} AND {f_sc} AND {uf_all}
            """).iloc[0]["br_exp"] or 0
            rows.append({
                "Setor": setor, "Periodo": periodo,
                "SC_EXP_USD": round(sc_q, 0),
                "BR_EXP_USD": round(br_q, 0),
                "Participacao_Pct": round(sc_q / br_q * 100, 2) if br_q else None,
            })
    df = pd.DataFrame(rows)
    p25 = df[df["Periodo"].str.contains("2025")].set_index("Setor")
    p26 = df[df["Periodo"].str.contains("2026")].set_index("Setor")
    out = p25[["SC_EXP_USD","BR_EXP_USD","Participacao_Pct"]].copy()
    out.columns = ["SC_EXP_2025","BR_EXP_2025","Part_Pct_2025"]
    out2 = p26[["SC_EXP_USD","BR_EXP_USD","Participacao_Pct"]].copy()
    out2.columns = ["SC_EXP_2026","BR_EXP_2026","Part_Pct_2026"]
    out = out.join(out2).reset_index()
    out["Var_SC_EXP_Pct"]  = var_pct(out["SC_EXP_2026"], out["SC_EXP_2025"])
    out["Var_BR_EXP_Pct"]  = var_pct(out["BR_EXP_2026"], out["BR_EXP_2025"])
    out["Var_Part_pp"]      = (out["Part_Pct_2026"] - out["Part_Pct_2025"]).round(2)
    return out


# ═══════════════════════════════════════════════════════════════════════════════
# DATAMART 8 — Ranking estados Jan-Mai 2026 vs 2025
# ═══════════════════════════════════════════════════════════════════════════════
def dm_ranking_estados():
    rows = []
    for setor, f_sc in SETORES.items():
        for ano, src in [(2025, f"read_parquet('{GOLD_ALL}')"), (2026, "v2026")]:
            uf_col = "sg_uf" if ano == 2025 else "sg_uf"
            df = q(f"""
                SELECT {uf_col} AS UF, SUM(vl_fob) AS EXP_USD
                FROM {src}
                WHERE tp_carga='EXP' AND nr_ano={ano} AND nr_mes<={MAX_MES}
                  AND {f_sc} AND {uf_col} IS NOT NULL AND TRIM({uf_col}) != ''
                GROUP BY UF ORDER BY EXP_USD DESC
            """)
            total = df["EXP_USD"].sum()
            df["Share_Pct"] = (df["EXP_USD"] / total * 100).round(2)
            df["Rank"] = range(1, len(df) + 1)
            df["Setor"] = setor; df["Ano"] = ano
            rows.append(df)
    all_df = pd.concat(rows, ignore_index=True)
    # pivot 2025 vs 2026 com rank SC
    result = []
    for (setor, uf), grp in all_df.groupby(["Setor","UF"]):
        r25 = grp[grp["Ano"]==2025].iloc[0] if len(grp[grp["Ano"]==2025]) else None
        r26 = grp[grp["Ano"]==2026].iloc[0] if len(grp[grp["Ano"]==2026]) else None
        result.append({
            "Setor": setor, "UF": uf,
            "Rank_2025": int(r25["Rank"]) if r25 is not None else None,
            "EXP_USD_2025": round(r25["EXP_USD"], 0) if r25 is not None else 0,
            "Share_2025_Pct": r25["Share_Pct"] if r25 is not None else None,
            "Rank_2026": int(r26["Rank"]) if r26 is not None else None,
            "EXP_USD_2026": round(r26["EXP_USD"], 0) if r26 is not None else 0,
            "Share_2026_Pct": r26["Share_Pct"] if r26 is not None else None,
        })
    out = pd.DataFrame(result)
    out["Var_EXP_Pct"] = var_pct(out["EXP_USD_2026"], out["EXP_USD_2025"])
    out["Var_Rank"] = out["Rank_2025"] - out["Rank_2026"]  # positivo = subiu
    # filtrar: top 8 por 2026 EXP + sempre SC
    top_por_setor = []
    for setor, grp in out.groupby("Setor"):
        top = grp.nsmallest(8, "Rank_2026")
        sc = grp[grp["UF"] == "SC"]
        combined = pd.concat([top, sc]).drop_duplicates("UF")
        top_por_setor.append(combined.sort_values("Rank_2026"))
    return pd.concat(top_por_setor, ignore_index=True)[
        ["Setor","UF","Rank_2025","Rank_2026","Var_Rank",
         "EXP_USD_2025","EXP_USD_2026","Var_EXP_Pct",
         "Share_2025_Pct","Share_2026_Pct"]
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# DATAMART 9 — Destinos por setor Jan-Mai 2026 vs 2025
# ═══════════════════════════════════════════════════════════════════════════════
def dm_destinos_setor():
    rows = []
    for setor, f_sc in [
        ("Madeira e Moveis (16+31)", SETORES["Madeira e Moveis (16+31)"]),
        ("Papel e Celulose (CNAE 17)", SETORES["Papel e Celulose (CNAE 17)"]),
        ("Base Florestal (CNAE 2)", SETORES["Base Florestal (CNAE 2)"]),
    ]:
        for ano, src, uf_f in [
            (2025, f"read_parquet('{GOLD_SC}')", "TRUE"),
            (2026, "v2026", "sg_uf='SC'"),
        ]:
            df = q(f"""
                SELECT ds_pais AS Pais, SUM(vl_fob) AS EXP_USD
                FROM {src}
                WHERE tp_carga='EXP' AND nr_ano={ano} AND nr_mes<={MAX_MES}
                  AND {f_sc} AND {uf_f}
                GROUP BY Pais ORDER BY EXP_USD DESC
                LIMIT 10
            """)
            df["Setor"] = setor; df["Ano"] = ano
            rows.append(df)
    all_df = pd.concat(rows, ignore_index=True)
    d25 = all_df[all_df["Ano"]==2025].rename(columns={"EXP_USD":"EXP_USD_2025"})
    d26 = all_df[all_df["Ano"]==2026].rename(columns={"EXP_USD":"EXP_USD_2026"})
    # top 10 por 2026
    top = d26.groupby("Setor").head(10)[["Setor","Pais"]]
    out = top.merge(d26[["Setor","Pais","EXP_USD_2026"]], on=["Setor","Pais"])\
             .merge(d25[["Setor","Pais","EXP_USD_2025"]], on=["Setor","Pais"], how="left").fillna(0)
    out["Var_EXP_USD_Pct"] = var_pct(out["EXP_USD_2026"], out["EXP_USD_2025"])
    return out.sort_values(["Setor","EXP_USD_2026"], ascending=[True, False])


# ═══════════════════════════════════════════════════════════════════════════════
# Excel builder — mesmo estilo visual
# ═══════════════════════════════════════════════════════════════════════════════
def detect_fmt(col):
    c = col.lower()
    if any(k in c for k in ["var_", "yoy", "_pct", "share", "participacao", "_pp", "part_"]):
        return "pct"
    if any(k in c for k in ["usd", "exp_", "imp_", "saldo", "eua_2", "total_2", "sc_exp", "br_exp"]):
        return "num"
    if "kg" in c:
        return "num"
    if "rank" in c or "nr_" in c or "nr " in c:
        return "int"
    if "preco" in c:
        return "num"
    return "text"


def write_sheet(ws, df, wb, titulo, freeze_cols=1):
    F = {
        "hdr":   wb.add_format({"bold": True, "bg_color": AZUL_ESC, "font_color": BRANCO,
                                 "border": 1, "text_wrap": True, "valign": "vcenter",
                                 "align": "center", "font_size": 9}),
        "tit":   wb.add_format({"bold": True, "font_size": 11, "bg_color": AZUL_MED,
                                 "font_color": BRANCO, "align": "center", "valign": "vcenter"}),
        "num":   wb.add_format({"num_format": "#,##0", "border": 1, "font_size": 9}),
        "num_e": wb.add_format({"num_format": "#,##0", "border": 1, "font_size": 9, "bg_color": AZUL_CL}),
        "pct":   wb.add_format({"num_format": '0.00"%"', "border": 1, "font_size": 9}),
        "pct_e": wb.add_format({"num_format": '0.00"%"', "border": 1, "font_size": 9, "bg_color": AZUL_CL}),
        "pct+":  wb.add_format({"num_format": '"+"\\ 0.00"%"', "border": 1, "font_size": 9, "font_color": VERDE}),
        "pct-":  wb.add_format({"num_format": '0.00"%"', "border": 1, "font_size": 9, "font_color": VERMELHO}),
        "int":   wb.add_format({"num_format": "0", "border": 1, "font_size": 9}),
        "int_e": wb.add_format({"num_format": "0", "border": 1, "font_size": 9, "bg_color": AZUL_CL}),
        "text":  wb.add_format({"border": 1, "font_size": 9}),
        "text_e":wb.add_format({"border": 1, "font_size": 9, "bg_color": AZUL_CL}),
    }
    is_var = {ci: any(k in str(col).lower() for k in ["var_","_pp","yoy"])
              for ci, col in enumerate(df.columns)}
    fmt    = {ci: detect_fmt(str(col)) for ci, col in enumerate(df.columns)}

    ws.merge_range(0, 0, 0, len(df.columns) - 1, titulo, F["tit"])
    ws.set_row(0, 20)
    ws.set_row(1, 40)

    for ci, col in enumerate(df.columns):
        ws.write(1, ci, str(col), F["hdr"])
        try:
            max_data = df.iloc[:, ci].astype(str).map(len).max()
        except Exception:
            max_data = 10
        w = min(max(max_data, len(str(col))) + 3, 36)
        ws.set_column(ci, ci, w)

    for ri, row in enumerate(df.itertuples(index=False)):
        even = ri % 2 == 0
        for ci, val in enumerate(row):
            ft = fmt[ci]
            is_v = is_var[ci]
            if pd.isna(val) or str(val) in ("nan","inf","-inf",""):
                ws.write(ri + 2, ci, "", F["text_e"] if even else F["text"])
                continue
            if ft == "num":
                ws.write(ri + 2, ci, val, F["num_e"] if even else F["num"])
            elif ft == "pct":
                if is_v and isinstance(val, float):
                    ws.write(ri + 2, ci, val, F["pct+"] if val > 0 else (F["pct-"] if val < 0 else F["pct"]))
                else:
                    ws.write(ri + 2, ci, val, F["pct_e"] if even else F["pct"])
            elif ft == "int":
                ws.write(ri + 2, ci, int(val) if not pd.isna(val) else "", F["int_e"] if even else F["int"])
            else:
                ws.write(ri + 2, ci, val, F["text_e"] if even else F["text"])
    ws.freeze_panes(2, freeze_cols)


def build_excel(dms):
    with pd.ExcelWriter(OUT, engine="xlsxwriter",
                        engine_kwargs={"options": {"nan_inf_to_errors": True}}) as writer:
        wb = writer.book

        # Índice
        ws_idx = wb.add_worksheet("0_Indice")
        writer.sheets["0_Indice"] = ws_idx
        ws_idx.set_column(0, 0, 4)
        ws_idx.set_column(1, 1, 36)
        ws_idx.set_column(2, 2, 70)
        Fi = {
            "tit":  wb.add_format({"bold": True, "font_size": 14, "font_color": AZUL_ESC, "bottom": 2}),
            "sub":  wb.add_format({"italic": True, "font_size": 9, "font_color": CINZA}),
            "hdr":  wb.add_format({"bold": True, "bg_color": AZUL_ESC, "font_color": BRANCO, "border": 1}),
            "aba":  wb.add_format({"bold": True, "border": 1, "align": "center",
                                    "bg_color": AZUL_MED, "font_color": BRANCO}),
            "dsc":  wb.add_format({"border": 1}),
            "dsc_e":wb.add_format({"border": 1, "bg_color": AZUL_CL}),
        }
        ws_idx.merge_range("B2:C2",
            "SEAFLOR 2026 — Comercio Exterior SC: Comparativo Jan-Mai 2025 vs Jan-Mai 2026",
            Fi["tit"])
        ws_idx.merge_range("B3:C3",
            "Fonte: ComexStat/MDIC | Observatorio FIESC | Junho 2026", Fi["sub"])
        ws_idx.merge_range("B4:C4",
            "Complexo Florestal: Madeira (CNAE 16), Moveis (CNAE 31), "
            "Papel e Celulose (CNAE 17), Base Florestal (CNAE 2)", Fi["sub"])
        ws_idx.write("B6", "Aba", Fi["hdr"])
        ws_idx.write("C6", "Conteudo", Fi["hdr"])
        for i, (nome, (titulo, _)) in enumerate(dms.items()):
            ws_idx.write(6 + i, 1, nome, Fi["aba"])
            ws_idx.write(6 + i, 2, titulo, Fi["dsc_e"] if i % 2 == 0 else Fi["dsc"])

        # Abas de dados
        for nome, (titulo, df) in dms.items():
            ws = wb.add_worksheet(nome)
            writer.sheets[nome] = ws
            write_sheet(ws, df, wb, titulo, freeze_cols=(2 if "Setor" in df.columns else 1))
            print(f"  {nome}: {df.shape[0]}L x {df.shape[1]}C")

    return OUT


# ═══════════════════════════════════════════════════════════════════════════════
# main
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("Construindo datamarts Jan-Mai 2025 vs 2026...")

    print("  [1/9] Resumo geral por setor...")
    resumo = dm_resumo()

    print("  [2/9] Mensal total complexo florestal...")
    mensal_total = dm_mensal_total()

    print("  [3/9] Mensal por setor...")
    mensal_setor = dm_mensal_setor()

    print("  [4/9] Top produtos...")
    top_prod = dm_top_produtos()

    print("  [5/9] Top destinos...")
    top_dest = dm_top_destinos()

    print("  [6/9] Concentracao EUA...")
    eua = dm_eua()

    print("  [7/9] Participacao SC/Brasil...")
    part_sc_br = dm_participacao_sc_br()

    print("  [8/9] Ranking estados...")
    rank_estados = dm_ranking_estados()

    print("  [9/9] Destinos por setor...")
    dest_setor = dm_destinos_setor()

    con.close()

    dms = {
        "1_Resumo_Geral": (
            "1. Resumo por Setor — EXP, IMP, Saldo, Kg, Nr Destinos | Jan-Mai 2025 vs 2026",
            resumo),
        "2_Mensal_Total": (
            "2. Comparativo Mensal Jan-Mai — Complexo Florestal SC 2025 vs 2026",
            mensal_total),
        "3_Mensal_Setor": (
            "3. Mensal por Setor e CNAE — EXP SC Jan-Mai 2025 vs 2026",
            mensal_setor),
        "4_Top_Produtos": (
            "4. Top 30 Produtos Exportados — Jan-Mai 2026 vs 2025 (valor, volume, preco medio)",
            top_prod),
        "5_Top_Destinos": (
            "5. Top 25 Destinos das Exportacoes Florestais SC — Jan-Mai 2026 vs 2025",
            top_dest),
        "6_Concentracao_EUA": (
            "6. EUA — Exposicao Tarifaria: Share nas Exportacoes Florestais SC Mes a Mes 2025 vs 2026",
            eua),
        "7_Participacao_SC_BR": (
            "7. Participacao SC no Total Brasil por Setor — Jan-Mai 2025 vs 2026",
            part_sc_br),
        "8_Ranking_Estados": (
            "8. Ranking SC entre os Estados Exportadores por Setor — Jan-Mai 2025 vs 2026",
            rank_estados),
        "9_Destinos_Setor": (
            "9. Top 10 Destinos por Setor — Jan-Mai 2025 vs 2026",
            dest_setor),
    }

    excel = build_excel(dms)
    print(f"\nArquivo: {excel}")
    print(f"Tamanho: {excel.stat().st_size / 1024:.0f} KB")
