"""
Planilha de suporte — Estimativa de Perda de Receita de Exportação
Complexo Florestal SC | Impacto tarifário EUA 2025-2026

Metodologia:
  Destruição bruta  = EXP_EUA_jan-mai/2025 − EXP_EUA_jan-mai/2026
  Desvio de comércio = Δ EXP outros mercados (jan-mai 2025 vs 2026)
  Destruição líquida = Destruição bruta − Desvio
  Prêmio EUA        = Valor_unitário_EUA − Valor_unitário_Outros (USD/kg)
  Efeito-preço      = Volume desviado (kg) × Prêmio EUA
  Perda total       = Destruição líquida + Efeito-preço

Cenários contrafactuais:
  A — baseline = share EUA em Jan-Mai 2025 (39,2%)  [conservador]
  B — baseline = share EUA em 2024 ano fechado (41,0%) [base]
"""
import duckdb
import pandas as pd
import numpy as np
from pathlib import Path

ROOT       = Path(r"c:\Users\bruno.haeming\Desktop\Demandas\OBS - SEAFLOR MURARA")
BRONZE_EXP = str(ROOT / r"referencia\Dados\bronze\EXP\EXP_2026.csv")
BRONZE_IMP = str(ROOT / r"referencia\Dados\bronze\IMP\IMP_2026.csv")
GOLD_SC    = str(ROOT / r"referencia\Dados\gold\comexstat_ncm_sc.parquet")
NCM_DICT   = str(ROOT / r"referencia\Dados\silver\DICT\NCM_SH4 - atualizado 07.04.2026.xlsx")
PAIS_CSV   = str(ROOT / r"referencia\Dados\silver\DICT\PAIS.csv")
OUT        = ROOT / "data" / "processed" / "SEAFLOR_2026_Perda_Estimada.xlsx"

MAX_MES = 5
COMPLEXO = "cd_cgce_n3 IN ('2','16','17','31')"
SETORES  = {
    "Complexo Florestal":         "cd_cgce_n3 IN ('2','16','17','31')",
    "Madeira (CNAE 16)":          "sc_competitiva='Madeira e Móveis' AND cd_cgce_n3='16'",
    "Moveis (CNAE 31)":           "sc_competitiva='Madeira e Móveis' AND cd_cgce_n3='31'",
    "Madeira e Moveis (16+31)":   "sc_competitiva='Madeira e Móveis' AND cd_cgce_n3 IN ('16','31')",
    "Papel e Celulose (CNAE 17)": "sc_competitiva='Papel e Celulose' AND cd_cgce_n3='17'",
    "Base Florestal (CNAE 2)":    "sc_competitiva='Produção Florestal' AND cd_cgce_n3='2'",
}

AZUL_ESC = "1F4E79"; AZUL_MED = "2E75B6"; AZUL_CL = "DEEAF1"
VERDE = "375623"; VERMELHO = "C00000"; BRANCO = "FFFFFF"
CINZA = "595959"; LARANJA = "ED7D31"; AMARELO = "FFD966"

con = duckdb.connect()
ncm_df = pd.read_excel(NCM_DICT, dtype=str)
ncm_df.columns = [c.strip() for c in ncm_df.columns]
cod_col = [c for c in ncm_df.columns if "NCM" in c.upper() and "8" in c][0]
ncm_df = ncm_df.rename(columns={cod_col:"cd_ncm","SC Competitiva":"sc_competitiva",
                                  "CNAE divisão":"cd_cgce_n3","NO_NCM_POR":"ds_produto"})
ncm_df["cd_ncm"] = ncm_df["cd_ncm"].astype(str).str.strip()
ncm_df["cd_cgce_n3"] = (pd.to_numeric(ncm_df["cd_cgce_n3"],errors="coerce")
                         .fillna(0).astype(int).astype(str).replace("0",""))
