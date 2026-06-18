"""
Análise de participação SC/Brasil por setor florestal:
  - Madeira e Móveis (CNAE 16 + 31)
  - Papel e Celulose (CNAE 17)
  - Produção Florestal / Base Florestal (CNAE 2)
  + Complexo Florestal agregado
"""
import duckdb
import pandas as pd
import numpy as np
from pathlib import Path

GOLD_ALL = r"c:\Users\bruno.haeming\Desktop\Demandas\OBS - SEAFLOR MURARA\referencia\Dados\gold\comexstat_ncm_all.parquet"
GOLD_SC  = r"c:\Users\bruno.haeming\Desktop\Demandas\OBS - SEAFLOR MURARA\referencia\Dados\gold\comexstat_ncm_sc.parquet"
OUT      = Path(r"c:\Users\bruno.haeming\Desktop\Demandas\OBS - SEAFLOR MURARA\data\processed")

AZUL_ESC = "1F4E79"
AZUL_MED = "2E75B6"
AZUL_CL  = "DEEAF1"
VERDE    = "375623"
VERMELHO = "C00000"
BRANCO   = "FFFFFF"
CINZA    = "595959"
LARANJA  = "ED7D31"

FLORESTAIS = "('Madeira e Móveis', 'Papel e Celulose', 'Produção Florestal')"

SETORES = {
    "Madeira (CNAE 16)":          "cd_cgce_n3 = '16'",
    "Moveis (CNAE 31)":           "cd_cgce_n3 = '31'",
    "Madeira e Moveis (16+31)":   "cd_cgce_n3 IN ('16','31')",
    "Papel e Celulose (CNAE 17)": "cd_cgce_n3 = '17'",
    "Base Florestal (CNAE 2)":    "cd_cgce_n3 = '2'",
    "Complexo Florestal":         f"sc_competitiva IN {FLORESTAIS}",
}

con = duckdb.connect()


def q(sql):
    return con.execute(sql).fetchdf()


# ── 1. Participação SC/BR por setor — série anual 2015-2025 ───────────────────
def dm_part_serie():
    rows = []
    for setor, filtro in SETORES.items():
        br = q(f"""
            SELECT nr_ano AS Ano,
                SUM(CASE WHEN tp_carga='EXP' THEN vl_fob ELSE 0 END) AS BR_EXP_USD,
                SUM(CASE WHEN tp_carga='IMP' THEN vl_fob ELSE 0 END) AS BR_IMP_USD,
                SUM(CASE WHEN tp_carga='EXP' THEN qt_kilo_liquido ELSE 0 END) AS BR_EXP_Kg
            FROM read_parquet('{GOLD_ALL}')
            WHERE nr_ano BETWEEN 2015 AND 2025 AND {filtro}
            GROUP BY Ano ORDER BY Ano
        """)
        sc = q(f"""
            SELECT nr_ano AS Ano,
                SUM(CASE WHEN tp_carga='EXP' THEN vl_fob ELSE 0 END) AS SC_EXP_USD,
                SUM(CASE WHEN tp_carga='IMP' THEN vl_fob ELSE 0 END) AS SC_IMP_USD,
                SUM(CASE WHEN tp_carga='EXP' THEN qt_kilo_liquido ELSE 0 END) AS SC_EXP_Kg
            FROM read_parquet('{GOLD_SC}')
            WHERE nr_ano BETWEEN 2015 AND 2025 AND {filtro}
            GROUP BY Ano ORDER BY Ano
        """)
        df = br.merge(sc, on="Ano", how="left").fillna(0)
        df.insert(0, "Setor", setor)
        df["Participacao_EXP_Pct"]  = (df["SC_EXP_USD"] / df["BR_EXP_USD"] * 100).round(2)
        df["Participacao_IMP_Pct"]  = (df["SC_IMP_USD"] / df["BR_IMP_USD"] * 100).round(2)
        df["Participacao_Kg_Pct"]   = (df["SC_EXP_Kg"]  / df["BR_EXP_Kg"]  * 100).round(2)
        df["Var_SC_EXP_YoY_Pct"]   = ((df["SC_EXP_USD"] - df["SC_EXP_USD"].shift(1))
                                        / df["SC_EXP_USD"].shift(1).abs() * 100).round(1)
        df["Var_BR_EXP_YoY_Pct"]   = ((df["BR_EXP_USD"] - df["BR_EXP_USD"].shift(1))
                                        / df["BR_EXP_USD"].shift(1).abs() * 100).round(1)
        df["Var_Part_pp"]           = (df["Participacao_EXP_Pct"]
                                        - df["Participacao_EXP_Pct"].shift(1)).round(2)
        rows.append(df)
    return pd.concat(rows, ignore_index=True)


