"""
Gera o Excel consolidado v2 com todas as métricas de crescimento YoY.
"""
import pandas as pd
from pathlib import Path

PROCESSED = Path(r"c:\Users\bruno.haeming\Desktop\Demandas\OBS - SEAFLOR MURARA\data\processed")
OUT = PROCESSED / "SEAFLOR_2026_Comex_SC_Florestal_v2.xlsx"

AZUL_ESC  = "1F4E79"
AZUL_MED  = "2E75B6"
AZUL_CL   = "DEEAF1"
VERDE_ESC = "375623"
VERM_ESC  = "C00000"
LARANJA   = "C55A11"
CINZA     = "595959"
BRANCO    = "FFFFFF"

# Abas: (csv_v2, titulo longo)
ABAS = [
    ("01_serie_historica_v2",
     "1. Serie Historica — EXP e IMP por categoria com crescimento YoY (2015–2025)"),
    ("02_saldo_comercial_v2",
     "2. Saldo Comercial do Complexo Florestal SC com variacao YoY (2015–2025)"),
    ("03_top_produtos_v2",
     "3. Top Produtos Exportados — 2023, 2024 e 2025 com variacao YoY"),
    ("04_top_destinos_v2",
     "4. Top Destinos das Exportacoes Florestais SC — 2023, 2024 e 2025 com variacao YoY"),
    ("05_participacao_sc_v2",
     "5. Participacao do Complexo Florestal no Total Exportado por SC com crescimento YoY"),
    ("06_yoy_produtos_v2",
     "6. Variacao Anual por Produto — 2023, 2024 e 2025 (valor, volume e preco medio)"),
    ("07_destinos_categoria_v2",
     "7. Destinos por Categoria SC Competitiva — 2023, 2024 e 2025 com variacao YoY"),
    ("08_concentracao_eua_v2",
     "8. Concentracao EUA nas Exportacoes Florestais SC com variacao YoY (2015–2025)"),
    ("09_mensal_eua_v2",
     "9. Exportacoes Mensais EUA vs Outros — 2023, 2024 e 2025 com comparativo mesmo mes ano ant."),
    ("10_queda_eua_v2",
     "10. Produtos com Maior Variacao nas Exportacoes para EUA — 2023, 2024 e 2025"),
    ("11_desvio_comercio_v2",
     "11. Desvio de Comercio — Paises Ganhadores H1 vs H2 2025 com YoY H2 2024"),
    ("12_gini_resumo_v2",
     "12. Gini — Concentracao de Destinos por Setor com variacao YoY (2023–2025)"),
    ("13_gini_top10_v2",
     "13. Gini — Top 10 Paises por Setor e Ano com share acumulado"),
    ("14_gini_lorenz_v2",
     "14. Gini — Dados da Curva de Lorenz por Setor e Ano"),
    ("15_crescimento_por_atividade",
     "15. Painel de Crescimento por Atividade CNAE — EXP, IMP, Saldo e Nr Destinos com YoY"),
    # Participação SC vs Brasil
    ("16_resumo_sc_vs_br",
     "16. Participacao SC/Brasil — Painel Resumo por Setor Florestal (EXP, IMP, Kg, Nr Destinos) 2023-2025"),
    ("17_participacao_serie",
     "17. Participacao SC/Brasil — Serie Historica 2015-2025 com variacao YoY por Setor"),
    ("18_participacao_pivot",
     "18. Participacao SC/Brasil — Pivot Setor x Ano 2019-2025 (% EXP SC/BR)"),
    ("19_rank_estados",
     "19. Participacao SC/Brasil — Ranking SC entre os Estados Exportadores por Setor 2023-2025"),
    ("20_competit_produto",
     "20. Participacao SC/Brasil — Share SC nas Exportacoes BR por Produto com YoY"),
    ("21_destinos_sc_vs_br",
     "21. Participacao SC/Brasil — Share SC nos Principais Destinos do Complexo Florestal BR"),
]


def detect_fmt(col: str):
    c = col.lower()
    if any(k in c for k in ["yoy", "var ", "pct", "share", "participacao", "% p", "pp"]):
        return "pct"
    if any(k in c for k in ["usd", "exporta", "importa", "saldo", "delta", "exp_", "imp_", "h1", "h2"]):
        return "num"
    if any(k in c for k in ["kg", "peso"]):
        return "num"
    if "gini" in c:
        return "dec4"
    if "hhi" in c:
        return "num"
    return "text"