con.register("ncm_dim", ncm_df)
pais_df = pd.read_csv(PAIS_CSV, sep=";", encoding="latin-1", dtype=str)
pais_df.columns = [c.strip() for c in pais_df.columns]
pais_df = pais_df.rename(columns={"CO_PAIS":"co_pais","NO_PAIS":"ds_pais"})
pais_df["co_pais"] = pais_df["co_pais"].astype(str).str.strip()
con.register("pais_dim", pais_df)

con.execute(f"""
CREATE OR REPLACE VIEW v2026 AS
WITH raw AS (
    SELECT CAST(CO_ANO AS INTEGER) AS nr_ano, CAST(CO_MES AS INTEGER) AS nr_mes,
           CAST(CO_NCM AS VARCHAR) AS cd_ncm, CAST(CO_PAIS AS VARCHAR) AS co_pais,
           CAST(SG_UF_NCM AS VARCHAR) AS sg_uf, CAST(VL_FOB AS DOUBLE) AS vl_fob,
           CAST(KG_LIQUIDO AS DOUBLE) AS qt_kilo_liquido, 'EXP' AS tp_carga
    FROM read_csv_auto('{BRONZE_EXP}', sep=';', ignore_errors=true)
    WHERE CAST(CO_MES AS INTEGER) BETWEEN 1 AND {MAX_MES}
    UNION ALL
    SELECT CAST(CO_ANO AS INTEGER), CAST(CO_MES AS INTEGER), CAST(CO_NCM AS VARCHAR),
           CAST(CO_PAIS AS VARCHAR), CAST(SG_UF_NCM AS VARCHAR),
           CAST(VL_FOB AS DOUBLE), CAST(KG_LIQUIDO AS DOUBLE), 'IMP'
    FROM read_csv_auto('{BRONZE_IMP}', sep=';', ignore_errors=true)
    WHERE CAST(CO_MES AS INTEGER) BETWEEN 1 AND {MAX_MES}
)
SELECT r.*, COALESCE(n.sc_competitiva,'Outros') AS sc_competitiva,
       COALESCE(CAST(n.cd_cgce_n3 AS VARCHAR),'') AS cd_cgce_n3,
       COALESCE(n.ds_produto, r.cd_ncm) AS ds_produto,
       COALESCE(p.ds_pais,'Outros') AS ds_pais
FROM raw r
LEFT JOIN ncm_dim n ON r.cd_ncm = n.cd_ncm
LEFT JOIN pais_dim p ON r.co_pais = p.co_pais
""")

def q(sql): return con.execute(sql).fetchdf()

