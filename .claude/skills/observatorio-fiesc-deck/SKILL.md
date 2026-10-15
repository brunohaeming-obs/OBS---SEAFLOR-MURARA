---
name: observatorio-fiesc-deck
description: >-
  Gera e edita apresentações PowerPoint (.pptx) no padrão atual do Observatório FIESC
  (IEL/FIESC), modelado no deck "[OBS FIESC] Panorama Setor da Madeira" (out/2026):
  16:9, capa escura com onda pontilhada, divisórias de seção azul-marinho numeradas,
  slides de conteúdo em fundo off-white com gráfico NATIVO à esquerda e análise curta
  à direita, títulos afirmativos em duas cores, Montserrat, azul #0240CA, números em
  pt-BR, síntese em duas colunas e encerramento com QR e contatos. Use SEMPRE que o
  usuário pedir deck, slides, apresentação, panorama ou .pptx ligado ao Observatório
  FIESC, IEL, FIESC ou análises setoriais/regionais de SC, ou disser "no padrão do
  Observatório", "no nosso template", "estilo FIESC" — inclui montar um deck do zero a
  partir de dados, acrescentar slides a um deck existente e ajustar gráficos/tabelas.
---

# Apresentações no padrão Observatório FIESC

Referência visual e lógica: o deck **"[OBS FIESC] Panorama Setor da Madeira"**. Os
slides-base dele (sem os dados) estão em `assets/template.pptx`; a biblioteca
`scripts/obs_deck.py` clona esses slides e preenche texto e gráficos nativos. **Não
redesenhe nada à mão — use a biblioteca**, que já aplica posições, fontes, cores e
estilo dos gráficos.

## Estrutura do deck (a lógica narrativa)

1. **Capa** — título do estudo (ExtraBold), subtítulo, mês/ano.
2. **Seção 01** — divisória azul-marinho com nome em duas linhas (fina/forte) e número grande.
3. **Slides de conteúdo** — um achado por slide. Sequência típica num panorama setorial:
   total por setor → evolução mensal → importações/saldo → top produtos → top destinos →
   participação/concentração (ex.: share dos EUA, participação de SC no Brasil, HHI).
4. **Seção 02** (ex.: Mercado de trabalho) — saldo por setor → saldo em 12 meses →
   saldo por classe CNAE → saldo por região (VP FIESC).
5. **Síntese** — duas colunas de blocos "**Tema.** texto", terminando com um "Ponto de atenção".
6. **Encerramento** — slide fixo (QR, logos, contatos); não editar.

## Anatomia do slide de conteúdo

| Elemento | Regra |
|---|---|
| Título | Afirmativo, carrega a conclusão. Parte inicial em tinta `#1E1E29`, parte final (a conclusão) em azul `#0240CA`. Montserrat Medium 24 pt (20 pt se longo). Ex.: "Exportações do complexo florestal **recuam**". |
| Título do gráfico | O que é + período entre parênteses: "Exportações de SC por setor do complexo florestal (jan-set)". SemiBold 11,5 pt azul. |
| Unidade | Linha abaixo: "Em US$ milhões FOB", "Admissões menos desligamentos no ano". 9 pt azul. |
| Gráfico | Nativo do PowerPoint (dados no Excel embutido), à esquerda. Sem eixo de valores nos gráficos de barra/coluna — os rótulos de dados bastam. |
| Texto | À direita, 2–3 parágrafos curtos, 10,5 pt, justificado. Destaques (entidades e números-chave) em SemiBold azul via `**trecho**`. Sem caixas, cards de KPI ou bullets. |
| Fonte | Rodapé central, cinza 8 pt, só siglas: "MDIC (2026) e Observatório FIESC (2026)", "MTE (2026) e Observatório FIESC (2026)". |
| Nota | Opcional (asterisco no título do gráfico), 6 pt azul, canto inferior direito — para definições (ex.: o que é "complexo florestal", divisões CNAE). |

## Gráficos (cores e rótulos)

