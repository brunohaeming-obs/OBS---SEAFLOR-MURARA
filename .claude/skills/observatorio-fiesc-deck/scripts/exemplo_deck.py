"""Exemplo completo: reproduz a estrutura do "[OBS FIESC] Panorama Setor da Madeira".

    python exemplo_deck.py saida.pptx
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from obs_deck import ObsDeck, num_br, var_br  # noqa: E402

MDIC = "MDIC (2026) e Observatório FIESC (2026)"
MTE = "MTE (2026) e Observatório FIESC (2026)"

deck = ObsDeck()
deck.capa("Setor da Madeira", "Panorama setorial", "Outubro de 2026")

# ── Seção 1 ───────────────────────────────────────────────────────────────────
deck.secao("01", "Comércio", "exterior")

deck.grafico(
    titulo=("Exportações do complexo florestal ", "recuam"),
    grafico_titulo="Exportações de SC por setor do complexo florestal* (jan-set)",
    unidade="Em US$ milhões FOB, comparativo do somatório entre jan. e set. de cada ano",
    grafico=dict(tipo="colunas",
                 categorias=["Madeira", "Móveis", "Papel e celulose", "Base florestal"],
                 series={"2024": [963.64, 185.99, 238.69, 37.73],
                         "2025": [917.70, 194.39, 277.88, 36.70],
                         "2026": [852.25, 142.37, 275.57, 31.48]}),
    texto=["O **complexo florestal** catarinense exportou **US$ 1,30 bilhão** em jan-set/2026, "
           "retração de 8,8% frente a 2025.",
           "**A exportação de Madeira** responde por dois terços do total e caiu 7,1%. "
           "**Móveis** tiveram a maior queda, de 26,8%."],
    nota="*Complexo Florestal diz respeito às atividades que têm a floresta como origem da matéria-prima.",
    fonte=MDIC,
)

deck.grafico(
    titulo=("A queda do setor ", "no primeiro trimestre"),
    grafico_titulo="Exportações mensais do complexo florestal de SC",
    unidade="Em US$ milhões FOB",
    grafico=dict(tipo="linhas", categorias=["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set"],
                 series={"2024": [149, 153, 144, 156, 180, 156, 151, 160, 174.28],
                         "2025": [140, 159, 171, 176, 174, 162, 184, 131, 126.60],
                         "2026": [119, 122, 139, 160, 162, 161, 161, 139, 135.89]},
                 eixo_min=100, eixo_max=200),
    texto=["Mesmo em queda, em agosto e setembro, **o valor exportado superou o de 2025** "
           "(6,1% e 7,3%), as primeiras altas interanuais do ano."],
    fonte=MDIC,
)

# Top-N em barras horizontais + tabela de variação alinhada (sem % nos rótulos)
cats = ["Madeira serrada de pinus", "Compensados de madeira", "Portas de madeira", "Papel kraftliner"]
v25 = [268.78, 177.40, 190.05, 95.93]
v26 = [287.80, 166.99, 139.89, 112.43]
deck.grafico(
    titulo="Pinus cresce; portas e móveis recuam",
    grafico_titulo="Maiores produtos exportados pelo complexo florestal (jan-set)",
    unidade="US$ milhões FOB, variação de jan-set de 2026 em relação ao mesmo período de 2025",
    grafico=dict(tipo="barras", categorias=cats, series={"2025": v25, "2026": v26}, plot_x=0.42),
    tabela=dict(cabecalho=["Var. %", "Var. US$ mi"],
                linhas=[[var_br((b / a - 1) * 100, 1, "%"), var_br(b - a, 2)] for a, b in zip(v25, v26)]),
    texto=["A **madeira serrada de pinus**, principal item da pauta, avançou 7,1%.",
           "Entre os destaques positivos: **papel kraftliner (+17,2%)**."],
    fonte=MDIC,
)

# ── Seção 2 ───────────────────────────────────────────────────────────────────
deck.secao("02", "Mercado de", "trabalho")
deck.grafico(
    titulo=("Madeira volta a gerar ", "mais vagas em 2026"),
    grafico_titulo="Saldo de empregos formais por setor do complexo florestal (jan-ago)",
    unidade="Admissões menos desligamentos no ano",
    grafico=dict(tipo="colunas", formato="#,##0",
                 categorias=["Madeira", "Móveis", "Papel e celulose", "Base florestal"],
                 series={"2024": [2305, 1432, 1239, 253], "2025": [745, 889, 1201, 131],
                         "2026": [1602, 78, 1306, 115]}),
    texto=[f"O complexo florestal abriu **{num_br(3101)} vagas** em jan-ago de 2026."],
    fonte=MTE,
)

deck.sintese(("Síntese ", "e leitura do período"),
             esquerda=[("Comércio exterior.", "As exportações caíram 8,8% (US$ 1,30 bilhão)."),
                       ("Produtos.", "Serrados de pinus (+7,1%) crescem; portas e móveis recuam.")],
             direita=[("Emprego.", "O complexo abriu 3.101 vagas em jan-ago."),
                      ("Ponto de atenção", "O 2º semestre costuma ter saldo de empregos negativo.")])
deck.encerramento()

out = sys.argv[1] if len(sys.argv) > 1 else "exemplo_OBS_FIESC.pptx"
deck.salvar(out)
print("ok:", out)