# ─── 1. Decomposição destruição / desvio / líquida ──────────────────────────
def dm_decomposicao():
    rows = []
    for setor, f in SETORES.items():
        eua_pais = "ds_pais='Estados Unidos'"
        eua26    = "ds_pais ILIKE '%Estados Unidos%'"

        r25 = q(f"""
            SELECT
              SUM(CASE WHEN {eua_pais}  THEN vl_fob ELSE 0 END) AS exp_eua,
              SUM(CASE WHEN NOT ({eua_pais}) THEN vl_fob ELSE 0 END) AS exp_outros,
              SUM(vl_fob) AS exp_total,
              SUM(CASE WHEN {eua_pais} THEN qt_kilo_liquido ELSE 0 END) AS kg_eua,
              SUM(CASE WHEN NOT ({eua_pais}) THEN qt_kilo_liquido ELSE 0 END) AS kg_outros
            FROM read_parquet('{GOLD_SC}')
            WHERE tp_carga='EXP' AND nr_ano=2025 AND nr_mes<={MAX_MES} AND {f}
        """).iloc[0]

        r26 = q(f"""
            SELECT
              SUM(CASE WHEN {eua26}  THEN vl_fob ELSE 0 END) AS exp_eua,
              SUM(CASE WHEN NOT ({eua26}) THEN vl_fob ELSE 0 END) AS exp_outros,
              SUM(vl_fob) AS exp_total,
              SUM(CASE WHEN {eua26} THEN qt_kilo_liquido ELSE 0 END) AS kg_eua,
              SUM(CASE WHEN NOT ({eua26}) THEN qt_kilo_liquido ELSE 0 END) AS kg_outros
            FROM v2026
            WHERE tp_carga='EXP' AND nr_ano=2026 AND sg_uf='SC' AND {f}
        """).iloc[0]

        exp_eua_25   = r25.exp_eua   or 0
        exp_eua_26   = r26.exp_eua   or 0
        exp_out_25   = r25.exp_outros or 0
        exp_out_26   = r26.exp_outros or 0
        exp_tot_25   = r25.exp_total  or 0
        exp_tot_26   = r26.exp_total  or 0
        kg_eua_25    = r25.kg_eua     or 0
        kg_outros_25 = r25.kg_outros  or 0
        kg_outros_26 = r26.kg_outros  or 0

        destruct_bruta  = exp_eua_25  - exp_eua_26
        desvio          = exp_out_26  - exp_out_25
        destruct_liq    = destruct_bruta - max(desvio, 0)

        # prêmio de preço EUA vs outros mercados (2025 como referência)
        vu_eua_25   = (exp_eua_25   / kg_eua_25   ) if kg_eua_25   > 0 else None
        vu_outros_25= (exp_out_25   / kg_outros_25 ) if kg_outros_25> 0 else None
        premio_vu   = (vu_eua_25 - vu_outros_25) if (vu_eua_25 and vu_outros_25) else None

        # efeito-preço: volume desviado (kg outros 2026 - kg outros 2025) × prêmio
        delta_kg_outros = max(kg_outros_26 - kg_outros_25, 0)
        efeito_preco = (delta_kg_outros * premio_vu) if premio_vu and premio_vu > 0 else 0

        perda_total = destruct_liq + efeito_preco

        # contrafactual B: share 2024
        r24 = q(f"""
            SELECT SUM(CASE WHEN {eua_pais} THEN vl_fob ELSE 0 END) / SUM(vl_fob) AS share_eua
            FROM read_parquet('{GOLD_SC}')
            WHERE tp_carga='EXP' AND nr_ano=2024 AND {f}
        """).iloc[0]
        share_24 = r24.share_eua or 0
        ctf_b_exp_eua = exp_tot_26 * share_24
        perda_ctf_b   = ctf_b_exp_eua - exp_eua_26

        rows.append({
            "Setor": setor,
            # observados
            "EXP_EUA_janmai_2025":    round(exp_eua_25, 0),
            "EXP_EUA_janmai_2026":    round(exp_eua_26, 0),
            "EXP_Outros_janmai_2025": round(exp_out_25, 0),
            "EXP_Outros_janmai_2026": round(exp_out_26, 0),
            "EXP_Total_janmai_2025":  round(exp_tot_25, 0),
            "EXP_Total_janmai_2026":  round(exp_tot_26, 0),
            "Share_EUA_2025_Pct":     round(exp_eua_25/exp_tot_25*100, 2) if exp_tot_25 else None,
            "Share_EUA_2026_Pct":     round(exp_eua_26/exp_tot_26*100, 2) if exp_tot_26 else None,
            # decomposição
            "I_Destruicao_Bruta_USD": round(destruct_bruta, 0),
            "II_Desvio_Comercio_USD": round(max(desvio, 0), 0),
            "III_Destruicao_Liquida_USD": round(destruct_liq, 0),
            # efeito-preço
            "VU_EUA_2025_USD_kg":     round(vu_eua_25, 4)    if vu_eua_25    else None,
            "VU_Outros_2025_USD_kg":  round(vu_outros_25, 4) if vu_outros_25 else None,
            "Premio_EUA_USD_kg":      round(premio_vu, 4)     if premio_vu    else None,
            "IV_Efeito_Preco_USD":    round(efeito_preco, 0),
            # perda total (metodologia A = base 2025)
            "Perda_Total_MetA_USD":   round(perda_total, 0),
            # contrafactual B (base 2024)
            "Share_EUA_2024_Pct":     round(share_24*100, 2),
            "CTF_B_EXP_EUA_USD":      round(ctf_b_exp_eua, 0),
            "Perda_Total_MetB_USD":   round(perda_ctf_b, 0),
        })
    return pd.DataFrame(rows)


