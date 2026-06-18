"""
V2 — Comparativo Jan-Mai 2025 vs Jan-Mai 2026 + HHI/Gini de diversificação forçada
Complexo Florestal SC | Observatório FIESC | Junho 2026

Fontes:
  - Gold SC parquet  → 2024 ano fechado, 2025 ano fechado, Jan-Mai 2025
  - Gold ALL parquet → participação SC/Brasil
  - EXP/IMP_2026.csv (bronze) + dims NCM/PAIS → Jan-Mai 2026 (SC e Brasil)

Joins:
  - Produtos: por cd_ncm (não por ds_produto — textos divergem entre fontes)
  - Destinos: por ds_pais (mesmo PAIS.csv nas duas fontes)
  - Concentração HHI/Gini: 2024 ano fechado | 2025 ano fechado | 2026 Jan-Mai
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
OUT        = ROOT / "data" / "processed" / "SEAFLOR_2026_JanMai_2025vs2026_v2.xlsx"

MAX_MES = 5
MESES_NOME = {1:"Jan", 2:"Fev", 3:"Mar", 4:"Abr", 5:"Mai"}

# Filtros de setor: sempre combinam sc_competitiva + cd_cgce_n3
SETORES = {
    "Madeira (CNAE 16)":          "sc_competitiva = 'Madeira e Móveis' AND cd_cgce_n3 = '16'",
    "Moveis (CNAE 31)":           "sc_competitiva = 'Madeira e Móveis' AND cd_cgce_n3 = '31'",
    "Madeira e Moveis (16+31)":   "sc_competitiva = 'Madeira e Móveis' AND cd_cgce_n3 IN ('16','31')",
    "Papel e Celulose (CNAE 17)": "sc_competitiva = 'Papel e Celulose' AND cd_cgce_n3 = '17'",
    "Base Florestal (CNAE 2)":    "sc_competitiva = 'Produção Florestal' AND cd_cgce_n3 = '2'",
    "Complexo Florestal":         "cd_cgce_n3 IN ('2','16','17','31')",
}

# Setores usados nas análises de concentração (HHI/Gini) — excluímos sobreposições
SETORES_CONC = {
    "Madeira (CNAE 16)":          SETORES["Madeira (CNAE 16)"],
    "Moveis (CNAE 31)":           SETORES["Moveis (CNAE 31)"],
    "Papel e Celulose (CNAE 17)": SETORES["Papel e Celulose (CNAE 17)"],
    "Base Florestal (CNAE 2)":    SETORES["Base Florestal (CNAE 2)"],
    "Complexo Florestal":         SETORES["Complexo Florestal"],
}

COMPLEXO_FILTRO = "cd_cgce_n3 IN ('2','16','17','31')"

# ── Cores ─────────────────────────────────────────────────────────────────────
AZUL_ESC = "1F4E79"
AZUL_MED = "2E75B6"
AZUL_CL  = "DEEAF1"
VERDE    = "375623"
VERMELHO = "C00000"
BRANCO   = "FFFFFF"
CINZA    = "595959"
LARANJA  = "ED7D31"

# ── DuckDB + dimensões ────────────────────────────────────────────────────────
con = duckdb.connect()

ncm_df = pd.read_excel(NCM_DICT, dtype=str)
ncm_df.columns = [c.strip() for c in ncm_df.columns]
cod_col = [c for c in ncm_df.columns if "NCM" in c.upper() and "8" in c][0]
ncm_df = ncm_df.rename(columns={
    cod_col: "cd_ncm", "SC Competitiva": "sc_competitiva",
    "CNAE divisão": "cd_cgce_n3", "NO_NCM_POR": "ds_produto",
})
ncm_df["cd_ncm"] = ncm_df["cd_ncm"].astype(str).str.strip()
ncm_df["cd_cgce_n3"] = (
    pd.to_numeric(ncm_df["cd_cgce_n3"], errors="coerce")
    .fillna(0).astype(int).astype(str).replace("0", "")
)
con.register("ncm_dim", ncm_df)

pais_df = pd.read_csv(PAIS_CSV, sep=";", encoding="latin-1", dtype=str)
pais_df.columns = [c.strip() for c in pais_df.columns]
pais_df = pais_df.rename(columns={"CO_PAIS": "co_pais", "NO_PAIS": "ds_pais"})
pais_df["co_pais"] = pais_df["co_pais"].astype(str).str.strip()
con.register("pais_dim", pais_df)

con.execute(f"""
CREATE OR REPLACE VIEW v2026 AS
WITH raw AS (
    SELECT CAST(CO_ANO AS INTEGER) AS nr_ano, CAST(CO_MES AS INTEGER) AS nr_mes,
           CAST(CO_NCM AS VARCHAR) AS cd_ncm, CAST(CO_PAIS AS VARCHAR) AS co_pais,
           CAST(SG_UF_NCM AS VARCHAR) AS sg_uf,
           CAST(VL_FOB AS DOUBLE) AS vl_fob,
           CAST(KG_LIQUIDO AS DOUBLE) AS qt_kilo_liquido,
           'EXP' AS tp_carga
    FROM read_csv_auto('{BRONZE_EXP}', sep=';', ignore_errors=true)
    WHERE CAST(CO_MES AS INTEGER) BETWEEN 1 AND {MAX_MES}
    UNION ALL
    SELECT CAST(CO_ANO AS INTEGER), CAST(CO_MES AS INTEGER),
           CAST(CO_NCM AS VARCHAR), CAST(CO_PAIS AS VARCHAR), CAST(SG_UF_NCM AS VARCHAR),
           CAST(VL_FOB AS DOUBLE), CAST(KG_LIQUIDO AS DOUBLE), 'IMP'
    FROM read_csv_auto('{BRONZE_IMP}', sep=';', ignore_errors=true)
    WHERE CAST(CO_MES AS INTEGER) BETWEEN 1 AND {MAX_MES}
)
SELECT r.*,
       COALESCE(n.sc_competitiva, 'Outros') AS sc_competitiva,
       COALESCE(CAST(n.cd_cgce_n3 AS VARCHAR), '') AS cd_cgce_n3,
       COALESCE(n.ds_produto, r.cd_ncm) AS ds_produto,
       COALESCE(p.ds_pais, 'Outros') AS ds_pais