- Anos comparados: **cinza `#B9BEC8`** (dois anos antes) → **azul-claro `#7F9BE6`** (ano anterior) → **azul `#0240CA`** (ano corrente). A última série passada é sempre o ano corrente.
- `colunas` — comparação por setor (até 3 anos). Rótulos em todas as séries; ano corrente em negrito azul.
- `linhas` — série mensal. Ano corrente com linha mais grossa; rótulo só no último ponto (`rotular="fim"` em todas as séries ou `"ultima"` só no ano corrente). Use `eixo_min/eixo_max` para não começar no zero quando a variação for pequena.
- `barras` — rankings (top produtos, destinos, classes CNAE, regiões), ordenados do maior para o menor, 1º no topo. **Rótulos das categorias limpos**: nada de "(+7,1%)" ou códigos no nome — variações e códigos vão para a **tabela alinhada** (`tabela=`), uma linha por barra, positivos em azul e negativos em tinta.
- Formato: comex `#,##0.00` (US$ milhões, 2 casas); emprego `#,##0`. Sempre pt-BR (`num_br`, `var_br`).

## Como usar

A pasta `scripts/` fica em `~/.claude/skills/observatorio-fiesc-deck/` (instalação pessoal)
ou em `<repo>/.claude/skills/observatorio-fiesc-deck/` (versão versionada no projeto).

```python
import sys
sys.path.insert(0, r"C:\Users\bruno.haeming\.claude\skills\observatorio-fiesc-deck\scripts")
from obs_deck import ObsDeck, num_br, var_br

deck = ObsDeck()
deck.capa("Setor da Madeira", "Panorama setorial", "Outubro de 2026")
deck.secao("01", "Comércio", "exterior")
deck.grafico(
    titulo=("Exportações do complexo florestal ", "recuam"),
    grafico_titulo="Exportações de SC por setor do complexo florestal (jan-set)",
    unidade="Em US$ milhões FOB",
    grafico=dict(tipo="colunas", categorias=["Madeira", "Móveis"],
                 series={"2024": [963.64, 185.99], "2025": [917.70, 194.39], "2026": [852.25, 142.37]}),
    texto=["O **complexo florestal** exportou **US$ 1,30 bilhão**, queda de 8,8%."],
    fonte="MDIC (2026) e Observatório FIESC (2026)",
)
deck.grafico(  # ranking com tabela de variação alinhada
    titulo="Pinus cresce; portas e móveis recuam", grafico_titulo="...", unidade="...",
    grafico=dict(tipo="barras", categorias=cats, series={"2025": v25, "2026": v26}, plot_x=0.40),
    tabela=dict(cabecalho=["Var. %", "Var. US$ mi"],
                linhas=[[var_br((b/a-1)*100, 1, "%"), var_br(b-a, 2)] for a, b in zip(v25, v26)]),
    texto=[...], fonte="MDIC (2026) e Observatório FIESC (2026)",
)
deck.sintese(("Síntese ", "e leitura do período"),
             esquerda=[("Comércio exterior.", "...")], direita=[("Ponto de atenção", "...")])
deck.encerramento()
deck.salvar("reports/presentations/[OBS FIESC] Panorama <Tema>.pptx")
```

Exemplo completo e executável: `scripts/exemplo_deck.py`. `plot_x` (barras com tabela) é a
fração da largura reservada aos nomes das categorias: ~0,20 para nomes curtos (países),
~0,35–0,42 para nomes longos (produtos, classes CNAE).

## Fluxo

1. Levante os dados e escreva, para cada slide, a **conclusão** (vira o título) e 2–3 frases de leitura.
2. Gere o deck com `ObsDeck` num script em `src/` do projeto (reprodutível).
3. **Renderize e confira** antes de entregar (PowerPoint COM):
   ```powershell
   $pp = New-Object -ComObject PowerPoint.Application
   $p = $pp.Presentations.Open("<deck.pptx>", $true, $false, $false)
   foreach ($s in $p.Slides) { $s.Export("<pasta>\s$($s.SlideIndex).png", "PNG", 1600, 900) }
   $p.Close()
   ```
   Verifique: texto da direita não invade o rodapé, rótulos do gráfico não cortam, tabela alinhada às barras.

## Editar um deck que o usuário já mexeu

O usuário ajusta os decks à mão (títulos, posições, textos, fontes). **Nunca regenere o
arquivo inteiro para aplicar uma mudança**: faça backup, abra o .pptx com python-pptx e
altere só os shapes/gráficos pedidos (`chart.replace_data(...)` mantém a formatação). Para
"slides novos" pedidos como adição, gere-os num arquivo separado ou anexe ao final, sem
alterar o deck raiz, a menos que ele peça.

## Detalhes

Valores exatos (posições em polegadas, tamanhos, hex, estilos de eixo/legenda) estão em
`references/padrao_visual.md`.