# ─── 2. Mensal do Complexo Florestal ────────────────────────────────────────
def dm_mensal_perda():
    MESES = {1:"Jan",2:"Fev",3:"Mar",4:"Abr",5:"Mai"}
    rows = []
    for mes in range(1, MAX_MES+1):
        r25 = q(f"""
            SELECT SUM(CASE WHEN ds_pais='Estados Unidos' THEN vl_fob ELSE 0 END) AS eua,
                   SUM(CASE WHEN ds_pais!='Estados Unidos' THEN vl_fob ELSE 0 END) AS outros,
                   SUM(vl_fob) AS total,
                   SUM(CASE WHEN ds_pais='Estados Unidos' THEN qt_kilo_liquido ELSE 0 END) AS kg_eua,
                   SUM(CASE WHEN ds_pais!='Estados Unidos' THEN qt_kilo_liquido ELSE 0 END) AS kg_outros
            FROM read_parquet('{GOLD_SC}')
            WHERE tp_carga='EXP' AND nr_ano=2025 AND nr_mes={mes} AND {COMPLEXO}
        """).iloc[0]
        r26 = q(f"""
            SELECT SUM(CASE WHEN ds_pais ILIKE '%Estados Unidos%' THEN vl_fob ELSE 0 END) AS eua,
                   SUM(CASE WHEN NOT(ds_pais ILIKE '%Estados Unidos%') THEN vl_fob ELSE 0 END) AS outros,
                   SUM(vl_fob) AS total,
                   SUM(CASE WHEN ds_pais ILIKE '%Estados Unidos%' THEN qt_kilo_liquido ELSE 0 END) AS kg_eua,
                   SUM(CASE WHEN NOT(ds_pais ILIKE '%Estados Unidos%') THEN qt_kilo_liquido ELSE 0 END) AS kg_outros
            FROM v2026
            WHERE tp_carga='EXP' AND nr_ano=2026 AND nr_mes={mes} AND sg_uf='SC' AND {COMPLEXO}
        """).iloc[0]

        eua25=r25.eua or 0; out25=r25.outros or 0; tot25=r25.total or 0
        eua26=r26.eua or 0; out26=r26.outros or 0; tot26=r26.total or 0
        dest_bruta = eua25 - eua26
        desvio     = max(out26 - out25, 0)
        dest_liq   = dest_bruta - desvio

        vu_eua25   = (eua25/(r25.kg_eua or 1)) if r25.kg_eua else None
        vu_out25   = (out25/(r25.kg_outros or 1)) if r25.kg_outros else None
        premio     = (vu_eua25 - vu_out25) if (vu_eua25 and vu_out25) else 0
        delta_kg   = max((r26.kg_outros or 0) - (r25.kg_outros or 0), 0)
        ef_preco   = delta_kg * premio if premio > 0 else 0

        rows.append({
            "Mes": MESES[mes],
            "EXP_EUA_2025": round(eua25,0), "EXP_EUA_2026": round(eua26,0),
            "Var_EXP_EUA_Pct": round((eua26-eua25)/abs(eua25)*100,1) if eua25 else None,
            "Share_EUA_2025_Pct": round(eua25/tot25*100,2) if tot25 else None,
            "Share_EUA_2026_Pct": round(eua26/tot26*100,2) if tot26 else None,
            "EXP_Total_2025": round(tot25,0), "EXP_Total_2026": round(tot26,0),
            "Destr_Bruta_USD": round(dest_bruta,0),
            "Desvio_USD":      round(desvio,0),
            "Destr_Liq_USD":   round(dest_liq,0),
            "Efeito_Preco_USD":round(ef_preco,0),
            "Perda_Total_USD": round(dest_liq+ef_preco,0),
        })
    df = pd.DataFrame(rows)
    # total
    num_cols = [c for c in df.columns if c != "Mes"]
    tot = df[num_cols].sum()
    tot["Mes"] = "TOTAL Jan-Mai"
    tot["Var_EXP_EUA_Pct"] = round((tot["EXP_EUA_2026"]-tot["EXP_EUA_2025"])/abs(tot["EXP_EUA_2025"])*100,1)
    tot["Share_EUA_2025_Pct"] = round(tot["EXP_EUA_2025"]/tot["EXP_Total_2025"]*100,2)
    tot["Share_EUA_2026_Pct"] = round(tot["EXP_EUA_2026"]/tot["EXP_Total_2026"]*100,2)
    return pd.concat([df, tot.to_frame().T[df.columns]], ignore_index=True)