FROM raw r
LEFT JOIN ncm_dim n ON r.cd_ncm = n.cd_ncm
LEFT JOIN pais_dim p ON r.co_pais = p.co_pais
""")


def q(sql):
    return con.execute(sql).fetchdf()


def var_pct(new, old):
    return ((new - old) / old.abs() * 100).round(1)


# ═══════════════════════════════════════════════════════════════════════════════
# UTILIDADES HHI / GINI
# ═══════════════════════════════════════════════════════════════════════════════
def gini(values):
    arr = np.array(sorted(values), dtype=float)
    n = len(arr)
    if n == 0 or arr.sum() == 0:
        return None
    idx = np.arange(1, n + 1)
    return round((2 * (idx * arr).sum()) / (n * arr.sum()) - (n + 1) / n, 4)


def hhi(values):
    total = sum(values)
    if not total:
        return None
    return round(sum((v / total * 100) ** 2 for v in values), 1)


def get_destinos_exp(setor_filtro, fonte, ano_filtro, mes_filtro="TRUE", uf_filtro="TRUE"):
    """Retorna distribuição de exportações por país."""
    return q(f"""
        SELECT ds_pais AS Pais, SUM(vl_fob) AS EXP_USD
        FROM {fonte}
        WHERE tp_carga='EXP' AND {ano_filtro} AND {mes_filtro}
          AND {setor_filtro} AND {uf_filtro} AND ds_pais IS NOT NULL AND ds_pais != 'Outros'
        GROUP BY Pais
        ORDER BY EXP_USD DESC
    """)


# ═══════════════════════════════════════════════════════════════════════════════
# DATAMARTS EXISTENTES (todos com join por cd_ncm onde aplicável)
# ═══════════════════════════════════════════════════════════════════════════════

def dm_resumo():
    rows = []
    for setor, f_sc in SETORES.items():
        for periodo, ano, src, uf_f in [
            ("Jan-Mai 2025", 2025, f"read_parquet('{GOLD_SC}')", "TRUE"),
            ("Jan-Mai 2026", 2026, "v2026", "sg_uf='SC'"),
        ]:
            r = q(f"""
                SELECT
                    SUM(CASE WHEN tp_carga='EXP' THEN vl_fob       ELSE 0 END) AS EXP_USD,
                    SUM(CASE WHEN tp_carga='IMP' THEN vl_fob       ELSE 0 END) AS IMP_USD,
                    SUM(CASE WHEN tp_carga='EXP' THEN qt_kilo_liquido ELSE 0 END) AS EXP_Kg,
                    COUNT(DISTINCT CASE WHEN tp_carga='EXP' THEN ds_pais END)  AS Nr_Destinos,
                    COUNT(DISTINCT CASE WHEN tp_carga='EXP' THEN cd_ncm  END)  AS Nr_NCMs
                FROM {src}
                WHERE nr_ano={ano} AND nr_mes<={MAX_MES} AND {f_sc} AND {uf_f}
            """).iloc[0]
            rows.append({"Setor": setor, "Periodo": periodo,
                         "EXP_USD": round(r.EXP_USD or 0, 0),
                         "IMP_USD": round(r.IMP_USD or 0, 0),
                         "Saldo":   round((r.EXP_USD or 0) - (r.IMP_USD or 0), 0),
                         "EXP_Kg":  round(r.EXP_Kg or 0, 0),
                         "Nr_Destinos": int(r.Nr_Destinos or 0),
                         "Nr_NCMs":     int(r.Nr_NCMs or 0)})
    df = pd.DataFrame(rows)
    p25 = df[df.Periodo.str.contains("2025")].set_index("Setor")
    p26 = df[df.Periodo.str.contains("2026")].set_index("Setor")
    out = p25[["EXP_USD","IMP_USD","Saldo","EXP_Kg","Nr_Destinos","Nr_NCMs"]].copy()
    out.columns = [f"{c}_2025" for c in out.columns]
    out2 = p26[["EXP_USD","IMP_USD","Saldo","EXP_Kg","Nr_Destinos","Nr_NCMs"]].copy()
    out2.columns = [f"{c}_2026" for c in out2.columns]
    out = out.join(out2).reset_index()
    for m in ["EXP_USD","IMP_USD","Saldo","EXP_Kg"]:
        out[f"Var_{m}_Pct"] = var_pct(out[f"{m}_2026"], out[f"{m}_2025"])
    for m in ["Nr_Destinos","Nr_NCMs"]:
        out[f"Var_{m}"] = out[f"{m}_2026"] - out[f"{m}_2025"]
    return out


def dm_mensal_total():
    rows = []
    for mes in range(1, MAX_MES + 1):
        r25 = q(f"""
            SELECT SUM(CASE WHEN tp_carga='EXP' THEN vl_fob ELSE 0 END) AS EXP_USD,
                   SUM(CASE WHEN tp_carga='IMP' THEN vl_fob ELSE 0 END) AS IMP_USD,
                   SUM(CASE WHEN tp_carga='EXP' THEN qt_kilo_liquido ELSE 0 END) AS EXP_Kg
            FROM read_parquet('{GOLD_SC}')
            WHERE nr_ano=2025 AND nr_mes={mes} AND {COMPLEXO_FILTRO}
        """).iloc[0]
        r26 = q(f"""
            SELECT SUM(CASE WHEN tp_carga='EXP' THEN vl_fob ELSE 0 END) AS EXP_USD,
                   SUM(CASE WHEN tp_carga='IMP' THEN vl_fob ELSE 0 END) AS IMP_USD,
                   SUM(CASE WHEN tp_carga='EXP' THEN qt_kilo_liquido ELSE 0 END) AS EXP_Kg
            FROM v2026
            WHERE nr_ano=2026 AND nr_mes={mes} AND sg_uf='SC' AND {COMPLEXO_FILTRO}
        """).iloc[0]
        rows.append({"Mes_Nome": MESES_NOME[mes],
                     "EXP_USD_2025": round(r25.EXP_USD or 0, 0),
                     "IMP_USD_2025": round(r25.IMP_USD or 0, 0),
                     "EXP_Kg_2025":  round(r25.EXP_Kg  or 0, 0),
                     "EXP_USD_2026": round(r26.EXP_USD or 0, 0),
                     "IMP_USD_2026": round(r26.IMP_USD or 0, 0),
                     "EXP_Kg_2026":  round(r26.EXP_Kg  or 0, 0)})
    df = pd.DataFrame(rows)
    df["Var_EXP_USD_Pct"] = var_pct(df.EXP_USD_2026, df.EXP_USD_2025)
    df["Var_IMP_USD_Pct"] = var_pct(df.IMP_USD_2026, df.IMP_USD_2025)
    df["Var_EXP_Kg_Pct"]  = var_pct(df.EXP_Kg_2026,  df.EXP_Kg_2025)
    tot25 = df[["EXP_USD_2025","IMP_USD_2025","EXP_Kg_2025"]].sum()
    tot26 = df[["EXP_USD_2026","IMP_USD_2026","EXP_Kg_2026"]].sum()
    tot = pd.Series({"Mes_Nome": "TOTAL Jan-Mai",
                     **tot25.to_dict(), **tot26.to_dict(),
                     "Var_EXP_USD_Pct": var_pct(pd.Series([tot26.EXP_USD_2026]), pd.Series([tot25.EXP_USD_2025])).iloc[0],
                     "Var_IMP_USD_Pct": var_pct(pd.Series([tot26.IMP_USD_2026]), pd.Series([tot25.IMP_USD_2025])).iloc[0],
                     "Var_EXP_Kg_Pct":  var_pct(pd.Series([tot26.EXP_Kg_2026]),  pd.Series([tot25.EXP_Kg_2025])).iloc[0]})
    return pd.concat([df, tot.to_frame().T], ignore_index=True)[
        ["Mes_Nome","EXP_USD_2025","EXP_USD_2026","Var_EXP_USD_Pct",
         "IMP_USD_2025","IMP_USD_2026","Var_IMP_USD_Pct",
         "EXP_Kg_2025","EXP_Kg_2026","Var_EXP_Kg_Pct"]]


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
                rows.append({"Setor": setor, "Mes": mes, "Mes_Nome": MESES_NOME[mes],
                             "Ano": ano, "EXP_USD": round(r.EXP_USD or 0, 0),
                             "EXP_Kg": round(r.EXP_Kg or 0, 0)})
    df = pd.DataFrame(rows)
    d25 = df[df.Ano==2025].rename(columns={"EXP_USD":"EXP_USD_2025","EXP_Kg":"EXP_Kg_2025"})
    d26 = df[df.Ano==2026].rename(columns={"EXP_USD":"EXP_USD_2026","EXP_Kg":"EXP_Kg_2026"})
    out = d25[["Setor","Mes","Mes_Nome","EXP_USD_2025","EXP_Kg_2025"]].merge(
          d26[["Setor","Mes","EXP_USD_2026","EXP_Kg_2026"]], on=["Setor","Mes"])
    out["Var_EXP_USD_Pct"] = var_pct(out.EXP_USD_2026, out.EXP_USD_2025)
    out["Var_EXP_Kg_Pct"]  = var_pct(out.EXP_Kg_2026,  out.EXP_Kg_2025)
    return out.sort_values(["Setor","Mes"]).drop(columns="Mes")


def dm_top_produtos():
    # JOIN por cd_ncm — chave única entre fontes; ds_produto vem do gold (nome canônico)
    p26 = q(f"""
        SELECT cd_ncm, sc_competitiva AS Setor,
               SUM(vl_fob) AS EXP_USD_2026,
               SUM(qt_kilo_liquido) AS EXP_Kg_2026,
               COUNT(DISTINCT ds_pais) AS Nr_Destinos_2026
        FROM v2026
        WHERE tp_carga='EXP' AND nr_ano=2026 AND sg_uf='SC' AND {COMPLEXO_FILTRO}
        GROUP BY cd_ncm, Setor
        ORDER BY EXP_USD_2026 DESC
        LIMIT 35
    """)
    p25 = q(f"""
        SELECT cd_ncm, ds_produto AS Produto,
               SUM(vl_fob) AS EXP_USD_2025,
               SUM(qt_kilo_liquido) AS EXP_Kg_2025,
               COUNT(DISTINCT ds_pais) AS Nr_Destinos_2025
        FROM read_parquet('{GOLD_SC}')
        WHERE tp_carga='EXP' AND nr_ano=2025 AND nr_mes<={MAX_MES} AND {COMPLEXO_FILTRO}
        GROUP BY cd_ncm, Produto
    """)
    df = p26.merge(p25, on="cd_ncm", how="left").fillna(0)
    df["Produto"] = df["Produto"].replace("", np.nan).fillna(df["cd_ncm"])
    df["Var_EXP_USD_Pct"] = var_pct(df.EXP_USD_2026, df.EXP_USD_2025)
    df["Var_EXP_Kg_Pct"]  = var_pct(df.EXP_Kg_2026,  df.EXP_Kg_2025)
    df["Preco_Med_2025"]   = (df.EXP_USD_2025 / df.EXP_Kg_2025.replace(0, np.nan)).round(2)
    df["Preco_Med_2026"]   = (df.EXP_USD_2026 / df.EXP_Kg_2026.replace(0, np.nan)).round(2)
    df["Var_Preco_Med_Pct"]= var_pct(df.Preco_Med_2026, df.Preco_Med_2025)
    df["Rank_2026"] = range(1, len(df) + 1)
    return df[["Rank_2026","Produto","Setor",
               "EXP_USD_2025","EXP_USD_2026","Var_EXP_USD_Pct",
               "EXP_Kg_2025","EXP_Kg_2026","Var_EXP_Kg_Pct",
               "Preco_Med_2025","Preco_Med_2026","Var_Preco_Med_Pct",
               "Nr_Destinos_2025","Nr_Destinos_2026"]]


def dm_top_destinos():
    d26 = q(f"""
        SELECT ds_pais AS Pais,
               SUM(vl_fob) AS EXP_USD_2026,
               SUM(qt_kilo_liquido) AS EXP_Kg_2026,
               COUNT(DISTINCT cd_ncm) AS Nr_NCMs_2026
        FROM v2026
        WHERE tp_carga='EXP' AND nr_ano=2026 AND sg_uf='SC' AND {COMPLEXO_FILTRO}
        GROUP BY Pais ORDER BY EXP_USD_2026 DESC LIMIT 25
    """)
    d25 = q(f"""
        SELECT ds_pais AS Pais,
               SUM(vl_fob) AS EXP_USD_2025,
               SUM(qt_kilo_liquido) AS EXP_Kg_2025,
               COUNT(DISTINCT cd_ncm) AS Nr_NCMs_2025
        FROM read_parquet('{GOLD_SC}')
        WHERE tp_carga='EXP' AND nr_ano=2025 AND nr_mes<={MAX_MES} AND {COMPLEXO_FILTRO}
        GROUP BY Pais
    """)
    tot26 = d26.EXP_USD_2026.sum(); tot25 = d25.EXP_USD_2025.sum()
    df = d26.merge(d25, on="Pais", how="left").fillna(0)
    df["Share_2026_Pct"] = (df.EXP_USD_2026 / tot26 * 100).round(2)
    df["Share_2025_Pct"] = (df.EXP_USD_2025 / tot25 * 100).round(2)
    df["Var_Share_pp"]   = (df.Share_2026_Pct - df.Share_2025_Pct).round(2)
    df["Var_EXP_Pct"]    = var_pct(df.EXP_USD_2026, df.EXP_USD_2025)
    df["Rank_2026"] = range(1, len(df)+1)
    return df[["Rank_2026","Pais",
               "EXP_USD_2025","EXP_USD_2026","Var_EXP_Pct",
               "Share_2025_Pct","Share_2026_Pct","Var_Share_pp",
               "EXP_Kg_2025","EXP_Kg_2026","Nr_NCMs_2025","Nr_NCMs_2026"]]


def dm_eua():
    rows = []
    for mes in range(1, MAX_MES + 1):
        r25 = q(f"""
            SELECT SUM(CASE WHEN ds_pais='Estados Unidos' THEN vl_fob ELSE 0 END) AS EXP_EUA,
                   SUM(vl_fob) AS EXP_Total
            FROM read_parquet('{GOLD_SC}')
            WHERE tp_carga='EXP' AND nr_ano=2025 AND nr_mes={mes} AND {COMPLEXO_FILTRO}
        """).iloc[0]
        r26 = q(f"""
            SELECT SUM(CASE WHEN ds_pais ILIKE '%Estados Unidos%' THEN vl_fob ELSE 0 END) AS EXP_EUA,
                   SUM(vl_fob) AS EXP_Total
            FROM v2026
            WHERE tp_carga='EXP' AND nr_ano=2026 AND nr_mes={mes} AND sg_uf='SC' AND {COMPLEXO_FILTRO}
        """).iloc[0]
        rows.append({"Mes_Nome": MESES_NOME[mes],
                     "EXP_EUA_2025":   round(r25.EXP_EUA or 0, 0),
                     "EXP_Total_2025": round(r25.EXP_Total or 0, 0),
                     "EXP_EUA_2026":   round(r26.EXP_EUA or 0, 0),
                     "EXP_Total_2026": round(r26.EXP_Total or 0, 0)})
    df = pd.DataFrame(rows)
    df["Share_EUA_2025_Pct"] = (df.EXP_EUA_2025 / df.EXP_Total_2025 * 100).round(2)
    df["Share_EUA_2026_Pct"] = (df.EXP_EUA_2026 / df.EXP_Total_2026 * 100).round(2)
    df["Var_Share_EUA_pp"]   = (df.Share_EUA_2026_Pct - df.Share_EUA_2025_Pct).round(2)
    df["Var_EXP_EUA_Pct"]    = var_pct(df.EXP_EUA_2026, df.EXP_EUA_2025)
    df["Var_EXP_Total_Pct"]  = var_pct(df.EXP_Total_2026, df.EXP_Total_2025)
    e25 = df.EXP_EUA_2025.sum(); t25 = df.EXP_Total_2025.sum()
    e26 = df.EXP_EUA_2026.sum(); t26 = df.EXP_Total_2026.sum()
    tot = {"Mes_Nome":"TOTAL Jan-Mai",
           "EXP_EUA_2025":e25,"EXP_Total_2025":t25,
           "EXP_EUA_2026":e26,"EXP_Total_2026":t26,
           "Share_EUA_2025_Pct": round(e25/t25*100,2) if t25 else None,
           "Share_EUA_2026_Pct": round(e26/t26*100,2) if t26 else None,
           "Var_Share_EUA_pp":   round(e26/t26*100 - e25/t25*100, 2) if (t25 and t26) else None,
           "Var_EXP_EUA_Pct":    round((e26-e25)/abs(e25)*100, 1) if e25 else None,
           "Var_EXP_Total_Pct":  round((t26-t25)/abs(t25)*100, 1) if t25 else None}
    return pd.concat([df, pd.DataFrame([tot])], ignore_index=True)[
        ["Mes_Nome","EXP_EUA_2025","EXP_EUA_2026","Var_EXP_EUA_Pct",
         "EXP_Total_2025","EXP_Total_2026","Var_EXP_Total_Pct",
         "Share_EUA_2025_Pct","Share_EUA_2026_Pct","Var_Share_EUA_pp"]]


def dm_participacao_sc_br():
    rows = []
    for setor, f_sc in SETORES.items():
        for periodo, ano, src_sc, src_br, uf_f in [
            ("Jan-Mai 2025", 2025, f"read_parquet('{GOLD_SC}')", f"read_parquet('{GOLD_ALL}')", "TRUE"),
            ("Jan-Mai 2026", 2026, "v2026", "v2026", "sg_uf='SC'"),
        ]:
            br_uf = "TRUE"
            sc_exp = q(f"""
                SELECT SUM(vl_fob) AS v FROM {src_sc}
                WHERE tp_carga='EXP' AND nr_ano={ano} AND nr_mes<={MAX_MES} AND {f_sc} AND {uf_f}
            """).iloc[0, 0] or 0
            br_exp = q(f"""
                SELECT SUM(vl_fob) AS v FROM {src_br}
                WHERE tp_carga='EXP' AND nr_ano={ano} AND nr_mes<={MAX_MES} AND {f_sc} AND {br_uf}
            """).iloc[0, 0] or 0
            rows.append({"Setor": setor, "Periodo": periodo,
                         "SC_EXP": round(sc_exp, 0), "BR_EXP": round(br_exp, 0),
                         "Part_Pct": round(sc_exp/br_exp*100, 2) if br_exp else None})
    df = pd.DataFrame(rows)
    p25 = df[df.Periodo.str.contains("2025")].set_index("Setor")[["SC_EXP","BR_EXP","Part_Pct"]]
    p26 = df[df.Periodo.str.contains("2026")].set_index("Setor")[["SC_EXP","BR_EXP","Part_Pct"]]
    p25.columns = ["SC_EXP_2025","BR_EXP_2025","Part_Pct_2025"]
    p26.columns = ["SC_EXP_2026","BR_EXP_2026","Part_Pct_2026"]
    out = p25.join(p26).reset_index()
    out["Var_SC_EXP_Pct"] = var_pct(out.SC_EXP_2026, out.SC_EXP_2025)
    out["Var_BR_EXP_Pct"] = var_pct(out.BR_EXP_2026, out.BR_EXP_2025)
    out["Var_Part_pp"]     = (out.Part_Pct_2026 - out.Part_Pct_2025).round(2)
    return out


def dm_ranking_estados():
    rows = []
    for setor, f_sc in SETORES.items():
        for ano, src in [(2025, f"read_parquet('{GOLD_ALL}')"), (2026, "v2026")]:
            df = q(f"""
                SELECT sg_uf AS UF, SUM(vl_fob) AS EXP_USD
                FROM {src}
                WHERE tp_carga='EXP' AND nr_ano={ano} AND nr_mes<={MAX_MES}
                  AND {f_sc} AND sg_uf IS NOT NULL AND TRIM(sg_uf) != ''
                GROUP BY UF ORDER BY EXP_USD DESC
            """)
            tot = df.EXP_USD.sum()
            df["Share_Pct"] = (df.EXP_USD / tot * 100).round(2)
            df["Rank"] = range(1, len(df)+1)
            df["Setor"] = setor; df["Ano"] = ano
            rows.append(df)
    all_df = pd.concat(rows, ignore_index=True)
    result = []
    for (setor, uf), grp in all_df.groupby(["Setor","UF"]):
        r25 = grp[grp.Ano==2025].iloc[0] if len(grp[grp.Ano==2025]) else None
        r26 = grp[grp.Ano==2026].iloc[0] if len(grp[grp.Ano==2026]) else None
        result.append({
            "Setor": setor, "UF": uf,
            "Rank_2025": int(r25.Rank) if r25 is not None else None,
            "EXP_USD_2025": round(r25.EXP_USD, 0) if r25 is not None else 0,
            "Share_2025_Pct": r25.Share_Pct if r25 is not None else None,
            "Rank_2026": int(r26.Rank) if r26 is not None else None,
            "EXP_USD_2026": round(r26.EXP_USD, 0) if r26 is not None else 0,
            "Share_2026_Pct": r26.Share_Pct if r26 is not None else None,
        })
    out = pd.DataFrame(result)
    out["Var_EXP_Pct"] = var_pct(out.EXP_USD_2026, out.EXP_USD_2025)
    out["Var_Rank"]     = out.Rank_2025 - out.Rank_2026
    top = []
    for setor, grp in out.groupby("Setor"):
        t = grp.dropna(subset=["Rank_2026"]).nsmallest(8, "Rank_2026")
        sc = grp[grp.UF == "SC"]
        top.append(pd.concat([t, sc]).drop_duplicates("UF").sort_values("Rank_2026"))
    return pd.concat(top, ignore_index=True)[
        ["Setor","UF","Rank_2025","Rank_2026","Var_Rank",
         "EXP_USD_2025","EXP_USD_2026","Var_EXP_Pct","Share_2025_Pct","Share_2026_Pct"]]


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
                GROUP BY Pais ORDER BY EXP_USD DESC LIMIT 12
            """)
            df["Setor"] = setor; df["Ano"] = ano
            rows.append(df)
    all_df = pd.concat(rows, ignore_index=True)
    d25 = all_df[all_df.Ano==2025].rename(columns={"EXP_USD":"EXP_USD_2025"})
    d26 = all_df[all_df.Ano==2026].rename(columns={"EXP_USD":"EXP_USD_2026"})
    top = d26.groupby("Setor").head(12)[["Setor","Pais"]]
    out = (top.merge(d26[["Setor","Pais","EXP_USD_2026"]], on=["Setor","Pais"])
              .merge(d25[["Setor","Pais","EXP_USD_2025"]], on=["Setor","Pais"], how="left")
              .fillna(0))
    out["Var_EXP_Pct"] = var_pct(out.EXP_USD_2026, out.EXP_USD_2025)
    return out.sort_values(["Setor","EXP_USD_2026"], ascending=[True, False])