# ── 2. Participação SC em pivot — um setor por linha, anos como colunas ───────
def dm_part_pivot():
    rows = []
    for setor, filtro in SETORES.items():
        for ano in range(2019, 2026):
            br = q(f"""
                SELECT SUM(vl_fob) AS br_exp
                FROM read_parquet('{GOLD_ALL}')
                WHERE tp_carga='EXP' AND nr_ano={ano} AND {filtro}
            """).iloc[0, 0] or 0
            sc = q(f"""
                SELECT SUM(vl_fob) AS sc_exp
                FROM read_parquet('{GOLD_SC}')
                WHERE tp_carga='EXP' AND nr_ano={ano} AND {filtro}
            """).iloc[0, 0] or 0
            rows.append({"Setor": setor, "Ano": ano,
                         "SC_EXP": round(sc, 0), "BR_EXP": round(br, 0),
                         "Part_Pct": round(sc / br * 100, 2) if br else None})
    df = pd.DataFrame(rows)
    pivot = df.pivot(index="Setor", columns="Ano", values="Part_Pct").reset_index()
    pivot.columns.name = None
    cols = ["Setor"] + list(range(2019, 2026))
    pivot = pivot[cols]
    # variação 2024→2025
    pivot["Var 24→25 pp"] = (pivot[2025] - pivot[2024]).round(2)
    return pivot


# ── 3. Ranking SC/BR: posição de SC entre os estados exportadores ─────────────
def dm_rank_estados():
    rows = []
    for setor, filtro in SETORES.items():
        for ano in [2023, 2024, 2025]:
            df = q(f"""
                SELECT sg_uf AS UF, SUM(vl_fob) AS EXP_USD,
                       SUM(qt_kilo_liquido) AS EXP_Kg
                FROM read_parquet('{GOLD_ALL}')
                WHERE tp_carga='EXP' AND nr_ano={ano}
                  AND sg_uf IS NOT NULL AND {filtro}
                GROUP BY sg_uf
                ORDER BY EXP_USD DESC
            """)
            total_br = df["EXP_USD"].sum()
            df["Rank"] = range(1, len(df) + 1)
            df["Share_BR_Pct"] = (df["EXP_USD"] / total_br * 100).round(2)
            df["Setor"] = setor
            df["Ano"]   = ano
            rows.append(df)
    all_df = pd.concat(rows, ignore_index=True)
    # filtrar top 10 + SC sempre presente
    result = []
    for (setor, ano), grp in all_df.groupby(["Setor", "Ano"]):
        top10 = grp.head(10)
        sc_row = grp[grp["UF"] == "SC"]
        combined = pd.concat([top10, sc_row]).drop_duplicates("UF")
        combined = combined.sort_values("Rank")
        result.append(combined)
    return pd.concat(result, ignore_index=True)[
        ["Setor", "Ano", "Rank", "UF", "EXP_USD", "EXP_Kg", "Share_BR_Pct"]
    ]


