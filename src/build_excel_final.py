"""
Consolida todos os datamarts processados + análise Gini em um único Excel.
"""
import duckdb
import numpy as np
import pandas as pd
from pathlib import Path

GOLD = r"c:\Users\bruno.haeming\Desktop\Demandas\OBS - SEAFLOR MURARA\referencia\Dados\gold\comexstat_ncm_sc.parquet"
PROCESSED = Path(r"c:\Users\bruno.haeming\Desktop\Demandas\OBS - SEAFLOR MURARA\data\processed")
OUT = PROCESSED / "SEAFLOR_2026_Comex_SC_Florestal.xlsx"


# ── Gini ──────────────────────────────────────────────────────────────────────

def gini(values):
    arr = np.array(sorted(values), dtype=float)
    n = len(arr)
    if n == 0 or arr.sum() == 0:
        return None
    idx = np.arange(1, n + 1)
    return (2 * (idx * arr).sum()) / (n * arr.sum()) - (n + 1) / n


SETORES = {
    "Madeira (CNAE 16)":          "cd_cgce_n3 = '16'",
    "Moveis (CNAE 31)":           "cd_cgce_n3 = '31'",
    "Base Florestal (CNAE 2)":    "cd_cgce_n3 = '2'",
    "Papel e Celulose (CNAE 17)": "cd_cgce_n3 = '17'",
}

