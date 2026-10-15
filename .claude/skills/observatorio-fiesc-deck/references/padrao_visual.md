# Padrão visual — valores exatos

Extraídos do deck "[OBS FIESC] Panorama Setor da Madeira" (out/2026). Slide 16:9,
10 × 5,625 pol (9.144.000 × 5.143.500 EMU).

## Cores

| Uso | Hex |
|---|---|
| Texto (tinta) | `#1E1E29` |
| Destaque, ano corrente, títulos de gráfico | `#0240CA` |
| Ano anterior | `#7F9BE6` |
| Dois anos antes | `#B9BEC8` |
| Eixos, linhas da tabela | `#E4E7EC` |
| Fonte (rodapé) | `#6B7280` |
| Fundo do conteúdo | `#F6F6F0` |
| Fundo da seção | azul-marinho do layout (`1_Title and Content`) |
| Número da seção | `LIGHT_2` (≈ `#EEEEEE`), Open Sans 258 pt |

## Tipografia

| Elemento | Fonte | Tamanho | Cor |
|---|---|---|---|
| Capa — título | Montserrat ExtraBold | 32 | branco |
| Capa — subtítulo | Montserrat | 24 | branco |
| Seção — linha 1 / linha 2 | Montserrat / Montserrat SemiBold | 39,75 | branco |
| Título do slide | Montserrat Medium | 24 (20 se longo) | tinta + azul |
| Título do gráfico | Montserrat SemiBold | 11,5 | azul |
| Unidade | Montserrat | 9 | azul |
| Texto de análise | Montserrat (destaque SemiBold azul) | 10,5–11 | tinta; justificado, entrelinha 112%, 9 pt após parágrafo |
| Fonte | Montserrat | 8 | `#6B7280`, centralizado |
| Nota | Montserrat | 6 | azul |
| Síntese | Montserrat; rótulo SemiBold azul | 10,5 | tinta |

## Posições (pol) — slide de conteúdo

| Shape (nome no template) | x | y | largura |
|---|---|---|---|
| logo | 0,49 | 0,27 | 0,91 |
| `titulo` | 0,40 | 0,52 | 8,96 |
| linha sob o título | 0,50 | 1,12 | 1,58 |
| `grafico_titulo` | 0,45 | ~1,37 | 6,10 |
| `grafico_unidade` | 0,45 | ~1,63 | 6,10 |
| gráfico | 0,35 | 1,85 | 5,95 (4,30 com tabela) × 2,88 |
| tabela de variação | fim do gráfico + 0,05 | alinhada à área interna | 0,72 por coluna |
| `texto` | 6,60 | 1,75 | 2,95 |
| `fonte` | 1,95 | 5,17 | 6,10 |
| nota | 6,20 | 4,45 | 3,40 |

## Gráficos nativos

- Fonte do gráfico Montserrat 8 pt, tinta.
- **Colunas**: `gapWidth` 60, `overlap` −5; eixo de valores excluído; eixo de categorias com linha `#E4E7EC`, rótulos 8 pt; legenda no topo; rótulos 7 pt (ano corrente bold azul, demais tinta).
- **Barras**: `gapWidth` 45, `overlap` −5; categorias em ordem inversa (1º no topo); rótulos de categoria 7,5 pt; rótulos de dados 7,5 pt bold na cor da série; legenda no topo. Com tabela: área interna manual (y = 0,13, h = 0,84 da altura) para casar faixas e linhas da tabela.
- **Linhas**: espessura 1,5 pt (anos anteriores) e 2,5 pt (ano corrente), marcador círculo 4; eixo de valores visível, sem linha, 8 pt, `#,##0`; legenda embaixo; rótulo bold na cor da série só no último ponto; área interna manual (0,07; 0,05; 0,86; 0,74).

## Tabela de variação

Sem estilo de tabela, sem preenchimento. Cabeçalho SemiBold azul 7,5 pt com linha inferior
azul 0,75 pt; linhas com divisória `#E4E7EC` 0,5 pt; valores alinhados à direita, bold;
positivos azul, negativos tinta; colunas de texto (ex.: código CNAE) em tinta normal.