# ── 4. Top produtos SC × BR — SC é competitiva em quê? ───────────────────────
def dm_competitividade_produto():
    """Share de SC nas exportações brasileiras produto a produto."""
    rows = []
    for setor, filtro in SETORES.items():
        br = q(f"""
            SELECT ds_produto AS Produto, nr_ano AS Ano,
                   SUM(vl_fob) AS BR_EXP_USD
            FROM read_parquet('{GOLD_ALL}')
            WHERE tp_carga='EXP' AND nr_ano IN (2023,2024,2025)
              AND ds_produto IS NOT NULL AND {filtro}
            GROUP BY Produto, Ano
        """)
        sc = q(f"""
            SELECT ds_produto AS Produto, nr_ano AS Ano,
                   SUM(vl_fob) AS SC_EXP_USD
            FROM read_parquet('{GOLD_SC}')
            WHERE tp_carga='EXP' AND nr_ano IN (2023,2024,2025)
              AND ds_produto IS NOT NULL AND {filtro}
            GROUP BY Produto, Ano
        """)
        df = br.merge(sc, on=["Produto", "Ano"], how="left").fillna(0)
        df["Setor"] = setor
        df["Part_SC_BR_Pct"] = (df["SC_EXP_USD"] / df["BR_EXP_USD"] * 100).round(1)
        rows.append(df)
    all_df = pd.concat(rows, ignore_index=True)
    # top produtos por SC em 2025, com share SC/BR
    top = (all_df[all_df["Ano"] == 2025]
           .sort_values("SC_EXP_USD", ascending=False)
           .groupby("Setor")
           .head(12))
    # adicionar YoY
    all_df_s = all_df.sort_values(["Setor", "Produto", "Ano"])
    prev_sc = all_df_s.groupby(["Setor", "Produto"])["SC_EXP_USD"].shift(1)
    prev_br = all_df_s.groupby(["Setor", "Produto"])["BR_EXP_USD"].shift(1)
    all_df_s["Var_SC_YoY_Pct"]   = ((all_df_s["SC_EXP_USD"] - prev_sc) / prev_sc.abs() * 100).round(1)
    all_df_s["Var_BR_YoY_Pct"]   = ((all_df_s["BR_EXP_USD"] - prev_br) / prev_br.abs() * 100).round(1)
    all_df_s["Var_Part_pp"]       = (all_df_s["Part_SC_BR_Pct"]
                                      - all_df_s.groupby(["Setor","Produto"])["Part_SC_BR_Pct"].shift(1)).round(2)
    # merge com top list
    top_idx = top.set_index(["Setor", "Produto", "Ano"]).index
    final = all_df_s[
        all_df_s.set_index(["Setor", "Produto", "Ano"]).index.isin(
            all_df_s[all_df_s["Setor"].isin(top["Setor"].unique()) &
                     all_df_s["Produto"].isin(top["Produto"].unique())]
            .set_index(["Setor", "Produto", "Ano"]).index
        )
    ].copy()
    return final.sort_values(["Setor", "SC_EXP_USD"], ascending=[True, False])


# ── 5. Destinos SC × BR: SC exporte mais que o Brasil para algum destino? ─────
def dm_destinos_vs_brasil():
    """Share de SC nas exportações brasileiras por destino, setor florestal agregado."""
    br = q(f"""
        SELECT ds_pais AS Pais, nr_ano AS Ano, SUM(vl_fob) AS BR_EXP_USD
        FROM read_parquet('{GOLD_ALL}')
        WHERE tp_carga='EXP' AND nr_ano IN (2023,2024,2025)
          AND sc_competitiva IN {FLORESTAIS} AND ds_pais IS NOT NULL
        GROUP BY Pais, Ano
    """)
    sc = q(f"""
        SELECT ds_pais AS Pais, nr_ano AS Ano, SUM(vl_fob) AS SC_EXP_USD
        FROM read_parquet('{GOLD_SC}')
        WHERE tp_carga='EXP' AND nr_ano IN (2023,2024,2025)
          AND sc_competitiva IN {FLORESTAIS} AND ds_pais IS NOT NULL
        GROUP BY Pais, Ano
    """)
    df = br.merge(sc, on=["Pais", "Ano"], how="left").fillna(0)
    df["Part_SC_BR_Pct"] = (df["SC_EXP_USD"] / df["BR_EXP_USD"] * 100).round(1)
    df = df.sort_values(["Setor" if "Setor" in df.columns else "Pais", "Ano",
                          "SC_EXP_USD"], ascending=[True, True, False])
    # top 20 destinos de SC em 2025
    top_paises = (df[df["Ano"] == 2025]
                  .sort_values("SC_EXP_USD", ascending=False)
                  .head(20)["Pais"].tolist())
    df = df[df["Pais"].isin(top_paises)].copy()
    df = df.sort_values(["Pais", "Ano"])
    prev_sc   = df.groupby("Pais")["SC_EXP_USD"].shift(1)
    prev_br   = df.groupby("Pais")["BR_EXP_USD"].shift(1)
    prev_part = df.groupby("Pais")["Part_SC_BR_Pct"].shift(1)
    df["Var_SC_YoY_Pct"]  = ((df["SC_EXP_USD"] - prev_sc) / prev_sc.abs() * 100).round(1)
    df["Var_BR_YoY_Pct"]  = ((df["BR_EXP_USD"] - prev_br) / prev_br.abs() * 100).round(1)
    df["Var_Part_pp"]      = (df["Part_SC_BR_Pct"] - prev_part).round(2)
    return df.sort_values(["Ano", "SC_EXP_USD"], ascending=[True, False])