def build_gini_tables():
    con = duckdb.connect()
    resultados = []
    lorenz_rows = []
    detalhe_rows = []

    for setor, filtro in SETORES.items():
        for ano in [2024, 2025]:
            df = con.execute(f"""
                SELECT ds_pais, SUM(vl_fob) AS vl_fob
                FROM read_parquet('{GOLD}')
                WHERE tp_carga='EXP' AND nr_ano={ano}
                  AND {filtro} AND ds_pais IS NOT NULL
                GROUP BY ds_pais
                ORDER BY vl_fob DESC
            """).fetchdf()
            if df.empty:
                continue

            total = df["vl_fob"].sum()
            n = len(df)
            g = gini(df["vl_fob"].values)
            shares = df["vl_fob"] / total
            hhi = (shares ** 2).sum() * 10000

            resultados.append({
                "Setor": setor,
                "Ano": ano,
                "Gini (0=diversificado, 1=concentrado)": round(g, 4),
                "Nr Paises Compradores": n,
                "Exportacoes Totais (US$)": round(total, 0),
                "HHI": round(hhi, 0),
                "1 Pais": df.iloc[0]["ds_pais"],
                "Share 1 Pais (%)": round(df.iloc[0]["vl_fob"] / total * 100, 1),
                "Share Top 3 (%)": round(df.head(3)["vl_fob"].sum() / total * 100, 1),
                "Share Top 5 (%)": round(df.head(5)["vl_fob"].sum() / total * 100, 1),
            })

            # Top 10 países para detalhe
            for rank, row in enumerate(df.head(10).itertuples(), 1):
                detalhe_rows.append({
                    "Setor": setor,
                    "Ano": ano,
                    "Rank": rank,
                    "Pais": row.ds_pais,
                    "Exportacoes (US$)": round(row.vl_fob, 0),
                    "Share (%)": round(row.vl_fob / total * 100, 1),
                    "Share Acumulado (%)": round(df.head(rank)["vl_fob"].sum() / total * 100, 1),
                })

            # Lorenz curve
            vals = np.sort(df["vl_fob"].values)
            cum_pop = np.arange(1, n + 1) / n * 100
            cum_val = np.cumsum(vals) / total * 100
            step = max(1, n // 20)
            for pop, val in zip(cum_pop[::step], cum_val[::step]):
                lorenz_rows.append({
                    "Setor": setor, "Ano": ano,
                    "% Paises acumulado": round(pop, 1),
                    "% Exportacoes acumulado": round(val, 1),
                })
            lorenz_rows.append({
                "Setor": setor, "Ano": ano,
                "% Paises acumulado": 100.0,
                "% Exportacoes acumulado": 100.0,
            })

    con.close()
    return (
        pd.DataFrame(resultados),
        pd.DataFrame(lorenz_rows).drop_duplicates(),
        pd.DataFrame(detalhe_rows),
    )


# ── Formatação Excel ──────────────────────────────────────────────────────────

def write_sheet(writer, nome, df, wb, titulo=None):
    df.to_excel(writer, sheet_name=nome, index=False, startrow=1)
    ws = writer.sheets[nome]

    fmt_h  = wb.add_format({"bold": True, "bg_color": "#1F4E79", "font_color": "white",
                             "border": 1, "text_wrap": True, "valign": "vcenter"})
    fmt_n  = wb.add_format({"num_format": "#,##0", "border": 1})
    fmt_n2 = wb.add_format({"num_format": "0.0000", "border": 1})
    fmt_p  = wb.add_format({"num_format": "0.0", "border": 1})
    fmt_t  = wb.add_format({"border": 1})
    fmt_ng = wb.add_format({"num_format": "#,##0", "border": 1, "font_color": "#C00000"})
    fmt_ti = wb.add_format({"bold": True, "font_size": 12, "bg_color": "#2E75B6",
                             "font_color": "white", "align": "center", "valign": "vcenter"})

    label = titulo or nome.replace("_", " ")
    ws.merge_range(0, 0, 0, len(df.columns) - 1, label, fmt_ti)
    ws.set_row(0, 22)
    ws.set_row(1, 36)

    for ci, col in enumerate(df.columns):
        ws.write(1, ci, col, fmt_h)
        w = min(max(df[col].astype(str).map(len).max(), len(str(col))) + 4, 42)
        ws.set_column(ci, ci, w)
        col_l = col.lower()
        for ri, val in enumerate(df[col]):
            if pd.isna(val):
                ws.write(ri + 2, ci, "", fmt_t)
                continue
            if "gini" in col_l:
                ws.write(ri + 2, ci, val, fmt_n2)
            elif any(k in col_l for k in ["us$", "total", "export", "fob", "delta"]):
                ws.write(ri + 2, ci, val, fmt_ng if isinstance(val, float) and val < 0 else fmt_n)
            elif any(k in col_l for k in ["%", "share", "pct"]):
                ws.write(ri + 2, ci, val, fmt_p)
            else:
                ws.write(ri + 2, ci, val, fmt_t)


ABAS_EXISTENTES = {
    "1_Serie_Historica":        ("01_serie_historica_florestal.xlsx",        "1. Serie Historica - EXP e IMP por categoria (2015-2025)"),
    "2_Saldo_Comercial":        ("02_saldo_comercial_florestal.xlsx",        "2. Saldo Comercial Complexo Florestal SC (2015-2025)"),
    "3_Top_Produtos_2025":      ("03_top_produtos_exp_2025.xlsx",            "3. Top 20 Produtos Exportados - Complexo Florestal SC 2025"),
    "4_Top_Destinos_2025":      ("04_top_destinos_exp_2025.xlsx",            "4. Top 15 Destinos das Exportacoes Florestais SC 2025"),
    "5_Participacao_SC":        ("05_participacao_florestal_sc.xlsx",        "5. Participacao do Florestal no Total Exportado por SC"),
    "6_YoY_Produtos":           ("06_yoy_produtos_2024_2025.xlsx",           "6. Variacao Anual por Produto (2024 vs 2025)"),
    "7_Destinos_Categoria":     ("07_destinos_por_categoria_2023_2025.xlsx", "7. Destinos por Categoria SC Competitiva (2023-2025)"),
    "8_Concentracao_EUA":       ("08_concentracao_eua_serie.xlsx",           "8. Concentracao EUA nas Exportacoes Florestais SC"),
    "9_Mensal_EUA_vs_Outros":   ("09_mensal_eua_vs_outros_2024_2025.xlsx",   "9. Mensal 2024-2025 - EUA vs Outros (Efeito Tarifa)"),
    "10_Queda_Produtos_EUA":    ("10_queda_produtos_eua_2024_2025.xlsx",     "10. Produtos com Maior Queda nas Exportacoes EUA"),
    "11_Desvio_Comercio":       ("11_desvio_comercio_h1_h2_2025.xlsx",      "11. Desvio de Comercio - Paises Ganhadores Pos-Tarifa"),
}


def main():
    print("Calculando Gini...")
    gini_df, lorenz_df, detalhe_df = build_gini_tables()
    print(gini_df[["Setor", "Ano", "Gini (0=diversificado, 1=concentrado)", "Nr Paises Compradores",
                   "Share 1 Pais (%)", "Share Top 5 (%)"]].to_string(index=False))

    print(f"\nGerando {OUT.name}...")
    with pd.ExcelWriter(OUT, engine="xlsxwriter") as writer:
        wb = writer.book

        # Capa
        ws_capa = wb.add_worksheet("0_Indice")
        writer.sheets["0_Indice"] = ws_capa
        ws_capa.set_column(0, 0, 5)
        ws_capa.set_column(1, 1, 38)
        ws_capa.set_column(2, 2, 60)
        fmt_title = wb.add_format({"bold": True, "font_size": 15, "font_color": "#1F4E79", "bottom": 2})
        fmt_sub   = wb.add_format({"italic": True, "font_size": 10, "font_color": "#595959"})
        fmt_ih    = wb.add_format({"bold": True, "bg_color": "#1F4E79", "font_color": "white", "border": 1})
        fmt_ic    = wb.add_format({"border": 1})
        fmt_in_c  = wb.add_format({"border": 1, "bold": True, "align": "center"})
        ws_capa.merge_range("B2:C2", "SEAFLOR 2026 - Comercio Exterior SC: Complexo Florestal", fmt_title)
        ws_capa.merge_range("B3:C3", "Fonte: ComexStat/MDIC | Observatorio FIESC | Junho 2026", fmt_sub)
        ws_capa.write("B5", "Aba", fmt_ih)
        ws_capa.write("C5", "Conteudo", fmt_ih)

        indice_linhas = list(ABAS_EXISTENTES.items()) + [
            ("12_Gini_Resumo",    (None, "12. Gini - Concentracao de Destinos por Setor (2024 vs 2025)")),
            ("13_Gini_Top10",     (None, "13. Gini - Top 10 Paises por Setor e Ano")),
            ("14_Gini_Lorenz",    (None, "14. Gini - Dados da Curva de Lorenz")),
        ]
        for i, (nome, info) in enumerate(indice_linhas):
            titulo = info[1] if isinstance(info, tuple) else info
            ws_capa.write(5 + i, 1, nome, fmt_in_c)
            ws_capa.write(5 + i, 2, titulo, fmt_ic)

        # Abas existentes
        for nome, (arquivo, titulo) in ABAS_EXISTENTES.items():
            df = pd.read_excel(PROCESSED / arquivo)
            write_sheet(writer, nome, df, wb, titulo)

        # Abas Gini
        write_sheet(writer, "12_Gini_Resumo", gini_df, wb,
                    "12. Gini - Concentracao de Destinos por Setor (2024 vs 2025)")
        write_sheet(writer, "13_Gini_Top10", detalhe_df, wb,
                    "13. Gini - Top 10 Paises por Setor e Ano")
        write_sheet(writer, "14_Gini_Lorenz", lorenz_df, wb,
                    "14. Gini - Dados da Curva de Lorenz")

    print(f"Arquivo gerado: {OUT}")
    print(f"Tamanho: {OUT.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