# ═══════════════════════════════════════════════════════════════════════════════
# HHI / GINI — DIVERSIFICAÇÃO FORÇADA
# Períodos: 2024 ano fechado | 2025 ano fechado | 2026 Jan-Mai
# ═══════════════════════════════════════════════════════════════════════════════

PERIODOS_CONC = [
    ("2024 (ano fechado)",  2024, f"read_parquet('{GOLD_SC}')", "TRUE",        "nr_ano=2024"),
    ("2025 (ano fechado)",  2025, f"read_parquet('{GOLD_SC}')", "TRUE",        "nr_ano=2025"),
    ("2026 (Jan-Mai)",      2026, "v2026",                      "sg_uf='SC'",  "nr_ano=2026"),
]


def calc_conc(setor_filtro, fonte, ano_filtro, uf_filtro):
    df = q(f"""
        SELECT ds_pais AS Pais, SUM(vl_fob) AS EXP_USD
        FROM {fonte}
        WHERE tp_carga='EXP' AND {ano_filtro} AND {setor_filtro} AND {uf_filtro}
          AND ds_pais IS NOT NULL AND ds_pais NOT IN ('Outros','')
        GROUP BY Pais ORDER BY EXP_USD DESC
    """)
    if df.empty or df.EXP_USD.sum() == 0:
        return None, None, 0, None, None, None, None
    vals = df.EXP_USD.tolist()
    tot  = sum(vals)
    shares = [v/tot for v in vals]
    g  = gini(vals)
    h  = hhi(vals)
    nr = len(vals)
    top1  = round(shares[0]*100, 2) if shares else None
    top3  = round(sum(shares[:3])*100, 2) if len(shares) >= 3 else round(sum(shares)*100, 2)
    top5  = round(sum(shares[:5])*100, 2) if len(shares) >= 5 else round(sum(shares)*100, 2)
    top1p = df.Pais.iloc[0] if not df.empty else None
    return g, h, nr, top1, top3, top5, top1p