# ─── 3. Valor unitário EUA vs outros — por setor e ano ──────────────────────
def dm_valor_unitario():
    rows = []
    eua_f = "ds_pais='Estados Unidos'"
    for setor, f in SETORES.items():
        for ano, src, uf_f in [
            (2024, f"read_parquet('{GOLD_SC}')", "TRUE"),
            (2025, f"read_parquet('{GOLD_SC}')", "TRUE"),
            (2026, "v2026", "sg_uf='SC'"),
        ]:
            mes_f  = f"nr_mes<={MAX_MES}" if ano==2026 else "TRUE"
            eua_q  = "ds_pais ILIKE '%Estados Unidos%'" if ano==2026 else eua_f
            r = q(f"""
                SELECT
                  SUM(CASE WHEN {eua_q} THEN vl_fob ELSE 0 END) AS exp_eua,
                  SUM(CASE WHEN {eua_q} THEN qt_kilo_liquido ELSE 0 END) AS kg_eua,
                  SUM(CASE WHEN NOT({eua_q}) THEN vl_fob ELSE 0 END) AS exp_outros,
                  SUM(CASE WHEN NOT({eua_q}) THEN qt_kilo_liquido ELSE 0 END) AS kg_outros
                FROM {src}
                WHERE tp_carga='EXP' AND nr_ano={ano} AND {mes_f} AND {f} AND {uf_f}
            """).iloc[0]
            vu_eua   = (r.exp_eua   / r.kg_eua   ) if (r.kg_eua    or 0) > 0 else None
            vu_out   = (r.exp_outros/ r.kg_outros ) if (r.kg_outros or 0) > 0 else None
            premio   = (vu_eua - vu_out) if (vu_eua and vu_out) else None
            periodo  = "2024 (ano)" if ano==2024 else ("2025 (ano)" if ano==2025 else "2026 (Jan-Mai)")
            rows.append({
                "Setor": setor, "Periodo": periodo,
                "VU_EUA_USD_kg":    round(vu_eua,  4) if vu_eua  else None,
                "VU_Outros_USD_kg": round(vu_out,  4) if vu_out  else None,
                "Premio_EUA_USD_kg":round(premio,  4) if premio  else None,
                "Premio_Pct":       round(premio/vu_out*100,1) if (premio and vu_out) else None,
                "EXP_EUA_USD":      round(r.exp_eua   or 0, 0),
                "EXP_Outros_USD":   round(r.exp_outros or 0, 0),
            })
    return pd.DataFrame(rows)