def write_sheet(writer, nome_aba, df: pd.DataFrame, wb, titulo: str):
    df.to_excel(writer, sheet_name=nome_aba, index=False, startrow=1)
    ws = writer.sheets[nome_aba]

    # formatos
    F = {
        "hdr":  wb.add_format({"bold": True, "bg_color": AZUL_ESC, "font_color": BRANCO,
                                "border": 1, "text_wrap": True, "valign": "vcenter",
                                "align": "center", "font_size": 9}),
        "num":  wb.add_format({"num_format": "#,##0", "border": 1, "font_size": 9}),
        "num+": wb.add_format({"num_format": "#,##0", "border": 1, "font_size": 9,
                                "font_color": VERDE_ESC}),
        "num-": wb.add_format({"num_format": "#,##0", "border": 1, "font_size": 9,
                                "font_color": VERM_ESC}),
        "pct":  wb.add_format({"num_format": '0.0"%"', "border": 1, "font_size": 9}),
        "pct+": wb.add_format({"num_format": '"+"\\ 0.0"%"', "border": 1, "font_size": 9,
                                "font_color": VERDE_ESC}),
        "pct-": wb.add_format({"num_format": '0.0"%"', "border": 1, "font_size": 9,
                                "font_color": VERM_ESC}),
        "dec4": wb.add_format({"num_format": "0.0000", "border": 1, "font_size": 9}),
        "text": wb.add_format({"border": 1, "font_size": 9}),
        "tit":  wb.add_format({"bold": True, "font_size": 11, "bg_color": AZUL_MED,
                                "font_color": BRANCO, "align": "center", "valign": "vcenter"}),
        "even": wb.add_format({"border": 1, "font_size": 9, "bg_color": AZUL_CL}),
        "num_e":wb.add_format({"num_format": "#,##0", "border": 1, "font_size": 9,
                                "bg_color": AZUL_CL}),
        "pct_e":wb.add_format({"num_format": '0.0"%"', "border": 1, "font_size": 9,
                                "bg_color": AZUL_CL}),
        "dec_e":wb.add_format({"num_format": "0.0000", "border": 1, "font_size": 9,
                                "bg_color": AZUL_CL}),
    }

    # título
    ws.merge_range(0, 0, 0, len(df.columns) - 1, titulo, F["tit"])
    ws.set_row(0, 20)
    ws.set_row(1, 38)

    # cabeçalho
    for ci, col in enumerate(df.columns):
        ws.write(1, ci, str(col), F["hdr"])
        w = min(max(df[col].astype(str).map(len).max(), len(str(col))) + 3, 38)
        ws.set_column(ci, ci, w)

    # dados
    is_yoy_col = {ci: any(k in str(col).lower() for k in ["yoy", "var ", "delta", "pp"])
                  for ci, col in enumerate(df.columns)}
    fmt_type   = {ci: detect_fmt(str(col)) for ci, col in enumerate(df.columns)}

    for ri, row in enumerate(df.itertuples(index=False)):
        bg_even = ri % 2 == 0
        for ci, val in enumerate(row):
            is_yoy = is_yoy_col[ci]
            ft     = fmt_type[ci]
            even   = bg_even

            if pd.isna(val) or val == "" or str(val) == "nan":
                ws.write(ri + 2, ci, "", F["even" if even else "text"])
                continue

            if ft == "num":
                if is_yoy:
                    f = F["num+"] if isinstance(val, (int, float)) and val > 0 else (
                        F["num-"] if isinstance(val, (int, float)) and val < 0 else F["num"])
                else:
                    f = F["num_e"] if even else F["num"]
                ws.write(ri + 2, ci, val, f)
            elif ft == "pct":
                if is_yoy and isinstance(val, (int, float)):
                    f = F["pct+"] if val > 0 else (F["pct-"] if val < 0 else F["pct"])
                else:
                    f = F["pct_e"] if even else F["pct"]
                ws.write(ri + 2, ci, val, f)
            elif ft == "dec4":
                ws.write(ri + 2, ci, val, F["dec_e"] if even else F["dec4"])
            else:
                ws.write(ri + 2, ci, val, F["even"] if even else F["text"])

    # freeze
    ws.freeze_panes(2, 0)