def dm_hhi_gini_resumo():
    """Painel principal: HHI, Gini, Nr Destinos, Top1/3/5 share por setor e período."""
    rows = []
    for setor, f_sc in SETORES_CONC.items():
        for label, ano, fonte, uf_f, ano_f in PERIODOS_CONC:
            g, h, nr, top1, top3, top5, top1p = calc_conc(f_sc, fonte, ano_f, uf_f)
            rows.append({
                "Setor": setor, "Periodo": label, "Nr_Destinos": nr,
                "HHI": h, "Gini": g,
                "Top1_Pais": top1p, "Top1_Share_Pct": top1,
                "Top3_Share_Pct": top3, "Top5_Share_Pct": top5,
            })
    df = pd.DataFrame(rows)
    # variações entre períodos
    out_rows = []
    for setor, grp in df.groupby("Setor"):
        r24 = grp[grp.Periodo.str.contains("2024")].iloc[0]
        r25 = grp[grp.Periodo.str.contains("2025")].iloc[0]
        r26 = grp[grp.Periodo.str.contains("2026")].iloc[0]
        for r, rprev, suffix_curr, suffix_prev in [
            (r25, r24, "2025_vs_2024", ""),
            (r26, r25, "2026_vs_2025", ""),
        ]:
            pass
        out_rows.append({
            "Setor": setor,
            # 2024
            "Nr_Dest_2024": r24.Nr_Destinos, "HHI_2024": r24.HHI, "Gini_2024": r24.Gini,
            "Top1_Share_2024": r24.Top1_Share_Pct, "Top3_Share_2024": r24.Top3_Share_Pct,
            "Top5_Share_2024": r24.Top5_Share_Pct, "Top1_Pais_2024": r24.Top1_Pais,
            # 2025
            "Nr_Dest_2025": r25.Nr_Destinos, "HHI_2025": r25.HHI, "Gini_2025": r25.Gini,
            "Top1_Share_2025": r25.Top1_Share_Pct, "Top3_Share_2025": r25.Top3_Share_Pct,
            "Top5_Share_2025": r25.Top5_Share_Pct, "Top1_Pais_2025": r25.Top1_Pais,
            # 2026
            "Nr_Dest_2026": r26.Nr_Destinos, "HHI_2026": r26.HHI, "Gini_2026": r26.Gini,
            "Top1_Share_2026": r26.Top1_Share_Pct, "Top3_Share_2026": r26.Top3_Share_Pct,
            "Top5_Share_2026": r26.Top5_Share_Pct, "Top1_Pais_2026": r26.Top1_Pais,
            # variações
            "Var_HHI_24_25":   round(r25.HHI - r24.HHI, 1)  if (r25.HHI and r24.HHI) else None,
            "Var_HHI_25_26":   round(r26.HHI - r25.HHI, 1)  if (r26.HHI and r25.HHI) else None,
            "Var_Gini_24_25":  round(r25.Gini - r24.Gini, 4) if (r25.Gini and r24.Gini) else None,
            "Var_Gini_25_26":  round(r26.Gini - r25.Gini, 4) if (r26.Gini and r25.Gini) else None,
            "Var_Dest_24_25":  r25.Nr_Destinos - r24.Nr_Destinos,
            "Var_Dest_25_26":  r26.Nr_Destinos - r25.Nr_Destinos,
        })
    return pd.DataFrame(out_rows)