# ─── 4. Cenários contrafactuais consolidados ─────────────────────────────────
def dm_contrafactual():
    """
    Para o Complexo Florestal, três cenários de receita foregone:
      A: baseline share EUA = Jan-Mai 2025 observado
      B: baseline share EUA = 2024 ano fechado
      C: baseline = 2023 ano fechado (pré-ciclo Trump)
    Aplicados ao volume total exportado Jan-Mai 2026.
    """
    rows = []
    for setor, f in SETORES.items():
        # total exportado jan-mai 2026
        tot26 = q(f"""SELECT SUM(vl_fob) AS v FROM v2026
                      WHERE tp_carga='EXP' AND nr_ano=2026 AND sg_uf='SC' AND {f}
                   """).iloc[0, 0] or 0
        eua26 = q(f"""SELECT SUM(vl_fob) AS v FROM v2026
                      WHERE tp_carga='EXP' AND nr_ano=2026 AND sg_uf='SC'
                        AND ds_pais ILIKE '%Estados Unidos%' AND {f}
                   """).iloc[0, 0] or 0

        def get_share(ano):
            r = q(f"""
                SELECT SUM(CASE WHEN ds_pais='Estados Unidos' THEN vl_fob ELSE 0 END)
                     / NULLIF(SUM(vl_fob),0) AS sh
                FROM read_parquet('{GOLD_SC}')
                WHERE tp_carga='EXP' AND nr_ano={ano} AND {f}
            """).iloc[0, 0]
            return r or 0

        def get_share_janmai(ano):
            r = q(f"""
                SELECT SUM(CASE WHEN ds_pais='Estados Unidos' THEN vl_fob ELSE 0 END)
                     / NULLIF(SUM(vl_fob),0) AS sh
                FROM read_parquet('{GOLD_SC}')
                WHERE tp_carga='EXP' AND nr_ano={ano} AND nr_mes<={MAX_MES} AND {f}
            """).iloc[0, 0]
            return r or 0

        sh_A = get_share_janmai(2025)
        sh_B = get_share(2024)
        sh_C = get_share(2023)

        for label, sh in [
            ("A — Baseline Jan-Mai 2025 (conservador)", sh_A),
            ("B — Baseline 2024 ano fechado (base)",    sh_B),
            ("C — Baseline 2023 ano fechado (estrutural)", sh_C),
        ]:
            ctf_eua  = tot26 * sh
            foregone = ctf_eua - eua26
            rows.append({
                "Setor": setor, "Cenario": label,
                "Share_EUA_Baseline_Pct":   round(sh*100, 2),
                "EXP_Total_real_26_USD":     round(tot26, 0),
                "EXP_EUA_real_26_USD":       round(eua26, 0),
                "EXP_EUA_Share_real_26_Pct": round(eua26/tot26*100, 2) if tot26 else None,
                "EXP_EUA_Contrafactual_USD": round(ctf_eua, 0),
                "Receita_Foregone_USD":      round(foregone, 0),
                "Receita_Foregone_Pct_Total":round(foregone/tot26*100, 2) if tot26 else None,
            })
    return pd.DataFrame(rows)


# ─── 5. Desvio de comércio — ganhadores ──────────────────────────────────────
def dm_desvio_ganhadores():
    d25 = q(f"""
        SELECT ds_pais AS Pais, SUM(vl_fob) AS EXP_2025,
               SUM(qt_kilo_liquido) AS Kg_2025
        FROM read_parquet('{GOLD_SC}')
        WHERE tp_carga='EXP' AND nr_ano=2025 AND nr_mes<={MAX_MES}
          AND ds_pais != 'Estados Unidos' AND {COMPLEXO}
        GROUP BY Pais
    """)
    d26 = q(f"""
        SELECT ds_pais AS Pais, SUM(vl_fob) AS EXP_2026,
               SUM(qt_kilo_liquido) AS Kg_2026
        FROM v2026
        WHERE tp_carga='EXP' AND nr_ano=2026 AND sg_uf='SC'
          AND NOT(ds_pais ILIKE '%Estados Unidos%') AND {COMPLEXO}
        GROUP BY Pais
    """)
    df = d26.merge(d25, on="Pais", how="outer").fillna(0)
    df["Delta_EXP_USD"]  = df.EXP_2026 - df.EXP_2025
    df["Delta_Pct"]      = ((df.EXP_2026-df.EXP_2025)/df.EXP_2025.replace(0,np.nan)*100).round(1)
    df["VU_2025_USD_kg"] = (df.EXP_2025/df.Kg_2025.replace(0,np.nan)).round(4)
    df["VU_2026_USD_kg"] = (df.EXP_2026/df.Kg_2026.replace(0,np.nan)).round(4)
    df["Var_VU_Pct"]     = ((df.VU_2026_USD_kg-df.VU_2025_USD_kg)/df.VU_2025_USD_kg.replace(0,np.nan)*100).round(1)
    df = df.sort_values("Delta_EXP_USD", ascending=False).head(25)
    df["Classificacao"]  = df.Delta_EXP_USD.apply(
        lambda x: "Ganhador" if x > 1e6 else ("Perdedor" if x < -1e6 else "Estável"))
    return df[["Pais","EXP_2025","EXP_2026","Delta_EXP_USD","Delta_Pct",
               "VU_2025_USD_kg","VU_2026_USD_kg","Var_VU_Pct","Classificacao"]]