# ── 6. Painel resumo — SC vs BR últimos 3 anos ───────────────────────────────
def dm_resumo_sc_br():
    rows = []
    for setor, filtro in SETORES.items():
        for ano in [2023, 2024, 2025]:
            br = q(f"""
                SELECT
                    SUM(CASE WHEN tp_carga='EXP' THEN vl_fob ELSE 0 END) AS BR_EXP,
                    SUM(CASE WHEN tp_carga='IMP' THEN vl_fob ELSE 0 END) AS BR_IMP,
                    SUM(CASE WHEN tp_carga='EXP' THEN qt_kilo_liquido ELSE 0 END) AS BR_Kg,
                    COUNT(DISTINCT CASE WHEN tp_carga='EXP' THEN ds_pais END) AS BR_Nr_Destinos,
                    COUNT(DISTINCT CASE WHEN tp_carga='EXP' THEN cd_ncm END) AS BR_Nr_NCMs
                FROM read_parquet('{GOLD_ALL}')
                WHERE nr_ano={ano} AND {filtro}
            """).iloc[0]
            sc = q(f"""
                SELECT
                    SUM(CASE WHEN tp_carga='EXP' THEN vl_fob ELSE 0 END) AS SC_EXP,
                    SUM(CASE WHEN tp_carga='IMP' THEN vl_fob ELSE 0 END) AS SC_IMP,
                    SUM(CASE WHEN tp_carga='EXP' THEN qt_kilo_liquido ELSE 0 END) AS SC_Kg,
                    COUNT(DISTINCT CASE WHEN tp_carga='EXP' THEN ds_pais END) AS SC_Nr_Destinos,
                    COUNT(DISTINCT CASE WHEN tp_carga='EXP' THEN cd_ncm END) AS SC_Nr_NCMs
                FROM read_parquet('{GOLD_SC}')
                WHERE nr_ano={ano} AND {filtro}
            """).iloc[0]
            row = {"Setor": setor, "Ano": ano}
            for k in ["EXP", "IMP", "Kg", "Nr_Destinos", "Nr_NCMs"]:
                row[f"SC_{k}"]    = round(sc[f"SC_{k}"], 0) if k in ["EXP","IMP","Kg"] else int(sc[f"SC_{k}"] or 0)
                row[f"BR_{k}"]    = round(br[f"BR_{k}"], 0) if k in ["EXP","IMP","Kg"] else int(br[f"BR_{k}"] or 0)
                if row[f"BR_{k}"]:
                    row[f"Part_{k}_Pct"] = round(row[f"SC_{k}"] / row[f"BR_{k}"] * 100, 2)
                else:
                    row[f"Part_{k}_Pct"] = None
            rows.append(row)
    df = pd.DataFrame(rows)
    # YoY
    df = df.sort_values(["Setor", "Ano"])
    for k in ["EXP", "IMP", "Kg"]:
        prev_sc = df.groupby("Setor")[f"SC_{k}"].shift(1)
        prev_br = df.groupby("Setor")[f"BR_{k}"].shift(1)
        prev_p  = df.groupby("Setor")[f"Part_{k}_Pct"].shift(1)
        df[f"Var_SC_{k}_YoY_Pct"] = ((df[f"SC_{k}"] - prev_sc) / prev_sc.abs() * 100).round(1)
        df[f"Var_BR_{k}_YoY_Pct"] = ((df[f"BR_{k}"] - prev_br) / prev_br.abs() * 100).round(1)
        df[f"Var_Part_{k}_pp"]     = (df[f"Part_{k}_Pct"] - prev_p).round(2)
    return df


# ── Excel writer ──────────────────────────────────────────────────────────────
def detect_fmt(col):
    c = col.lower()
    if any(k in c for k in ["yoy", "var_", "var ", "pp", "_pct", "part_"]):
        return "pct"
    if any(k in c for k in ["usd", "_exp", "_imp", "_kg", "exp_usd", "sc_exp", "br_exp"]):
        return "num"
    if "rank" in c:
        return "int"
    if "gini" in c:
        return "dec4"
    return "text"