def build_index(wb, writer, abas_info):
    ws = wb.add_worksheet("0_Indice")
    writer.sheets["0_Indice"] = ws
    ws.set_column(0, 0, 4)
    ws.set_column(1, 1, 38)
    ws.set_column(2, 2, 62)

    Ft = {
        "tit": wb.add_format({"bold": True, "font_size": 16, "font_color": AZUL_ESC, "bottom": 2}),
        "sub": wb.add_format({"italic": True, "font_size": 9,  "font_color": CINZA}),
        "hdr": wb.add_format({"bold": True, "bg_color": AZUL_ESC, "font_color": BRANCO, "border": 1}),
        "aba": wb.add_format({"bold": True, "border": 1, "align": "center",
                               "bg_color": AZUL_MED, "font_color": BRANCO}),
        "desc":wb.add_format({"border": 1}),
        "even":wb.add_format({"border": 1, "bg_color": AZUL_CL}),
        "aba_e":wb.add_format({"bold": True, "border": 1, "align": "center",
                                "bg_color": AZUL_MED, "font_color": BRANCO, "bg_color": "BDD7EE"}),
    }

    ws.merge_range("B2:C2", "SEAFLOR 2026 — Comercio Exterior SC: Complexo Florestal", Ft["tit"])
    ws.merge_range("B3:C3",
                   "Fonte: ComexStat/MDIC  |  Observatorio FIESC  |  Junho 2026  |  v2 — com crescimento YoY",
                   Ft["sub"])
    ws.merge_range("B4:C4",
                   "Cobertura: EXP e IMP de SC por NCM, 2015-2025 | CNAE 2 (Base Florestal), 16 (Madeira), 17 (Papel), 31 (Moveis)",
                   Ft["sub"])

    ws.write(5, 1, "Aba", Ft["hdr"])
    ws.write(5, 2, "Conteudo", Ft["hdr"])
    for i, (nome, titulo) in enumerate(abas_info):
        f_aba  = Ft["aba"]
        f_desc = Ft["even"] if i % 2 == 0 else Ft["desc"]
        ws.write(6 + i, 1, nome, f_aba)
        ws.write(6 + i, 2, titulo, f_desc)

    ws.set_row(1, 22)


def main():
    abas_info = []
    with pd.ExcelWriter(OUT, engine="xlsxwriter",
                        engine_kwargs={"options": {"nan_inf_to_errors": True}}) as writer:
        wb = writer.book

        for csv_nome, titulo in ABAS:
            path = PROCESSED / f"{csv_nome}.csv"
            if not path.exists():
                print(f"  SKIP (não encontrado): {csv_nome}")
                continue
            df = pd.read_csv(path, encoding="utf-8-sig")
            # nome da aba = prefixo numérico + label curto
            num = csv_nome.split("_")[0]
            short = {
                "01": "1_Serie_Hist",      "02": "2_Saldo",
                "03": "3_Top_Produtos",    "04": "4_Top_Destinos",
                "05": "5_Participacao",    "06": "6_YoY_Produtos",
                "07": "7_Dest_Categoria",  "08": "8_Conc_EUA",
                "09": "9_Mensal_EUA",      "10": "10_Queda_EUA",
                "11": "11_Desvio",         "12": "12_Gini_Resumo",
                "13": "13_Gini_Top10",     "14": "14_Gini_Lorenz",
                "15": "15_Cresc_Atividade",
                "16": "16_SC_BR_Resumo",
                "17": "17_SC_BR_Serie",
                "18": "18_SC_BR_Pivot",
                "19": "19_SC_BR_Rank",
                "20": "20_SC_BR_Produto",
                "21": "21_SC_BR_Destinos",
            }
            nome_aba = short.get(num, csv_nome[:31])
            write_sheet(writer, nome_aba, df, wb, titulo)
            abas_info.append((nome_aba, titulo))
            print(f"  {nome_aba}: {df.shape[0]}L x {df.shape[1]}C")

        build_index(wb, writer, abas_info)

    print(f"\nArquivo: {OUT}")
    print(f"Tamanho: {OUT.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