# ─── Excel writer ─────────────────────────────────────────────────────────────
def detect_fmt(col):
    c = col.lower()
    if "classificacao" in c or "cenario" in c or "pais" in c or "setor" in c or "periodo" in c or "mes" in c:
        return "text"
    if any(k in c for k in ["_pct","share","foregone_pct","premio_pct","var_vu","delta_pct","var_exp"]):
        return "pct"
    if any(k in c for k in ["vu_","premio_eua_usd"]):
        return "dec4"
    if any(k in c for k in ["usd","_usd","exp_","delta_exp","kg_","efeito","destr","desvio","perda","ctf","foregone_usd","receita_foregone_usd"]):
        return "num"
    return "text"

def write_sheet(ws, df, wb, titulo, freeze_cols=1):
    F = {
        "hdr":   wb.add_format({"bold":True,"bg_color":AZUL_ESC,"font_color":BRANCO,"border":1,
                                 "text_wrap":True,"valign":"vcenter","align":"center","font_size":9}),
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
        "text":  wb.add_format({"border":1,"font_size":9}),
        "text_e":wb.add_format({"border":1,"font_size":9,"bg_color":AZUL_CL}),
        "num_dest": wb.add_format({"num_format":"#,##0","border":1,"font_size":10,"bold":True,
                                    "bg_color":AMARELO}),
    }
    is_var = {ci: any(k in str(col).lower() for k in ["var_","delta_","_pct","foregone_pct"])
              for ci, col in enumerate(df.columns)}
    fmt    = {ci: detect_fmt(str(col)) for ci, col in enumerate(df.columns)}
    ws.merge_range(0, 0, 0, len(df.columns)-1, titulo, F["tit"])
    ws.set_row(0, 20); ws.set_row(1, 42)
    for ci, col in enumerate(df.columns):
        ws.write(1, ci, str(col), F["hdr"])
        try:
            w = min(max(df.iloc[:,ci].astype(str).map(len).max(), len(str(col)))+3, 40)
        except: w = 14
        ws.set_column(ci, ci, w)
    for ri, row in enumerate(df.itertuples(index=False)):
        even = ri % 2 == 0
        for ci, val in enumerate(row):
            ft = fmt[ci]; isv = is_var[ci]
            if pd.isna(val) or str(val) in ("nan","inf","-inf",""):
                ws.write(ri+2, ci, "", F["text_e"] if even else F["text"]); continue
            if ft == "num":
                ws.write(ri+2, ci, val, F["num_e"] if even else F["num"])
            elif ft == "pct":
                if isv and isinstance(val, float):
                    ws.write(ri+2, ci, val, F["pct+"] if val>0 else (F["pct-"] if val<0 else F["pct"]))
                else:
                    ws.write(ri+2, ci, val, F["pct_e"] if even else F["pct"])
            elif ft == "dec4":
                ws.write(ri+2, ci, val, F["dec4_e"] if even else F["dec4"])
            else:
                ws.write(ri+2, ci, val, F["text_e"] if even else F["text"])
    ws.freeze_panes(2, freeze_cols)