def dm_hhi_gini_longo():
    """Formato longo para pivot/gráfico: setor × período, uma linha por combinação."""
    rows = []
    for setor, f_sc in SETORES_CONC.items():
        for label, ano, fonte, uf_f, ano_f in PERIODOS_CONC:
            g, h, nr, top1, top3, top5, top1p = calc_conc(f_sc, fonte, ano_f, uf_f)
            rows.append({
                "Setor": setor, "Periodo": label, "Ano_Ref": ano,
                "Nr_Destinos": nr, "HHI": h, "Gini": g,
                "Top1_Pais": top1p, "Top1_Share_Pct": top1,
                "Top3_Share_Pct": top3, "Top5_Share_Pct": top5,
            })
    return pd.DataFrame(rows)


def dm_share_pais_evolucao():
    """
    Share de cada país nos 3 períodos — mostra quem ganhou e quem perdeu.
    Top 20 países por EXP 2025 (ano fechado), para o Complexo Florestal.
    """
    rows_all = []
    for label, ano, fonte, uf_f, ano_f in PERIODOS_CONC:
        df = q(f"""
            SELECT ds_pais AS Pais, SUM(vl_fob) AS EXP_USD
            FROM {fonte}
            WHERE tp_carga='EXP' AND {ano_f} AND {COMPLEXO_FILTRO} AND {uf_f}
              AND ds_pais IS NOT NULL AND ds_pais NOT IN ('Outros','')
            GROUP BY Pais ORDER BY EXP_USD DESC
        """)
        tot = df.EXP_USD.sum()
        df["Share_Pct"] = (df.EXP_USD / tot * 100).round(2)
        df["Periodo"] = label
        df["Ano"] = ano
        rows_all.append(df)
    all_df = pd.concat(rows_all, ignore_index=True)

    # top 20 países por EXP 2025 ano fechado
    top20 = (all_df[all_df.Ano==2025]
             .sort_values("EXP_USD", ascending=False)
             .head(20)["Pais"].tolist())
    filt = all_df[all_df.Pais.isin(top20)].copy()

    d24 = filt[filt.Ano==2024][["Pais","EXP_USD","Share_Pct"]].rename(
        columns={"EXP_USD":"EXP_2024","Share_Pct":"Share_2024_Pct"})
    d25 = filt[filt.Ano==2025][["Pais","EXP_USD","Share_Pct"]].rename(
        columns={"EXP_USD":"EXP_2025","Share_Pct":"Share_2025_Pct"})
    d26 = filt[filt.Ano==2026][["Pais","EXP_USD","Share_Pct"]].rename(
        columns={"EXP_USD":"EXP_2026","Share_Pct":"Share_2026_Pct"})

    out = d25.merge(d24, on="Pais", how="outer").merge(d26, on="Pais", how="outer").fillna(0)
    out["Var_Share_24_25_pp"] = (out.Share_2025_Pct - out.Share_2024_Pct).round(2)
    out["Var_Share_25_26_pp"] = (out.Share_2026_Pct - out.Share_2025_Pct).round(2)
    out["Var_EXP_24_25_Pct"]  = var_pct(out.EXP_2025, out.EXP_2024)
    out["Var_EXP_25_26_Pct"]  = var_pct(out.EXP_2026, out.EXP_2025)
    out["Ganhou_Perdeu_25_26"] = out.Var_Share_25_26_pp.apply(
        lambda x: "GANHOU" if x > 0.5 else ("PERDEU" if x < -0.5 else "ESTAVEL"))
    return out.sort_values("EXP_2025", ascending=False)[
        ["Pais","EXP_2024","EXP_2025","EXP_2026",
         "Share_2024_Pct","Share_2025_Pct","Share_2026_Pct",
         "Var_Share_24_25_pp","Var_Share_25_26_pp",
         "Var_EXP_24_25_Pct","Var_EXP_25_26_Pct","Ganhou_Perdeu_25_26"]]