def write_sheet(ws, df, wb, titulo, freeze_cols=0):
    F = {
        "hdr":  wb.add_format({"bold": True, "bg_color": AZUL_ESC, "font_color": BRANCO,
                                "border": 1, "text_wrap": True, "valign": "vcenter",
                                "align": "center", "font_size": 9}),
        "tit":  wb.add_format({"bold": True, "font_size": 11, "bg_color": AZUL_MED,
                                "font_color": BRANCO, "align": "center", "valign": "vcenter"}),
        "num":  wb.add_format({"num_format": "#,##0", "border": 1, "font_size": 9}),
        "num_e":wb.add_format({"num_format": "#,##0", "border": 1, "font_size": 9,
                                "bg_color": AZUL_CL}),
        "num+": wb.add_format({"num_format": "#,##0", "border": 1, "font_size": 9,
                                "font_color": VERDE}),
        "num-": wb.add_format({"num_format": "#,##0", "border": 1, "font_size": 9,
                                "font_color": VERMELHO}),
        "pct":  wb.add_format({"num_format": '0.00"%"', "border": 1, "font_size": 9}),
        "pct_e":wb.add_format({"num_format": '0.00"%"', "border": 1, "font_size": 9,
                                "bg_color": AZUL_CL}),
        "pct+": wb.add_format({"num_format": '"+"\\ 0.00"%"', "border": 1, "font_size": 9,
                                "font_color": VERDE}),
        "pct-": wb.add_format({"num_format": '0.00"%"', "border": 1, "font_size": 9,
                                "font_color": VERMELHO}),
        "dec4": wb.add_format({"num_format": "0.0000", "border": 1, "font_size": 9}),
        "text": wb.add_format({"border": 1, "font_size": 9}),
        "text_e":wb.add_format({"border": 1, "font_size": 9, "bg_color": AZUL_CL}),
        "int":  wb.add_format({"num_format": "0", "border": 1, "font_size": 9}),
        "int_e":wb.add_format({"num_format": "0", "border": 1, "font_size": 9,
                                "bg_color": AZUL_CL}),
    }
    is_yoy = {ci: any(k in str(col).lower() for k in ["yoy","var_","var ","pp","_pp"])
              for ci, col in enumerate(df.columns)}
    fmt    = {ci: detect_fmt(str(col)) for ci, col in enumerate(df.columns)}

    ws.merge_range(0, 0, 0, len(df.columns) - 1, titulo, F["tit"])
    ws.set_row(0, 20)
    ws.set_row(1, 40)

    for ci, col in enumerate(df.columns):
        ws.write(1, ci, str(col), F["hdr"])
        w = min(max(df[col].astype(str).map(len).max(), len(str(col))) + 3, 36)
        ws.set_column(ci, ci, w)

    for ri, row in enumerate(df.itertuples(index=False)):
        even = ri % 2 == 0
        for ci, val in enumerate(row):
            yoy_col = is_yoy[ci]
            ft = fmt[ci]
            if pd.isna(val) or str(val) in ("nan", "inf", "-inf", ""):
                ws.write(ri + 2, ci, "", F["text_e"] if even else F["text"])
                continue
            if ft == "num":
                if yoy_col and isinstance(val, float):
                    f = F["num+"] if val > 0 else (F["num-"] if val < 0 else F["num"])
                else:
                    f = F["num_e"] if even else F["num"]
            elif ft == "pct":
                if yoy_col and isinstance(val, float):
                    f = F["pct+"] if val > 0 else (F["pct-"] if val < 0 else F["pct"])
                else:
                    f = F["pct_e"] if even else F["pct"]
            elif ft in ("int",):
                f = F["int_e"] if even else F["int"]
            elif ft == "dec4":
                f = F["dec4"]
            else:
                f = F["text_e"] if even else F["text"]
            ws.write(ri + 2, ci, val, f)

    ws.freeze_panes(2, freeze_cols)


