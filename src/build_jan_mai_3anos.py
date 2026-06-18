"""
Comparativo Jan-Mai: 2024 vs 2025 vs 2026
Complexo Florestal SC | Observatório FIESC | Junho 2026

Fontes:
  - Gold SC parquet  → 2024 Jan-Mai e 2025 Jan-Mai
  - EXP/IMP_2026.csv (bronze) + dims NCM/PAIS → 2026 Jan-Mai (SC)
  - Gold ALL parquet → participação SC/Brasil e ranking estados

Mesmas análises da v2 (25vs26), agora com os três anos lado a lado.
HHI/Gini comparado nos três períodos Jan-Mai para consistência metodológica.
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
OUT        = ROOT / "data" / "processed" / "SEAFLOR_2026_JanMai_3anos_v2.xlsx"

MAX_MES = 5
MESES_NOME = {1:"Jan", 2:"Fev", 3:"Mar", 4:"Abr", 5:"Mai"}

SETORES = {
    "Madeira (CNAE 16)":          "sc_competitiva = 'Madeira e Móveis' AND cd_cgce_n3 = '16'",
    "Moveis (CNAE 31)":           "sc_competitiva = 'Madeira e Móveis' AND cd_cgce_n3 = '31'",
    "Madeira e Moveis (16+31)":   "sc_competitiva = 'Madeira e Móveis' AND cd_cgce_n3 IN ('16','31')",
    "Papel e Celulose (CNAE 17)": "sc_competitiva = 'Papel e Celulose' AND cd_cgce_n3 = '17'",
    "Base Florestal (CNAE 2)":    "sc_competitiva = 'Produção Florestal' AND cd_cgce_n3 = '2'",
    "Complexo Florestal":         "cd_cgce_n3 IN ('2','16','17','31')",
}

SETORES_CONC = {
    "Madeira (CNAE 16)":          SETORES["Madeira (CNAE 16)"],
    "Moveis (CNAE 31)":           SETORES["Moveis (CNAE 31)"],
    "Papel e Celulose (CNAE 17)": SETORES["Papel e Celulose (CNAE 17)"],
    "Base Florestal (CNAE 2)":    SETORES["Base Florestal (CNAE 2)"],
    "Complexo Florestal":         SETORES["Complexo Florestal"],
}

COMPLEXO_FILTRO = "cd_cgce_n3 IN ('2','16','17','31')"

# Fontes por ano: (ano, fonte_sql, filtro_uf, filtro_periodo)
PERIODOS = [
    (2024, f"read_parquet('{GOLD_SC}')", "TRUE",       f"nr_ano=2024 AND nr_mes<={MAX_MES}"),
    (2025, f"read_parquet('{GOLD_SC}')", "TRUE",       f"nr_ano=2025 AND nr_mes<={MAX_MES}"),
    (2026, "v2026",                      "sg_uf='SC'", f"nr_ano=2026 AND nr_mes<={MAX_MES}"),
]

ANOS = [2024, 2025, 2026]

# ── Cores ─────────────────────────────────────────────────────────────────────
AZUL_ESC = "1F4E79"
AZUL_MED = "2E75B6"
AZUL_CL  = "DEEAF1"
VERDE    = "375623"
VERMELHO = "C00000"
BRANCO   = "FFFFFF"
CINZA    = "595959"
LARANJA  = "ED7D31"
AMARELO  = "FFF2CC"

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
# HHI / GINI
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


def interpreta_hhi(h):
    if h is None:
        return ""
    if h < 1000:
        return "Diversificado"
    if h < 1500:
        return "Baixa concentracao"
    if h < 2500:
        return "Concentracao moderada"
    return "Alta concentracao"


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
    vals   = df.EXP_USD.tolist()
    tot    = sum(vals)
    shares = [v / tot for v in vals]
    g      = gini(vals)
    h      = hhi(vals)
    nr     = len(vals)
    top1   = round(shares[0] * 100, 2) if shares else None
    top3   = round(sum(shares[:3]) * 100, 2) if len(shares) >= 3 else round(sum(shares) * 100, 2)
    top5   = round(sum(shares[:5]) * 100, 2) if len(shares) >= 5 else round(sum(shares) * 100, 2)
    top1p  = df.Pais.iloc[0] if not df.empty else None
    return g, h, nr, top1, top3, top5, top1p


# ═══════════════════════════════════════════════════════════════════════════════
# DATAMARTS
# ═══════════════════════════════════════════════════════════════════════════════

def dm_resumo():
    """Resumo EXP/IMP/Saldo/Kg/Destinos/NCMs por setor — 3 anos."""
    rows = []
    for setor, f_sc in SETORES.items():
        for ano, src, uf_f, ano_f in PERIODOS:
            r = q(f"""
                SELECT
                    SUM(CASE WHEN tp_carga='EXP' THEN vl_fob          ELSE 0 END) AS EXP_USD,
                    SUM(CASE WHEN tp_carga='IMP' THEN vl_fob          ELSE 0 END) AS IMP_USD,
                    SUM(CASE WHEN tp_carga='EXP' THEN qt_kilo_liquido ELSE 0 END) AS EXP_Kg,
                    COUNT(DISTINCT CASE WHEN tp_carga='EXP' THEN ds_pais END)     AS Nr_Destinos,
                    COUNT(DISTINCT CASE WHEN tp_carga='EXP' THEN cd_ncm  END)     AS Nr_NCMs
                FROM {src}
                WHERE {ano_f} AND {f_sc} AND {uf_f}
            """).iloc[0]
            rows.append({"Setor": setor, "Ano": ano,
                         "EXP_USD": round(r.EXP_USD or 0, 0),
                         "IMP_USD": round(r.IMP_USD or 0, 0),
                         "Saldo":   round((r.EXP_USD or 0) - (r.IMP_USD or 0), 0),
                         "EXP_Kg":  round(r.EXP_Kg or 0, 0),
                         "Nr_Destinos": int(r.Nr_Destinos or 0),
                         "Nr_NCMs":     int(r.Nr_NCMs or 0)})
    df = pd.DataFrame(rows)
    pivot = {ano: df[df.Ano == ano].set_index("Setor") for ano in ANOS}
    out = pivot[2024][["EXP_USD","IMP_USD","Saldo","EXP_Kg","Nr_Destinos","Nr_NCMs"]].copy()
    out.columns = [f"{c}_2024" for c in out.columns]
    for ano in [2025, 2026]:
        tmp = pivot[ano][["EXP_USD","IMP_USD","Saldo","EXP_Kg","Nr_Destinos","Nr_NCMs"]].copy()
        tmp.columns = [f"{c}_{ano}" for c in tmp.columns]
        out = out.join(tmp)
    out = out.reset_index()
    for m in ["EXP_USD","IMP_USD","Saldo","EXP_Kg"]:
        out[f"Var_{m}_24_25_Pct"] = var_pct(out[f"{m}_2025"], out[f"{m}_2024"])
        out[f"Var_{m}_25_26_Pct"] = var_pct(out[f"{m}_2026"], out[f"{m}_2025"])
    for m in ["Nr_Destinos","Nr_NCMs"]:
        out[f"Var_{m}_24_25"] = out[f"{m}_2025"] - out[f"{m}_2024"]
        out[f"Var_{m}_25_26"] = out[f"{m}_2026"] - out[f"{m}_2025"]
    return out


def dm_mensal_total():
    """Mensal total do Complexo Florestal — 3 anos."""
    rows = []
    for mes in range(1, MAX_MES + 1):
        rec = {"Mes_Nome": MESES_NOME[mes]}
        for ano, src, uf_f, _ in PERIODOS:
            r = q(f"""
                SELECT SUM(CASE WHEN tp_carga='EXP' THEN vl_fob          ELSE 0 END) AS EXP_USD,
                       SUM(CASE WHEN tp_carga='IMP' THEN vl_fob          ELSE 0 END) AS IMP_USD,
                       SUM(CASE WHEN tp_carga='EXP' THEN qt_kilo_liquido ELSE 0 END) AS EXP_Kg
                FROM {src}
                WHERE nr_ano={ano} AND nr_mes={mes} AND {COMPLEXO_FILTRO} AND {uf_f}
            """).iloc[0]
            rec[f"EXP_USD_{ano}"] = round(r.EXP_USD or 0, 0)
            rec[f"IMP_USD_{ano}"] = round(r.IMP_USD or 0, 0)
            rec[f"EXP_Kg_{ano}"]  = round(r.EXP_Kg  or 0, 0)
        rows.append(rec)
    df = pd.DataFrame(rows)
    df["Var_EXP_USD_24_25_Pct"] = var_pct(df.EXP_USD_2025, df.EXP_USD_2024)
    df["Var_EXP_USD_25_26_Pct"] = var_pct(df.EXP_USD_2026, df.EXP_USD_2025)
    df["Var_IMP_USD_24_25_Pct"] = var_pct(df.IMP_USD_2025, df.IMP_USD_2024)
    df["Var_IMP_USD_25_26_Pct"] = var_pct(df.IMP_USD_2026, df.IMP_USD_2025)
    df["Var_EXP_Kg_24_25_Pct"]  = var_pct(df.EXP_Kg_2025,  df.EXP_Kg_2024)
    df["Var_EXP_Kg_25_26_Pct"]  = var_pct(df.EXP_Kg_2026,  df.EXP_Kg_2025)
    # linha total
    tot = {"Mes_Nome": "TOTAL Jan-Mai"}
    for ano in ANOS:
        for m in ["EXP_USD","IMP_USD","EXP_Kg"]:
            tot[f"{m}_{ano}"] = df[f"{m}_{ano}"].sum()
    for suf, a1, a2 in [("24_25",2024,2025),("25_26",2025,2026)]:
        for m in ["EXP_USD","IMP_USD","EXP_Kg"]:
            v1, v2 = tot[f"{m}_{a1}"], tot[f"{m}_{a2}"]
            tot[f"Var_{m}_{suf}_Pct"] = round((v2-v1)/abs(v1)*100, 1) if v1 else None
    return pd.concat([df, pd.DataFrame([tot])], ignore_index=True)[
        ["Mes_Nome",
         "EXP_USD_2024","EXP_USD_2025","Var_EXP_USD_24_25_Pct","EXP_USD_2026","Var_EXP_USD_25_26_Pct",
         "IMP_USD_2024","IMP_USD_2025","Var_IMP_USD_24_25_Pct","IMP_USD_2026","Var_IMP_USD_25_26_Pct",
         "EXP_Kg_2024","EXP_Kg_2025","Var_EXP_Kg_24_25_Pct","EXP_Kg_2026","Var_EXP_Kg_25_26_Pct"]]


def dm_mensal_setor():
    """Mensal por setor — 3 anos."""
    rows = []
    for setor, f_sc in SETORES.items():
        for mes in range(1, MAX_MES + 1):
            rec = {"Setor": setor, "Mes": mes, "Mes_Nome": MESES_NOME[mes]}
            for ano, src, uf_f, _ in PERIODOS:
                r = q(f"""
                    SELECT SUM(CASE WHEN tp_carga='EXP' THEN vl_fob          ELSE 0 END) AS EXP_USD,
                           SUM(CASE WHEN tp_carga='EXP' THEN qt_kilo_liquido ELSE 0 END) AS EXP_Kg
                    FROM {src}
                    WHERE nr_ano={ano} AND nr_mes={mes} AND {f_sc} AND {uf_f}
                """).iloc[0]
                rec[f"EXP_USD_{ano}"] = round(r.EXP_USD or 0, 0)
                rec[f"EXP_Kg_{ano}"]  = round(r.EXP_Kg  or 0, 0)
            rows.append(rec)
    df = pd.DataFrame(rows)
    df["Var_EXP_USD_24_25_Pct"] = var_pct(df.EXP_USD_2025, df.EXP_USD_2024)
    df["Var_EXP_USD_25_26_Pct"] = var_pct(df.EXP_USD_2026, df.EXP_USD_2025)
    df["Var_EXP_Kg_24_25_Pct"]  = var_pct(df.EXP_Kg_2025,  df.EXP_Kg_2024)
    df["Var_EXP_Kg_25_26_Pct"]  = var_pct(df.EXP_Kg_2026,  df.EXP_Kg_2025)
    return df.sort_values(["Setor","Mes"]).drop(columns="Mes")[
        ["Setor","Mes_Nome",
         "EXP_USD_2024","EXP_USD_2025","Var_EXP_USD_24_25_Pct","EXP_USD_2026","Var_EXP_USD_25_26_Pct",
         "EXP_Kg_2024","EXP_Kg_2025","Var_EXP_Kg_24_25_Pct","EXP_Kg_2026","Var_EXP_Kg_25_26_Pct"]]


def dm_top_produtos():
    """Top 35 produtos (rank por 2026) com dados dos 3 anos. Join por cd_ncm."""
    # base: top por 2026
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
    for ano, src, uf_f, ano_f in [(2025, f"read_parquet('{GOLD_SC}')", "TRUE", f"nr_ano=2025 AND nr_mes<={MAX_MES}"),
                                   (2024, f"read_parquet('{GOLD_SC}')", "TRUE", f"nr_ano=2024 AND nr_mes<={MAX_MES}")]:
        p = q(f"""
            SELECT cd_ncm,
                   {'ds_produto AS Produto,' if ano == 2025 else ''}
                   SUM(vl_fob) AS EXP_USD_{ano},
                   SUM(qt_kilo_liquido) AS EXP_Kg_{ano},
                   COUNT(DISTINCT ds_pais) AS Nr_Destinos_{ano}
            FROM {src}
            WHERE tp_carga='EXP' AND {ano_f} AND {COMPLEXO_FILTRO}
            GROUP BY cd_ncm {',' + 'Produto' if ano == 2025 else ''}
        """)
        p26 = p26.merge(p, on="cd_ncm", how="left").fillna(0)
    p26["Produto"] = p26["Produto"].replace("", np.nan).fillna(p26["cd_ncm"])
    for suf, a1, a2 in [("24_25", 2024, 2025), ("25_26", 2025, 2026)]:
        p26[f"Var_EXP_USD_{suf}_Pct"] = var_pct(p26[f"EXP_USD_{a2}"], p26[f"EXP_USD_{a1}"])
        p26[f"Var_EXP_Kg_{suf}_Pct"]  = var_pct(p26[f"EXP_Kg_{a2}"],  p26[f"EXP_Kg_{a1}"])
    for ano in ANOS:
        p26[f"Preco_Med_{ano}"] = (p26[f"EXP_USD_{ano}"] / p26[f"EXP_Kg_{ano}"].replace(0, np.nan)).round(2)
    p26["Var_Preco_24_25_Pct"] = var_pct(p26.Preco_Med_2025, p26.Preco_Med_2024)
    p26["Var_Preco_25_26_Pct"] = var_pct(p26.Preco_Med_2026, p26.Preco_Med_2025)
    p26["Rank_2026"] = range(1, len(p26) + 1)
    return p26[["Rank_2026","Produto","Setor",
                "EXP_USD_2024","EXP_USD_2025","Var_EXP_USD_24_25_Pct","EXP_USD_2026","Var_EXP_USD_25_26_Pct",
                "EXP_Kg_2024","EXP_Kg_2025","Var_EXP_Kg_24_25_Pct","EXP_Kg_2026","Var_EXP_Kg_25_26_Pct",
                "Preco_Med_2024","Preco_Med_2025","Var_Preco_24_25_Pct","Preco_Med_2026","Var_Preco_25_26_Pct",
                "Nr_Destinos_2024","Nr_Destinos_2025","Nr_Destinos_2026"]]


def dm_top_destinos():
    """Top 25 destinos (rank por 2026) com dados dos 3 anos."""
    d26 = q(f"""
        SELECT ds_pais AS Pais, SUM(vl_fob) AS EXP_USD_2026,
               SUM(qt_kilo_liquido) AS EXP_Kg_2026, COUNT(DISTINCT cd_ncm) AS Nr_NCMs_2026
        FROM v2026
        WHERE tp_carga='EXP' AND nr_ano=2026 AND sg_uf='SC' AND {COMPLEXO_FILTRO}
        GROUP BY Pais ORDER BY EXP_USD_2026 DESC LIMIT 25
    """)
    totais = {}
    for ano, src, uf_f, ano_f in PERIODOS:
        d = q(f"""
            SELECT ds_pais AS Pais, SUM(vl_fob) AS EXP_USD_{ano},
                   SUM(qt_kilo_liquido) AS EXP_Kg_{ano}, COUNT(DISTINCT cd_ncm) AS Nr_NCMs_{ano}
            FROM {src}
            WHERE tp_carga='EXP' AND {ano_f} AND {COMPLEXO_FILTRO} AND {uf_f}
            GROUP BY Pais
        """)
        totais[ano] = d[f"EXP_USD_{ano}"].sum()
        if ano != 2026:
            d26 = d26.merge(d, on="Pais", how="left")
    d26 = d26.fillna(0)
    for ano in ANOS:
        d26[f"Share_{ano}_Pct"] = (d26[f"EXP_USD_{ano}"] / totais[ano] * 100).round(2)
    for suf, a1, a2 in [("24_25",2024,2025),("25_26",2025,2026)]:
        d26[f"Var_Share_{suf}_pp"] = (d26[f"Share_{a2}_Pct"] - d26[f"Share_{a1}_Pct"]).round(2)
        d26[f"Var_EXP_{suf}_Pct"]  = var_pct(d26[f"EXP_USD_{a2}"], d26[f"EXP_USD_{a1}"])
    d26["Rank_2026"] = range(1, len(d26) + 1)
    return d26[["Rank_2026","Pais",
                "EXP_USD_2024","EXP_USD_2025","Var_EXP_24_25_Pct","EXP_USD_2026","Var_EXP_25_26_Pct",
                "Share_2024_Pct","Share_2025_Pct","Var_Share_24_25_pp","Share_2026_Pct","Var_Share_25_26_pp",
                "EXP_Kg_2024","EXP_Kg_2025","EXP_Kg_2026",
                "Nr_NCMs_2024","Nr_NCMs_2025","Nr_NCMs_2026"]]


def dm_eua():
    """Share EUA mês a mês — 3 anos."""
    rows = []
    for mes in range(1, MAX_MES + 1):
        rec = {"Mes_Nome": MESES_NOME[mes]}
        for ano, src, uf_f, _ in PERIODOS:
            r = q(f"""
                SELECT SUM(CASE WHEN ds_pais ILIKE '%Estados Unidos%' THEN vl_fob ELSE 0 END) AS EXP_EUA,
                       SUM(vl_fob) AS EXP_Total
                FROM {src}
                WHERE tp_carga='EXP' AND nr_ano={ano} AND nr_mes={mes} AND {COMPLEXO_FILTRO} AND {uf_f}
            """).iloc[0]
            rec[f"EXP_EUA_{ano}"]   = round(r.EXP_EUA   or 0, 0)
            rec[f"EXP_Total_{ano}"] = round(r.EXP_Total or 0, 0)
        rows.append(rec)
    df = pd.DataFrame(rows)
    for ano in ANOS:
        df[f"Share_EUA_{ano}_Pct"] = (df[f"EXP_EUA_{ano}"] / df[f"EXP_Total_{ano}"] * 100).round(2)
    for suf, a1, a2 in [("24_25",2024,2025),("25_26",2025,2026)]:
        df[f"Var_EXP_EUA_{suf}_Pct"]   = var_pct(df[f"EXP_EUA_{a2}"],   df[f"EXP_EUA_{a1}"])
        df[f"Var_Share_EUA_{suf}_pp"]   = (df[f"Share_EUA_{a2}_Pct"] - df[f"Share_EUA_{a1}_Pct"]).round(2)
    # total
    tot = {"Mes_Nome": "TOTAL Jan-Mai"}
    for ano in ANOS:
        tot[f"EXP_EUA_{ano}"]   = df[f"EXP_EUA_{ano}"].sum()
        tot[f"EXP_Total_{ano}"] = df[f"EXP_Total_{ano}"].sum()
        tot[f"Share_EUA_{ano}_Pct"] = round(tot[f"EXP_EUA_{ano}"] / tot[f"EXP_Total_{ano}"] * 100, 2) if tot[f"EXP_Total_{ano}"] else None
    for suf, a1, a2 in [("24_25",2024,2025),("25_26",2025,2026)]:
        e1, e2 = tot[f"EXP_EUA_{a1}"], tot[f"EXP_EUA_{a2}"]
        s1, s2 = tot[f"Share_EUA_{a1}_Pct"], tot[f"Share_EUA_{a2}_Pct"]
        tot[f"Var_EXP_EUA_{suf}_Pct"] = round((e2-e1)/abs(e1)*100, 1) if e1 else None
        tot[f"Var_Share_EUA_{suf}_pp"] = round(s2-s1, 2) if (s1 and s2) else None
    return pd.concat([df, pd.DataFrame([tot])], ignore_index=True)[
        ["Mes_Nome",
         "EXP_EUA_2024","EXP_EUA_2025","Var_EXP_EUA_24_25_Pct","EXP_EUA_2026","Var_EXP_EUA_25_26_Pct",
         "EXP_Total_2024","EXP_Total_2025","EXP_Total_2026",
         "Share_EUA_2024_Pct","Share_EUA_2025_Pct","Var_Share_EUA_24_25_pp",
         "Share_EUA_2026_Pct","Var_Share_EUA_25_26_pp"]]


def dm_participacao_sc_br():
    """Participação SC/Brasil por setor — 3 anos (Jan-Mai)."""
    rows = []
    for setor, f_sc in SETORES.items():
        for ano, src, uf_f, ano_f in PERIODOS:
            src_br = f"read_parquet('{GOLD_ALL}')" if ano < 2026 else "v2026"
            sc_exp = q(f"""
                SELECT SUM(vl_fob) AS v FROM {src}
                WHERE tp_carga='EXP' AND {ano_f} AND {f_sc} AND {uf_f}
            """).iloc[0, 0] or 0
            br_exp = q(f"""
                SELECT SUM(vl_fob) AS v FROM {src_br}
                WHERE tp_carga='EXP' AND {ano_f} AND {f_sc}
            """).iloc[0, 0] or 0
            rows.append({"Setor": setor, "Ano": ano,
                         "SC_EXP": round(sc_exp, 0), "BR_EXP": round(br_exp, 0),
                         "Part_Pct": round(sc_exp / br_exp * 100, 2) if br_exp else None})
    df = pd.DataFrame(rows)
    pv = {ano: df[df.Ano == ano].set_index("Setor")[["SC_EXP","BR_EXP","Part_Pct"]].copy() for ano in ANOS}
    for ano in ANOS:
        pv[ano].columns = [f"SC_EXP_{ano}", f"BR_EXP_{ano}", f"Part_Pct_{ano}"]
    out = pv[2024].join(pv[2025]).join(pv[2026]).reset_index()
    for suf, a1, a2 in [("24_25",2024,2025),("25_26",2025,2026)]:
        out[f"Var_SC_EXP_{suf}_Pct"] = var_pct(out[f"SC_EXP_{a2}"], out[f"SC_EXP_{a1}"])
        out[f"Var_BR_EXP_{suf}_Pct"] = var_pct(out[f"BR_EXP_{a2}"], out[f"BR_EXP_{a1}"])
        out[f"Var_Part_{suf}_pp"]     = (out[f"Part_Pct_{a2}"] - out[f"Part_Pct_{a1}"]).round(2)
    return out


def dm_ranking_estados():
    """Ranking SC entre estados exportadores por setor — 3 anos."""
    rows = []
    for setor, f_sc in SETORES.items():
        for ano, src, uf_f, ano_f in PERIODOS:
            src_br = f"read_parquet('{GOLD_ALL}')" if ano < 2026 else "v2026"
            df = q(f"""
                SELECT sg_uf AS UF, SUM(vl_fob) AS EXP_USD
                FROM {src_br}
                WHERE tp_carga='EXP' AND {ano_f} AND {f_sc}
                  AND sg_uf IS NOT NULL AND TRIM(sg_uf) != ''
                GROUP BY UF ORDER BY EXP_USD DESC
            """)
            tot = df.EXP_USD.sum()
            df["Share_Pct"] = (df.EXP_USD / tot * 100).round(2) if tot else 0
            df["Rank"] = range(1, len(df) + 1)
            df["Setor"] = setor; df["Ano"] = ano
            rows.append(df)
    all_df = pd.concat(rows, ignore_index=True)
    result = []
    for (setor, uf), grp in all_df.groupby(["Setor","UF"]):
        rec = {"Setor": setor, "UF": uf}
        for ano in ANOS:
            sub = grp[grp.Ano == ano]
            if len(sub):
                r = sub.iloc[0]
                rec[f"Rank_{ano}"]      = int(r.Rank)
                rec[f"EXP_USD_{ano}"]   = round(r.EXP_USD, 0)
                rec[f"Share_{ano}_Pct"] = r.Share_Pct
            else:
                rec[f"Rank_{ano}"] = None
                rec[f"EXP_USD_{ano}"] = 0
                rec[f"Share_{ano}_Pct"] = None
        result.append(rec)
    out = pd.DataFrame(result)
    for suf, a1, a2 in [("24_25",2024,2025),("25_26",2025,2026)]:
        out[f"Var_EXP_{suf}_Pct"] = var_pct(out[f"EXP_USD_{a2}"], out[f"EXP_USD_{a1}"])
        out[f"Var_Rank_{suf}"]    = out[f"Rank_{a1}"] - out[f"Rank_{a2}"]
    # top 8 por 2026 + SC sempre incluído
    top = []
    for setor, grp in out.groupby("Setor"):
        t  = grp.dropna(subset=["Rank_2026"]).nsmallest(8, "Rank_2026")
        sc = grp[grp.UF == "SC"]
        top.append(pd.concat([t, sc]).drop_duplicates("UF").sort_values("Rank_2026"))
    return pd.concat(top, ignore_index=True)[
        ["Setor","UF",
         "Rank_2024","EXP_USD_2024","Share_2024_Pct",
         "Rank_2025","EXP_USD_2025","Share_2025_Pct","Var_EXP_24_25_Pct","Var_Rank_24_25",
         "Rank_2026","EXP_USD_2026","Share_2026_Pct","Var_EXP_25_26_Pct","Var_Rank_25_26"]]


def dm_destinos_setor():
    """Top 15 destinos para todos os SETORES_CONC, com share % por ano."""
    out_all = []
    for setor, f_sc in SETORES_CONC.items():
        # coleta dados de todos os países nos 3 anos
        dfs_ano = {}
        totais_ano = {}
        for ano, src, uf_f, ano_f in PERIODOS:
            tot = q(f"""
                SELECT SUM(vl_fob) FROM {src}
                WHERE tp_carga='EXP' AND {ano_f} AND {f_sc} AND {uf_f}
            """).iloc[0, 0] or 0
            totais_ano[ano] = tot
            df = q(f"""
                SELECT ds_pais AS Pais, SUM(vl_fob) AS EXP_USD
                FROM {src}
                WHERE tp_carga='EXP' AND {ano_f} AND {f_sc} AND {uf_f}
                  AND ds_pais IS NOT NULL AND ds_pais NOT IN ('Outros','')
                GROUP BY Pais ORDER BY EXP_USD DESC
            """)
            df[f"EXP_{ano}"] = df.EXP_USD
            df[f"Share_{ano}_Pct"] = (df.EXP_USD / tot * 100).round(2) if tot else 0
            dfs_ano[ano] = df[["Pais", f"EXP_{ano}", f"Share_{ano}_Pct"]]

        # top 15 pelo ranking de 2026
        top15 = dfs_ano[2026].nlargest(15, f"EXP_{2026}")["Pais"].tolist()
        base = pd.DataFrame({"Pais": top15})
        for ano in ANOS:
            base = base.merge(dfs_ano[ano], on="Pais", how="left")
        base = base.fillna(0)
        base["Setor"] = setor
        out_all.append(base)

    out = pd.concat(out_all, ignore_index=True)
    out["Var_EXP_24_25_Pct"]   = var_pct(out.EXP_2025, out.EXP_2024)
    out["Var_EXP_25_26_Pct"]   = var_pct(out.EXP_2026, out.EXP_2025)
    out["Var_Share_24_25_pp"]  = (out.Share_2025_Pct - out.Share_2024_Pct).round(2)
    out["Var_Share_25_26_pp"]  = (out.Share_2026_Pct - out.Share_2025_Pct).round(2)
    return out[["Setor","Pais",
                "EXP_2024","Share_2024_Pct",
                "EXP_2025","Share_2025_Pct","Var_EXP_24_25_Pct","Var_Share_24_25_pp",
                "EXP_2026","Share_2026_Pct","Var_EXP_25_26_Pct","Var_Share_25_26_pp"]]


# ═══════════════════════════════════════════════════════════════════════════════
# HHI / GINI — Jan-Mai consistente nos 3 anos
# ═══════════════════════════════════════════════════════════════════════════════
PERIODOS_CONC = [
    ("Jan-Mai 2024", 2024, f"read_parquet('{GOLD_SC}')", "TRUE",       f"nr_ano=2024 AND nr_mes<={MAX_MES}"),
    ("Jan-Mai 2025", 2025, f"read_parquet('{GOLD_SC}')", "TRUE",       f"nr_ano=2025 AND nr_mes<={MAX_MES}"),
    ("Jan-Mai 2026", 2026, "v2026",                      "sg_uf='SC'", f"nr_ano=2026 AND nr_mes<={MAX_MES}"),
]


def dm_hhi_gini_resumo():
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
    out_rows = []
    for setor, grp in df.groupby("Setor"):
        r24 = grp[grp.Periodo.str.contains("2024")].iloc[0]
        r25 = grp[grp.Periodo.str.contains("2025")].iloc[0]
        r26 = grp[grp.Periodo.str.contains("2026")].iloc[0]
        out_rows.append({
            "Setor": setor,
            "Nr_Dest_2024": r24.Nr_Destinos, "HHI_2024": r24.HHI, "Gini_2024": r24.Gini,
            "Top1_Share_2024": r24.Top1_Share_Pct, "Top3_Share_2024": r24.Top3_Share_Pct,
            "Top5_Share_2024": r24.Top5_Share_Pct, "Top1_Pais_2024": r24.Top1_Pais,
            "Nr_Dest_2025": r25.Nr_Destinos, "HHI_2025": r25.HHI, "Gini_2025": r25.Gini,
            "Top1_Share_2025": r25.Top1_Share_Pct, "Top3_Share_2025": r25.Top3_Share_Pct,
            "Top5_Share_2025": r25.Top5_Share_Pct, "Top1_Pais_2025": r25.Top1_Pais,
            "Nr_Dest_2026": r26.Nr_Destinos, "HHI_2026": r26.HHI, "Gini_2026": r26.Gini,
            "Top1_Share_2026": r26.Top1_Share_Pct, "Top3_Share_2026": r26.Top3_Share_Pct,
            "Top5_Share_2026": r26.Top5_Share_Pct, "Top1_Pais_2026": r26.Top1_Pais,
            "Var_HHI_24_25":  round(r25.HHI - r24.HHI, 1)  if (r25.HHI  and r24.HHI)  else None,
            "Var_HHI_25_26":  round(r26.HHI - r25.HHI, 1)  if (r26.HHI  and r25.HHI)  else None,
            "Var_Gini_24_25": round(r25.Gini - r24.Gini, 4) if (r25.Gini and r24.Gini) else None,
            "Var_Gini_25_26": round(r26.Gini - r25.Gini, 4) if (r26.Gini and r25.Gini) else None,
            "Var_Dest_24_25": r25.Nr_Destinos - r24.Nr_Destinos,
            "Var_Dest_25_26": r26.Nr_Destinos - r25.Nr_Destinos,
            # interpretação baseada nos limites do DOJ (< 1500 = baixa; 1500-2500 = moderada; > 2500 = alta)
            "Interp_2024": interpreta_hhi(r24.HHI),
            "Interp_2025": interpreta_hhi(r25.HHI),
            "Interp_2026": interpreta_hhi(r26.HHI),
        })
    return pd.DataFrame(out_rows)


def dm_hhi_gini_longo():
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
    """Share dos top 20 países (por 2025) nos 3 anos Jan-Mai."""
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
        df["Ano"] = ano
        rows_all.append(df)
    all_df = pd.concat(rows_all, ignore_index=True)
    top20 = (all_df[all_df.Ano == 2025]
             .sort_values("EXP_USD", ascending=False)
             .head(20)["Pais"].tolist())
    filt = all_df[all_df.Pais.isin(top20)].copy()
    dfs = {}
    for ano in ANOS:
        dfs[ano] = filt[filt.Ano == ano][["Pais","EXP_USD","Share_Pct"]].rename(
            columns={"EXP_USD": f"EXP_{ano}", "Share_Pct": f"Share_{ano}_Pct"})
    out = dfs[2025].merge(dfs[2024], on="Pais", how="outer").merge(dfs[2026], on="Pais", how="outer").fillna(0)
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
    """Top 15 países por setor nos 3 períodos Jan-Mai."""
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
            df["Setor"] = setor; df["Periodo"] = label; df["Rank"] = range(1, len(df)+1)
            rows.append(df)
    return pd.concat(rows, ignore_index=True)[["Setor","Periodo","Rank","Pais","EXP_USD","Share_Pct"]]


def dm_hhi_decomposicao():
    """
    Decomposição do HHI por país — mostra a contribuição individual de cada destino
    ao índice de concentração (HHI_Contrib = share_pct²).

    HHI total = Σ(share_i%)²  →  cada linha mostra quanto aquele país "pesa" no HHI.
    Linha final de cada bloco (HHI TOTAL) fecha a conta e confirma o índice.
    """
    rows = []
    for setor, f_sc in SETORES_CONC.items():
        for label, ano, fonte, uf_f, ano_f in PERIODOS_CONC:
            # todos os países (sem LIMIT) para somar 100% do HHI
            df = q(f"""
                SELECT ds_pais AS Pais, SUM(vl_fob) AS EXP_USD
                FROM {fonte}
                WHERE tp_carga='EXP' AND {ano_f} AND {f_sc} AND {uf_f}
                  AND ds_pais IS NOT NULL AND ds_pais NOT IN ('Outros','')
                GROUP BY Pais ORDER BY EXP_USD DESC
            """)
            if df.empty:
                continue
            tot = df.EXP_USD.sum()
            df["Share_Pct"]   = (df.EXP_USD / tot * 100).round(4)
            df["HHI_Contrib"] = (df.Share_Pct ** 2).round(1)  # contribuição individual ao HHI
            n_total = len(df)

            # top 15 + bloco "Outros"
            top15  = df.head(15).copy()
            outros = df.iloc[15:] if len(df) > 15 else pd.DataFrame()

            for rank, row in enumerate(top15.itertuples(index=False), 1):
                rows.append({
                    "Setor": setor, "Periodo": label,
                    "Rank": rank, "Pais": row.Pais,
                    "EXP_USD": round(row.EXP_USD, 0),
                    "Share_Pct": round(row.Share_Pct, 2),
                    "HHI_Contrib": round(row.HHI_Contrib, 1),
                })

            if not outros.empty:
                outros_exp   = outros.EXP_USD.sum()
                outros_share = outros.Share_Pct.sum()
                outros_hhi   = outros.HHI_Contrib.sum()
                rows.append({
                    "Setor": setor, "Periodo": label,
                    "Rank": 16,
                    "Pais": f"Outros ({len(outros)} paises)",
                    "EXP_USD": round(outros_exp, 0),
                    "Share_Pct": round(outros_share, 2),
                    "HHI_Contrib": round(outros_hhi, 1),
                })

            # linha de total — fecha o HHI
            hhi_total = round(df.HHI_Contrib.sum(), 1)
            rows.append({
                "Setor": setor, "Periodo": label,
                "Rank": 999,
                "Pais": f"HHI TOTAL ({n_total} paises)",
                "EXP_USD": round(tot, 0),
                "Share_Pct": 100.0,
                "HHI_Contrib": hhi_total,
            })

    return pd.DataFrame(rows)[["Setor","Periodo","Rank","Pais","EXP_USD","Share_Pct","HHI_Contrib"]]


# ═══════════════════════════════════════════════════════════════════════════════
# EXCEL BUILDER
# ═══════════════════════════════════════════════════════════════════════════════
def detect_fmt(col):
    c = col.lower()
    if "gini" in c:
        return "dec4"
    if "hhi" in c:
        return "hhi"
    if any(k in c for k in ["interp","pais_","top1_p"]):
        return "text"
    if any(k in c for k in ["var_","_pct","_pp","share","part_","24_25","25_26"]):
        return "pct"
    if any(k in c for k in ["usd","exp_","imp_","saldo","eua_","total_","sc_exp","br_exp",
                             "_2024","_2025","_2026","preco_med"]):
        return "num"
    if "kg" in c:
        return "num"
    if any(k in c for k in ["rank","nr_dest","nr_ncm","nr_dest_"]):
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
                    ws.write(ri+2, ci, int(val) if not pd.isna(val) else "", F["int_e"] if even else F["int"])
            else:
                ws.write(ri+2, ci, val, F["text_e"] if even else F["text"])
    ws.freeze_panes(2, freeze_cols)


def build_excel(dms):
    with pd.ExcelWriter(OUT, engine="xlsxwriter",
                        engine_kwargs={"options": {"nan_inf_to_errors": True}}) as writer:
        wb = writer.book

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
            "SEAFLOR 2026 — Complexo Florestal SC: Comparativo Jan-Mai 2024 | 2025 | 2026",
            Fi["tit"])
        ws_idx.merge_range("B3:C3",
            "Fonte: ComexStat/MDIC | Observatorio FIESC | Junho 2026", Fi["sub"])
        ws_idx.merge_range("B4:C4",
            "Nota: Complexo = cd_cgce_n3 IN (2,16,17,31). "
            "HHI/Gini calculados sobre Jan-Mai dos 3 anos para comparacao metodologicamente consistente.", Fi["sub"])
        ws_idx.write("B6", "Aba", Fi["hdr"])
        ws_idx.write("C6", "Descricao", Fi["hdr"])
        for i, (nome, (titulo, _, tag)) in enumerate(dms.items()):
            f_aba = Fi["aba2"] if tag == "conc" else Fi["aba"]
            ws_idx.write(6+i, 1, nome, f_aba)
            ws_idx.write(6+i, 2, titulo, Fi["dsc_e"] if i%2==0 else Fi["dsc"])

        for nome, (titulo, df, _) in dms.items():
            ws = wb.add_worksheet(nome)
            writer.sheets[nome] = ws
            fc = 2 if any(c in df.columns for c in ["Setor","Pais","Produto","UF"]) else 1
            write_sheet(ws, df, wb, titulo, freeze_cols=fc)
            print(f"  {nome}: {df.shape[0]}L x {df.shape[1]}C")

    return OUT


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("Construindo SEAFLOR_2026_JanMai_3anos.xlsx...")

    print("  [1/14] Resumo geral 3 anos...")
    resumo = dm_resumo()

    print("  [2/14] Mensal total complexo 3 anos...")
    mensal_total = dm_mensal_total()

    print("  [3/14] Mensal por setor 3 anos...")
    mensal_setor = dm_mensal_setor()

    print("  [4/14] Top produtos 3 anos (join cd_ncm)...")
    top_prod = dm_top_produtos()

    print("  [5/14] Top destinos 3 anos...")
    top_dest = dm_top_destinos()

    print("  [6/14] Concentracao EUA 3 anos...")
    eua = dm_eua()

    print("  [7/14] Participacao SC/Brasil 3 anos...")
    part = dm_participacao_sc_br()

    print("  [8/14] Ranking estados 3 anos...")
    rank = dm_ranking_estados()

    print("  [9/14] Destinos por setor — todos os setores com share % ...")
    dest_setor = dm_destinos_setor()

    print("  [10/14] HHI e Gini Jan-Mai 2024|2025|2026 + interpretacao...")
    hhi_gini_res = dm_hhi_gini_resumo()

    print("  [11/14] HHI e Gini formato longo...")
    hhi_gini_lng = dm_hhi_gini_longo()

    print("  [12/14] Share por pais evolucao Jan-Mai 3 anos...")
    share_pais = dm_share_pais_evolucao()

    print("  [13/14] Detalhe destinos por setor 3 periodos...")
    detalhe_dest = dm_hhi_gini_por_setor_detalhe()

    print("  [14/14] Decomposicao HHI por pais (contribuicao individual)...")
    hhi_decomp = dm_hhi_decomposicao()

    con.close()

    dms = {
        "1_Resumo_Geral":    ("1. Resumo por Setor — EXP/IMP/Saldo/Kg/Destinos/NCMs | Jan-Mai 2024 vs 2025 vs 2026", resumo, "base"),
        "2_Mensal_Total":    ("2. Comparativo Mensal — Complexo Florestal SC | Jan-Mai 2024 | 2025 | 2026", mensal_total, "base"),
        "3_Mensal_Setor":    ("3. Mensal por Setor e CNAE — EXP SC | Jan-Mai 2024 | 2025 | 2026", mensal_setor, "base"),
        "4_Top_Produtos":    ("4. Top 35 Produtos (rank 2026) — Valor, Volume, Preco Medio | Jan-Mai 3 anos | join NCM", top_prod, "base"),
        "5_Top_Destinos":    ("5. Top 25 Destinos (rank 2026) — EXP Florestais SC | Jan-Mai 2024 | 2025 | 2026", top_dest, "base"),
        "6_Conc_EUA":        ("6. Concentracao EUA — Share nas EXP Florestais SC Mes a Mes | Jan-Mai 2024 | 2025 | 2026", eua, "base"),
        "7_Part_SC_BR":      ("7. Participacao SC no Brasil por Setor — Jan-Mai 2024 | 2025 | 2026", part, "base"),
        "8_Rank_Estados":    ("8. Ranking SC entre Estados Exportadores por Setor | Jan-Mai 2024 | 2025 | 2026", rank, "base"),
        "9_Dest_Setor":      ("9. Top 15 Destinos por Setor (todos) + Share % | Jan-Mai 2024 | 2025 | 2026", dest_setor, "base"),
        "10_HHI_Gini":       ("10. HHI e Gini — Concentracao Jan-Mai 2024|2025|2026 + Interpretacao (limites DOJ)", hhi_gini_res, "conc"),
        "10b_HHI_Decomp":    ("10b. Decomposicao HHI por Pais — Contribuicao Individual ao Indice (Share%^2) | todos setores", hhi_decomp, "conc"),
        "11_HHI_Gini_Longo": ("11. HHI e Gini — Formato Longo por Setor e Periodo (base grafico)", hhi_gini_lng, "conc"),
        "12_Share_Pais":     ("12. Share por Pais — Evolucao Jan-Mai 2024|2025|2026: Ganhadores e Perdedores", share_pais, "conc"),
        "13_Dest_Detalhe":   ("13. Top 15 Destinos por Setor — Jan-Mai 2024|2025|2026 (base Lorenz)", detalhe_dest, "conc"),
    }

    excel = build_excel(dms)
    print(f"\nArquivo: {excel}")
    print(f"Tamanho: {excel.stat().st_size / 1024:.0f} KB")