def dm_hhi_gini_por_setor_detalhe():
    """Top 15 países por setor nos 3 períodos — base para análise de Lorenz."""
    rows = []
    for setor, f_sc in SETORES_CONC.items():
        for label, ano, fonte, uf_f, ano_f in PERIODOS_CONC:
            df = q(f"""
                SELECT ds_pais AS Pais, SUM(vl_fob) AS EXP_USD
                FROM {fonte}
                WHERE tp_carga='EXP' AND {ano_f} AND {f_sc} AND {uf_f}
                  AND ds_pais IS NOT NULL AND ds_pais NOT IN ('Outros','')
                GROUP BY Pais ORDER BY EXP_USD DESC LIMIT 15
            """)
            if df.empty:
                continue
            tot = df.EXP_USD.sum()
            df["Share_Pct"] = (df.EXP_USD / tot * 100).round(2)
            df["Setor"] = setor; df["Periodo"] = label
            df["Rank"] = range(1, len(df)+1)
            rows.append(df)
    return pd.concat(rows, ignore_index=True)[
        ["Setor","Periodo","Rank","Pais","EXP_USD","Share_Pct"]]


# ═══════════════════════════════════════════════════════════════════════════════
# EXCEL BUILDER
# ═══════════════════════════════════════════════════════════════════════════════
def detect_fmt(col):
    c = col.lower()
    if any(k in c for k in ["gini"]):
        return "dec4"
    if any(k in c for k in ["hhi"]):
        return "hhi"
    if any(k in c for k in ["var_", "_pct", "_pp", "share", "part_"]):
        return "pct"
    if any(k in c for k in ["usd","exp_","imp_","saldo","eua_","total_","sc_exp","br_exp","_2024","_2025","_2026"]):
        return "num"
    if "kg" in c:
        return "num"
    if any(k in c for k in ["rank","nr_dest","nr_ncm"]):
        return "int"
    return "text"