def build_excel(dms: dict):
    excel_path = OUT / "SEAFLOR_2026_Participacao_SC_Brasil.xlsx"
    with pd.ExcelWriter(excel_path, engine="xlsxwriter",
                        engine_kwargs={"options": {"nan_inf_to_errors": True}}) as writer:
        wb = writer.book

        # capa
        ws_idx = wb.add_worksheet("0_Indice")
        writer.sheets["0_Indice"] = ws_idx
        ws_idx.set_column(0, 0, 4)
        ws_idx.set_column(1, 1, 36)
        ws_idx.set_column(2, 2, 64)
        Ft = {
            "tit": wb.add_format({"bold": True, "font_size": 15, "font_color": AZUL_ESC,
                                   "bottom": 2}),
            "sub": wb.add_format({"italic": True, "font_size": 9, "font_color": CINZA}),
            "hdr": wb.add_format({"bold": True, "bg_color": AZUL_ESC, "font_color": BRANCO,
                                   "border": 1}),
            "aba": wb.add_format({"bold": True, "border": 1, "align": "center",
                                   "bg_color": AZUL_MED, "font_color": BRANCO}),
            "dsc": wb.add_format({"border": 1}),
            "dsc_e": wb.add_format({"border": 1, "bg_color": AZUL_CL}),
        }
        ws_idx.merge_range("B2:C2",
            "SEAFLOR 2026 — Participacao de SC nas Exportacoes Brasileiras: Complexo Florestal",
            Ft["tit"])
        ws_idx.merge_range("B3:C3",
            "Fonte: ComexStat/MDIC | Observatorio FIESC | Junho 2026", Ft["sub"])
        ws_idx.merge_range("B4:C4",
            "Setores: Madeira (CNAE 16), Moveis (CNAE 31), Papel e Celulose (CNAE 17), "
            "Base Florestal (CNAE 2) e Complexo Florestal agregado", Ft["sub"])
        ws_idx.write("B6", "Aba", Ft["hdr"])
        ws_idx.write("C6", "Conteudo", Ft["hdr"])
        for i, (nome, (titulo, _)) in enumerate(dms.items()):
            ws_idx.write(6 + i, 1, nome, Ft["aba"])
            ws_idx.write(6 + i, 2, titulo, Ft["dsc_e"] if i % 2 == 0 else Ft["dsc"])

        # abas de dados
        for nome, (titulo, df) in dms.items():
            ws = wb.add_worksheet(nome)
            writer.sheets[nome] = ws
            write_sheet(ws, df, wb, titulo, freeze_cols=2)
            print(f"  {nome}: {df.shape[0]}L x {df.shape[1]}C")

    return excel_path


# ── main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Calculando participações SC/Brasil...")

    print("  [1/6] Serie historica participacao...")
    serie = dm_part_serie()

    print("  [2/6] Pivot participacao por setor e ano...")
    pivot = dm_part_pivot()

    print("  [3/6] Ranking SC entre estados exportadores...")
    ranking = dm_rank_estados()

    print("  [4/6] Competitividade por produto (share SC/BR)...")
    comp_prod = dm_competitividade_produto()

    print("  [5/6] Destinos SC vs Brasil...")
    dest_vs_br = dm_destinos_vs_brasil()

    print("  [6/6] Painel resumo SC vs Brasil...")
    resumo = dm_resumo_sc_br()

    con.close()

    dms = {
        "1_Resumo_SC_vs_BR": (
            "1. Painel Resumo — SC vs Brasil por Setor (EXP, IMP, Kg, Nr Destinos) 2023-2025",
            resumo),
        "2_Participacao_Serie": (
            "2. Serie Historica Participacao SC/BR por Setor com variacao YoY (2015-2025)",
            serie),
        "3_Participacao_Pivot": (
            "3. Participacao SC/BR em Pivot — Setor vs Ano (2019-2025)",
            pivot),
        "4_Rank_Estados": (
            "4. Ranking SC entre Estados Exportadores por Setor — 2023, 2024 e 2025",
            ranking),
        "5_Competit_Produto": (
            "5. Competitividade por Produto — Share SC nas Exportacoes BR com YoY",
            comp_prod),
        "6_Destinos_SC_vs_BR": (
            "6. Participacao SC nos Principais Destinos do Complexo Florestal BR com YoY",
            dest_vs_br),
    }

    excel = build_excel(dms)
    print(f"\nArquivo gerado: {excel}")
    print(f"Tamanho: {excel.stat().st_size / 1024:.0f} KB")

    # Salvar CSVs para integração no Excel principal
    csv_map = {
        "16_resumo_sc_vs_br":       resumo,
        "17_participacao_serie":     serie,
        "18_participacao_pivot":     pivot,
        "19_rank_estados":           ranking,
        "20_competit_produto":       comp_prod,
        "21_destinos_sc_vs_br":      dest_vs_br,
    }
    for nome, df in csv_map.items():
        p = OUT / f"{nome}.csv"
        df.to_csv(p, index=False, encoding="utf-8-sig")
        print(f"  CSV: {nome}.csv ({len(df)} linhas)")