def build_excel(dms):
    with pd.ExcelWriter(OUT, engine="xlsxwriter",
                        engine_kwargs={"options":{"nan_inf_to_errors":True}}) as writer:
        wb = writer.book
        ws_idx = wb.add_worksheet("0_Indice")
        writer.sheets["0_Indice"] = ws_idx
        ws_idx.set_column(0,0,4); ws_idx.set_column(1,1,38); ws_idx.set_column(2,2,72)
        Fi = {
            "tit": wb.add_format({"bold":True,"font_size":13,"font_color":AZUL_ESC,"bottom":2}),
            "sub": wb.add_format({"italic":True,"font_size":9,"font_color":CINZA}),
            "hdr": wb.add_format({"bold":True,"bg_color":AZUL_ESC,"font_color":BRANCO,"border":1}),
            "aba": wb.add_format({"bold":True,"border":1,"align":"center","bg_color":AZUL_MED,"font_color":BRANCO}),
            "dsc": wb.add_format({"border":1}),
            "dsc_e":wb.add_format({"border":1,"bg_color":AZUL_CL}),
        }
        ws_idx.merge_range("B2:C2",
            "SEAFLOR 2026 — Estimativa de Perda de Receita de Exportação | Complexo Florestal SC",
            Fi["tit"])
        ws_idx.merge_range("B3:C3","Fonte: ComexStat/MDIC | Observatório FIESC | Junho 2026", Fi["sub"])
        ws_idx.merge_range("B4:C4",
            "Metodologia: destruição bruta − desvio de comércio + efeito-preço. "
            "Contrafactual A (baseline Jan-Mai 2025) e B (baseline 2024) e C (baseline 2023).", Fi["sub"])
        ws_idx.write("B6","Aba",Fi["hdr"]); ws_idx.write("C6","Descrição",Fi["hdr"])
        for i,(nome,(titulo,_)) in enumerate(dms.items()):
            ws_idx.write(6+i,1,nome,Fi["aba"])
            ws_idx.write(6+i,2,titulo,Fi["dsc_e"] if i%2==0 else Fi["dsc"])

        for nome,(titulo,df) in dms.items():
            ws = wb.add_worksheet(nome); writer.sheets[nome] = ws
            fc = 2 if any(c in df.columns for c in ["Setor","Pais"]) else 1
            write_sheet(ws, df, wb, titulo, freeze_cols=fc)
            print(f"  {nome}: {df.shape[0]}L x {df.shape[1]}C")
    return OUT


if __name__ == "__main__":
    print("Calculando estimativas de perda...")
    print("  [1/5] Decomposição destruição/desvio/efeito-preço por setor...")
    decomp = dm_decomposicao()
    print("  [2/5] Mensal complexo florestal...")
    mensal = dm_mensal_perda()
    print("  [3/5] Valor unitário EUA vs outros mercados...")
    vu = dm_valor_unitario()
    print("  [4/5] Cenários contrafactuais...")
    ctf = dm_contrafactual()
    print("  [5/5] Desvio de comércio — ganhadores/perdedores...")
    desv = dm_desvio_ganhadores()
    con.close()
    dms = {
        "1_Decomposicao":    ("1. Decomposição: Destruição Bruta | Desvio de Comércio | Destruição Líquida | Efeito-Preço | Perda Total — por Setor", decomp),
        "2_Mensal":          ("2. Perda Mensal Jan-Mai 2026 vs 2025 — Complexo Florestal SC", mensal),
        "3_Valor_Unitario":  ("3. Valor Unitário (USD/kg) EUA vs Outros Mercados — Prêmio de Mercado por Setor e Período", vu),
        "4_Contrafactual":   ("4. Cenários Contrafactuais A/B/C — Receita Foregone por Setor e Baseline de Share EUA", ctf),
        "5_Desvio_Ganhos":   ("5. Desvio de Comércio — Países Ganhadores/Perdedores com Variação de Valor Unitário", desv),
    }
    excel = build_excel(dms)
    print(f"\nArquivo: {excel}")
    print(f"Tamanho: {excel.stat().st_size/1024:.0f} KB")