def write_sheet(ws, df, wb, titulo, freeze_cols=1):
    F = {
        "hdr":   wb.add_format({"bold":True,"bg_color":AZUL_ESC,"font_color":BRANCO,
                                 "border":1,"text_wrap":True,"valign":"vcenter",
                                 "align":"center","font_size":9}),
        "tit":   wb.add_format({"bold":True,"font_size":11,"bg_color":AZUL_MED,
                                 "font_color":BRANCO,"align":"center","valign":"vcenter"}),
        "num":   wb.add_format({"num_format":"#,##0","border":1,"font_size":9}),
        "num_e": wb.add_format({"num_format":"#,##0","border":1,"font_size":9,"bg_color":AZUL_CL}),
        "pct":   wb.add_format({"num_format":'0.00"%"',"border":1,"font_size":9}),
        "pct_e": wb.add_format({"num_format":'0.00"%"',"border":1,"font_size":9,"bg_color":AZUL_CL}),
        "pct+":  wb.add_format({"num_format":'"+"\\ 0.00"%"',"border":1,"font_size":9,"font_color":VERDE}),
        "pct-":  wb.add_format({"num_format":'0.00"%"',"border":1,"font_size":9,"font_color":VERMELHO}),
        "dec4":  wb.add_format({"num_format":"0.0000","border":1,"font_size":9}),
        "dec4_e":wb.add_format({"num_format":"0.0000","border":1,"font_size":9,"bg_color":AZUL_CL}),
        "dec4+": wb.add_format({"num_format":'"+"\\ 0.0000',"border":1,"font_size":9,"font_color":VERDE}),
        "dec4-": wb.add_format({"num_format":"0.0000","border":1,"font_size":9,"font_color":VERMELHO}),
        "hhi":   wb.add_format({"num_format":"#,##0.0","border":1,"font_size":9}),
        "hhi_e": wb.add_format({"num_format":"#,##0.0","border":1,"font_size":9,"bg_color":AZUL_CL}),
        "hhi+":  wb.add_format({"num_format":'"+"\\ #,##0.0',"border":1,"font_size":9,"font_color":VERDE}),
        "hhi-":  wb.add_format({"num_format":"#,##0.0","border":1,"font_size":9,"font_color":VERMELHO}),
        "int":   wb.add_format({"num_format":"0","border":1,"font_size":9}),
        "int_e": wb.add_format({"num_format":"0","border":1,"font_size":9,"bg_color":AZUL_CL}),
        "int+":  wb.add_format({"num_format":'"+"\\ 0',"border":1,"font_size":9,"font_color":VERDE}),
        "int-":  wb.add_format({"num_format":"0","border":1,"font_size":9,"font_color":VERMELHO}),
        "text":  wb.add_format({"border":1,"font_size":9}),
        "text_e":wb.add_format({"border":1,"font_size":9,"bg_color":AZUL_CL}),
    }
    is_var = {ci: any(k in str(col).lower() for k in ["var_","_pp","24_25","25_26"])
              for ci, col in enumerate(df.columns)}
    fmt    = {ci: detect_fmt(str(col)) for ci, col in enumerate(df.columns)}

    ws.merge_range(0, 0, 0, len(df.columns)-1, titulo, F["tit"])
    ws.set_row(0, 20); ws.set_row(1, 40)

    for ci, col in enumerate(df.columns):
        ws.write(1, ci, str(col), F["hdr"])
        try:
            w = min(max(df.iloc[:, ci].astype(str).map(len).max(), len(str(col)))+3, 38)
        except Exception:
            w = 14
        ws.set_column(ci, ci, w)

    for ri, row in enumerate(df.itertuples(index=False)):
        even = ri % 2 == 0
        for ci, val in enumerate(row):
            ft  = fmt[ci]
            isv = is_var[ci]
            if pd.isna(val) or str(val) in ("nan","inf","-inf",""):
                ws.write(ri+2, ci, "", F["text_e"] if even else F["text"])
                continue
            if ft == "num":
                ws.write(ri+2, ci, val, F["num_e"] if even else F["num"])
            elif ft == "pct":
                if isv and isinstance(val, float):
                    ws.write(ri+2, ci, val, F["pct+"] if val > 0 else (F["pct-"] if val < 0 else F["pct"]))
                else:
                    ws.write(ri+2, ci, val, F["pct_e"] if even else F["pct"])
            elif ft == "dec4":
                if isv and isinstance(val, float):
                    ws.write(ri+2, ci, val, F["dec4+"] if val > 0 else (F["dec4-"] if val < 0 else F["dec4"]))
                else:
                    ws.write(ri+2, ci, val, F["dec4_e"] if even else F["dec4"])
            elif ft == "hhi":
                if isv and isinstance(val, float):
                    ws.write(ri+2, ci, val, F["hhi+"] if val > 0 else (F["hhi-"] if val < 0 else F["hhi"]))
                else:
                    ws.write(ri+2, ci, val, F["hhi_e"] if even else F["hhi"])
            elif ft == "int":
                if isv and isinstance(val, (int, float)):
                    ws.write(ri+2, ci, int(val), F["int+"] if val > 0 else (F["int-"] if val < 0 else F["int"]))
                else:
                    ws.write(ri+2, ci, int(val), F["int_e"] if even else F["int"])
            else:
                ws.write(ri+2, ci, val, F["text_e"] if even else F["text"])
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
        ws_idx.set_column(2, 2, 72)
        Fi = {
            "tit":  wb.add_format({"bold":True,"font_size":14,"font_color":AZUL_ESC,"bottom":2}),
            "sub":  wb.add_format({"italic":True,"font_size":9,"font_color":CINZA}),
            "hdr":  wb.add_format({"bold":True,"bg_color":AZUL_ESC,"font_color":BRANCO,"border":1}),
            "aba":  wb.add_format({"bold":True,"border":1,"align":"center","bg_color":AZUL_MED,"font_color":BRANCO}),
            "aba2": wb.add_format({"bold":True,"border":1,"align":"center","bg_color":LARANJA,"font_color":BRANCO}),
            "dsc":  wb.add_format({"border":1}),
            "dsc_e":wb.add_format({"border":1,"bg_color":AZUL_CL}),
        }
        ws_idx.merge_range("B2:C2",
            "SEAFLOR 2026 — Complexo Florestal SC: Jan-Mai 2025 vs 2026 + HHI/Gini de Diversificacao",
            Fi["tit"])
        ws_idx.merge_range("B3:C3",
            "Fonte: ComexStat/MDIC | Observatorio FIESC | Junho 2026 | v2", Fi["sub"])
        ws_idx.merge_range("B4:C4",
            "Nota: Complexo = cd_cgce_n3 IN (2,16,17,31). "
            "Gini e HHI: 2024 ano fechado | 2025 ano fechado | 2026 Jan-Mai.", Fi["sub"])
        ws_idx.write("B6", "Aba", Fi["hdr"])
        ws_idx.write("C6", "Descricao", Fi["hdr"])
        for i, (nome, (titulo, _, tag)) in enumerate(dms.items()):
            f_aba = Fi["aba2"] if tag == "conc" else Fi["aba"]
            ws_idx.write(6+i, 1, nome, f_aba)
            ws_idx.write(6+i, 2, titulo, Fi["dsc_e"] if i%2==0 else Fi["dsc"])

        for nome, (titulo, df, _) in dms.items():
            ws = wb.add_worksheet(nome)
            writer.sheets[nome] = ws
            fc = 2 if any(c in df.columns for c in ["Setor","Pais","Produto"]) else 1
            write_sheet(ws, df, wb, titulo, freeze_cols=fc)
            print(f"  {nome}: {df.shape[0]}L x {df.shape[1]}C")

    return OUT


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("Construindo SEAFLOR_2026_JanMai_2025vs2026_v2.xlsx...")

    print("  [1/13] Resumo geral...")
    resumo = dm_resumo()

    print("  [2/13] Mensal total complexo...")
    mensal_total = dm_mensal_total()

    print("  [3/13] Mensal por setor...")
    mensal_setor = dm_mensal_setor()

    print("  [4/13] Top produtos (join por cd_ncm)...")
    top_prod = dm_top_produtos()

    print("  [5/13] Top destinos...")
    top_dest = dm_top_destinos()

    print("  [6/13] Concentracao EUA...")
    eua = dm_eua()

    print("  [7/13] Participacao SC/Brasil...")
    part = dm_participacao_sc_br()

    print("  [8/13] Ranking estados...")
    rank = dm_ranking_estados()

    print("  [9/13] Destinos por setor...")
    dest_setor = dm_destinos_setor()

    print("  [10/13] HHI e Gini — resumo comparativo 2024|2025|2026...")
    hhi_gini_res = dm_hhi_gini_resumo()

    print("  [11/13] HHI e Gini — formato longo para grafico...")
    hhi_gini_lng = dm_hhi_gini_longo()

    print("  [12/13] Share por pais — evolucao 2024|2025|2026...")
    share_pais = dm_share_pais_evolucao()

    print("  [13/13] Detalhe destinos por setor (top 15) nos 3 periodos...")
    detalhe_dest = dm_hhi_gini_por_setor_detalhe()

    con.close()

    # dict: nome_aba → (titulo, df, tag)  — tag="conc" pinta laranja no índice
    dms = {
        "1_Resumo_Geral":    ("1. Resumo por Setor — EXP, IMP, Saldo, Kg, Nr Destinos | Jan-Mai 2025 vs 2026", resumo, "base"),
        "2_Mensal_Total":    ("2. Comparativo Mensal — Complexo Florestal SC | Jan-Mai 2025 vs 2026", mensal_total, "base"),
        "3_Mensal_Setor":    ("3. Mensal por Setor e CNAE — EXP SC | Jan-Mai 2025 vs 2026", mensal_setor, "base"),
        "4_Top_Produtos":    ("4. Top 35 Produtos Exportados — Jan-Mai 2026 vs 2025 (valor, volume, preco medio) | join por NCM", top_prod, "base"),
        "5_Top_Destinos":    ("5. Top 25 Destinos das Exportacoes Florestais SC — Jan-Mai 2026 vs 2025", top_dest, "base"),
        "6_Conc_EUA":        ("6. Concentracao EUA — Share nas Exportacoes Florestais SC Mes a Mes | Jan-Mai 2025 vs 2026", eua, "base"),
        "7_Part_SC_BR":      ("7. Participacao SC no Total Brasil por Setor — Jan-Mai 2025 vs 2026", part, "base"),
        "8_Rank_Estados":    ("8. Ranking SC entre Estados Exportadores por Setor — Jan-Mai 2025 vs 2026", rank, "base"),
        "9_Dest_Setor":      ("9. Top 12 Destinos por Setor Principal — Jan-Mai 2025 vs 2026", dest_setor, "base"),
        "10_HHI_Gini":       ("10. HHI e Gini — Concentracao de Destinos: 2024 (ano) | 2025 (ano) | 2026 (Jan-Mai) | Diversificacao Forcada", hhi_gini_res, "conc"),
        "11_HHI_Gini_Longo": ("11. HHI e Gini — Formato Longo por Setor e Periodo (base para grafico)", hhi_gini_lng, "conc"),
        "12_Share_Pais":     ("12. Share por Pais — Evolucao 2024|2025|2026: Ganhadores e Perdedores | Complexo Florestal SC", share_pais, "conc"),
        "13_Dest_Detalhe":   ("13. Top 15 Destinos por Setor nos 3 Periodos — base para Curva de Lorenz", detalhe_dest, "conc"),
    }

    excel = build_excel(dms)
    print(f"\nArquivo: {excel}")
    print(f"Tamanho: {excel.stat().st_size / 1024:.0f} KB")
