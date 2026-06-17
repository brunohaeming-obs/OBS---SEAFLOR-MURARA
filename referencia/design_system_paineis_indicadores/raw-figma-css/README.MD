Design System — Portal do Observatório
Este arquivo contém o design system oficial para criação dos painéis de indicadores do novo portal do Observatório.
O objetivo deste design system é garantir consistência visual, reutilização de componentes e padronização da experiência entre diferentes painéis, páginas e módulos do portal.
Este arquivo deve ser usado por designers, desenvolvedores e agentes de desenvolvimento com acesso ao Figma MCP, como Codex, Claude Code ou outras ferramentas compatíveis.
1. Stack de front-end
Neste primeiro momento, o front-end do portal será desenvolvido em React.
Portanto, agentes de desenvolvimento devem gerar implementações pensando em:
componentes React reutilizáveis;
composição por props;
separação entre componentes visuais e lógica de dados;
reutilização de componentes existentes no projeto;
estrutura modular para cards, filtros, gráficos, tabelas e layouts de painel;
código aderente à arquitetura real do repositório.
Não gerar implementação em Django templates, HTML estático isolado ou outro framework, a menos que isso seja solicitado explicitamente.
Quando houver dúvida, priorizar:
React Components;
JSX/TSX conforme padrão do projeto;
CSS conforme padrão adotado no repositório;
componentes reutilizáveis em vez de telas monolíticas.
2. Como este arquivo está organizado
O design system está dividido nas seguintes páginas:
00 — README / Guia de Uso
Página inicial de orientação. Deve ser consultada antes de qualquer implementação.
01 — Foundations
Contém os fundamentos visuais do produto:
tipografia;
cores;
espaçamentos;
grid;
radius;
sombras;
tokens visuais;
padrões de visualização de dados, quando aplicável.
02 — Marca e Assets
Contém elementos de identidade visual:
logos do Observatório;
ícones;
ativos institucionais;
regras de uso da marca.
03 — Core UI Components
Contém componentes básicos de interface:
botões;
inputs;
selects/dropdowns;
tags;
paginação;
controles;
avatares;
barra de progresso;
navegação;
tooltip;
breadcrumbs;
checkbox;
radio;
toggle;
stepper.
04 — Dashboard Components
Contém componentes específicos para painéis de indicadores:
cards de KPI;
cards de indicador;
filtros;
containers de gráfico;
tabelas;
mapas;
rankings;
cards de insight;
fonte dos dados;
estados de carregamento;
estados vazios;
estados de erro.
05 — Dashboard Templates
Contém estruturas oficiais para montagem de páginas:
dashboard com grid;
dashboard sem grid;
página municipal;
página setorial;
página comparativa;
página de detalhe de indicador.
06 — Exemplos de Aplicação
Página reservada para exemplos completos de telas e painéis finalizados.
Enquanto não houver painéis finalizados, esta página pode permanecer vazia ou conter apenas um aviso de “em construção”.
Quando existirem exemplos, eles devem servir como referência de composição visual, mas não devem substituir os componentes oficiais.
99 — Sandbox / Não usar
Contém testes, estudos, versões antigas ou variações ainda não aprovadas.
Esta página deve ser ignorada em implementações oficiais.
3. Ordem oficial de consulta
Ao implementar uma nova tela ou componente, seguir esta ordem:
Consultar 00 — README / Guia de Uso.
Consultar 01 — Foundations para cores, tipografia, espaçamento, grid e tokens.
Consultar 03 — Core UI Components para componentes básicos de interface.
Consultar 04 — Dashboard Components para elementos específicos de painéis de indicadores.
Consultar 05 — Dashboard Templates para definir a estrutura da página.
Consultar o frame específico da tarefa.
Consultar 06 — Exemplos de Aplicação apenas quando houver exemplos finalizados.
Ignorar 99 — Sandbox / Não usar.
4. Regras gerais de implementação em React
Ao transformar este design em código React:
Não criar estilos visuais novos se já existir token, componente ou padrão equivalente.
Não usar valores hardcoded de cor, fonte, espaçamento, radius ou sombra quando houver token definido.
Reutilizar componentes existentes do projeto antes de criar novos componentes.
Criar componentes pequenos, reutilizáveis e sem responsabilidade excessiva.
Separar componentes de layout, componentes de UI e componentes específicos de dashboard.
Usar props para textos, valores, indicadores, estados e ações.
Evitar deixar dados fixos dentro dos componentes.
Preservar hierarquia visual, espaçamento, alinhamento e responsividade definidos no Figma.
Usar nomes semânticos para componentes, arquivos, props e classes.
Adaptar o design ao stack real do projeto.
Não gerar código isolado fora da arquitetura existente.
Não usar frames da página 99 — Sandbox / Não usar como referência de produção.
Quando houver divergência entre exemplo visual e componente oficial, priorizar o componente oficial.
5. Organização esperada dos componentes React
Sempre que possível, organizar a implementação em camadas:
Componentes básicos de interface
Exemplos:
Button
Input
Select
Tag
Tooltip
Pagination
Breadcrumb
ProgressBar
Referência principal no Figma:
03 — Core UI Components
Componentes específicos de dashboard
Exemplos:
KpiCard
IndicatorCard
FilterBar
ChartCard
TableCard
MapCard
RankingList
InsightCard
DataSource
EmptyState
LoadingState
ErrorState
Referência principal no Figma:
04 — Dashboard Components
Templates de página
Exemplos:
DashboardGridTemplate
DashboardNoGridTemplate
MunicipalDashboardTemplate
SectorDashboardTemplate
ComparisonDashboardTemplate
IndicatorDetailTemplate
Referência principal no Figma:
05 — Dashboard Templates
6. Regras para painéis de indicadores
Painéis de indicadores devem priorizar clareza, leitura rápida e consistência.
Todo painel deve conter, quando aplicável:
título claro da página;
descrição breve do objetivo do painel;
filtros globais;
cards principais de indicadores;
visualizações de dados;
tabelas ou rankings complementares;
indicação de fonte dos dados;
data de atualização;
estados de carregamento, vazio e erro;
possibilidade de exportação, quando previsto.
Os cards de indicadores devem seguir os padrões definidos em 04 — Dashboard Components.
As estruturas de página devem seguir os templates definidos em 05 — Dashboard Templates.
7. Quando usar dashboard com grid
Usar template com grid quando:
houver vários indicadores na mesma tela;
houver múltiplos gráficos;
o usuário precisar comparar regiões, períodos, setores ou categorias;
a tela tiver cards, gráficos, tabelas e filtros;
a organização modular facilitar a leitura do painel.
8. Quando usar dashboard sem grid
Usar template sem grid quando:
o conteúdo for mais narrativo;
houver uma visualização principal dominante;
a página tiver poucos indicadores;
o objetivo for explicar um tema com maior profundidade;
a experiência precisar ser mais editorial ou institucional.
9. Como agentes devem usar este design system
Agentes de desenvolvimento com acesso ao Figma MCP devem:
Começar por esta página.
Confirmar que a stack alvo é React.
Consultar os fundamentos visuais.
Identificar os componentes oficiais.
Identificar o template de dashboard correto.
Usar o frame específico da tarefa como referência final.
Gerar código React aderente ao projeto.
Validar o resultado comparando com o Figma.
O link geral deste arquivo serve como contexto do design system.
Para implementação, sempre que possível, fornecer também o link direto do frame específico que será implementado.
10. Prompt base para Codex, Claude ou outro agente MCP
Você está implementando uma tela do novo portal do Observatório.
Use o Figma MCP para consultar o design system oficial.
A stack de front-end alvo é React.
Ordem de consulta:
00 — README / Guia de Uso
01 — Foundations
03 — Core UI Components
04 — Dashboard Components
05 — Dashboard Templates
Frame específico da tela a ser implementada
Regras:
Gerar componentes React.
Não gerar Django template, HTML estático isolado ou outro framework.
Não criar estilos visuais novos se já existirem tokens ou componentes equivalentes.
Não usar valores hardcoded de cor, fonte, espaçamento, radius ou sombra.
Reutilizar os componentes existentes do projeto sempre que possível.
Adaptar o design ao stack real do projeto.
Priorizar responsividade e consistência visual.
Ignorar qualquer conteúdo da página 99 — Sandbox / Não usar.
Ao final, informar quais componentes e tokens foram utilizados.
Tarefa:
Implementar o frame selecionado seguindo o design system do Observatório.
Link do frame:
[INSERIR LINK DO FRAME ESPECÍFICO]
Stack do projeto:
React
Componentes existentes no repositório:
[INSERIR CAMINHOS OU NOMES DOS COMPONENTES, SE HOUVER]
11. Checklist de validação
Antes de considerar a implementação concluída, validar:
A tela foi implementada em React?
A tela segue o template correto?
As cores seguem os tokens oficiais?
A tipografia segue os estilos definidos?
O espaçamento está coerente com o design system?
Os componentes oficiais foram reutilizados?
Os filtros e controles seguem o padrão?
Os cards de indicador seguem o padrão?
Os gráficos estão dentro dos containers corretos?
A navegação está consistente?
Existem estados de loading, empty e error?
A fonte dos dados e data de atualização estão visíveis quando necessário?
A tela está responsiva?
O resultado foi comparado visualmente com o Figma?