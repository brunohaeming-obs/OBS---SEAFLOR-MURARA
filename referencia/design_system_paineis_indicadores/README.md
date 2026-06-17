# Design System Paineis Indicadores

Este repositorio converte exports CSS do Figma em um design system reutilizavel para paineis, dashboards e indicadores.

O objetivo e manter um padrao visual unico para novos projetos, usando tokens, componentes, templates e referencias do Figma como base.

## Repositorio Oficial

```text
https://github.com/observatorio-fiesc/design_system_paineis_indicadores
```

## Areas Do Repositorio

- `raw-figma-css/` guarda CSS copiado de frames do Figma. Use como referencia visual e evidencia de origem.
- `tokens/` contem variaveis CSS compartilhadas para cores, tipografia, espacamento, radius, sombras e layout.
- `components/` contem componentes CSS de producao construidos com tokens.
- `templates/` compoe componentes em layouts de dashboard.
- `examples/` contem exemplos locais para validar o design system.
- `docs/` contem documentacao de uso, mapeamento e governanca.

## Como Usar Em Um Novo Painel

A estrategia recomendada e incorporar este repositorio no novo projeto usando `git submodule`.

Dentro da raiz do novo projeto, rode:

```bash
git submodule add https://github.com/observatorio-fiesc/design_system_paineis_indicadores.git design_system_paineis_indicadores
```

Isso cria uma pasta dentro do projeto consumidor:

```text
novo-painel/
  design_system_paineis_indicadores/
    tokens/
    components/
    templates/
    raw-figma-css/
    docs/
```

O comando cria apenas a pasta informada no final do comando, neste caso `design_system_paineis_indicadores`. Ele nao cria automaticamente uma pasta `src/`.

A pasta `src/` pertence ao projeto consumidor. Ela sera criada pelo framework ou scaffold usado no novo painel, por exemplo Vite, Next.js, React, Vue ou outro setup.

## Importando O CSS

Para usar o layout completo de dashboard:

```css
@import "../design_system_paineis_indicadores/templates/index.css";
```

Para usar apenas tokens e componentes:

```css
@import "../design_system_paineis_indicadores/components/index.css";
```

O caminho pode mudar conforme a localizacao do arquivo CSS no projeto consumidor.

## Regra Sobre Raw Figma CSS

`raw-figma-css/` deve ser consultado como referencia visual, especialmente para containers de filtros, tabelas, graficos, KPIs e templates.

Nao importe arquivos de `raw-figma-css/` diretamente em apps, exemplos de producao ou componentes finais.

Quando uma decisao visual existir apenas em `raw-figma-css/`, converta essa decisao para:

1. Um token em `tokens/`, se for uma decisao reutilizavel.
2. Um componente em `components/`, se for uma peca reutilizavel.
3. Um template em `templates/`, se for uma composicao de layout.

## Atualizando O Submodule No Projeto Consumidor

Quando este design system receber atualizacoes, rode no projeto consumidor:

```bash
git submodule update --remote design_system_paineis_indicadores
```

Depois, registre a nova versao no repositorio do painel:

```bash
git add design_system_paineis_indicadores
git commit -m "chore: update design system submodule"
```

## Skill Para Agentes

Este repositorio inclui uma skill em:

```text
.codex/skills/use-design-system-paineis/
```

Essa pasta e a origem versionada da skill. Para usar em outro projeto ou em outra maquina, copie a pasta inteira `use-design-system-paineis/`, mantendo o `SKILL.md`, `agents/` e `scripts/`.

Use essa skill ao criar, revisar ou corrigir novos paineis que precisam seguir este design system.

No projeto consumidor, a skill assume que o submodule esta na raiz com este nome:

```text
design_system_paineis_indicadores
```

A skill consulta `tokens/`, `components/`, `templates/`, `docs/` e usa `raw-figma-css/` apenas como referencia visual.

### Instalacao No Codex

Instalacao pessoal, disponivel para todos os projetos:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.codex\skills" | Out-Null
Copy-Item -Recurse -Force ".\.codex\skills\use-design-system-paineis" "$env:USERPROFILE\.codex\skills\use-design-system-paineis"
```

Se `CODEX_HOME` estiver configurado, use:

```powershell
New-Item -ItemType Directory -Force "$env:CODEX_HOME\skills" | Out-Null
Copy-Item -Recurse -Force ".\.codex\skills\use-design-system-paineis" "$env:CODEX_HOME\skills\use-design-system-paineis"
```

### Instalacao No Claude Code

Instalacao pessoal, disponivel para todos os projetos:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\skills" | Out-Null
Copy-Item -Recurse -Force ".\.codex\skills\use-design-system-paineis" "$env:USERPROFILE\.claude\skills\use-design-system-paineis"
```

Instalacao somente no projeto atual:

```powershell
New-Item -ItemType Directory -Force ".\.claude\skills" | Out-Null
Copy-Item -Recurse -Force ".\.codex\skills\use-design-system-paineis" ".\.claude\skills\use-design-system-paineis"
```

No Claude Code, o nome do diretorio define o comando direto:

```text
/use-design-system-paineis
```

Se o diretorio `.claude/skills/` nao existia quando o Claude Code foi iniciado, reinicie a sessao para garantir que a nova skill seja carregada.

### Validacao Da Skill

Para validar um projeto consumidor, rode a partir da raiz do projeto:

```powershell
powershell -ExecutionPolicy Bypass -File .\.codex\skills\use-design-system-paineis\scripts\validate-design-system-usage.ps1
```

Se a skill estiver instalada fora do projeto, informe o caminho do projeto:

```powershell
powershell -ExecutionPolicy Bypass -File <skill-path>\scripts\validate-design-system-usage.ps1 -ProjectRoot <project-root>
```

## Padrao De Desenvolvimento

Ao desenvolver um novo painel:

- Consulte `tokens/index.css`, `components/index.css` e `templates/index.css` antes de criar CSS novo.
- Use classes `obs-*` existentes sempre que possivel.
- Use variaveis `--obs-*` para cores, fontes, espacamentos, radius, sombras e layout.
- Consulte `raw-figma-css/` para entender decisoes visuais ainda nao normalizadas.
- Nao crie cores, fontes ou espacamentos fora dos tokens sem documentar a necessidade.
- Nao use `raw-figma-css/` como dependencia de producao.

## Validacao Recomendada

Procure cores hardcoded fora dos tokens:

```bash
rg "#[0-9A-Fa-f]{6}" components templates examples src
```

Procure imports indevidos de CSS bruto:

```bash
rg "raw-figma-css" components templates examples src
```

Procure layouts absolutos em CSS de producao:

```bash
rg "position:\s*absolute" components templates src
```

## Documentacao Complementar

- [CSS Import Guidelines](docs/css-import-guidelines.md)
- [Figma Map](docs/figma-map.md)
- [Token Map](docs/token-map.md)
- [React Adoption Strategy](docs/react-adoption.md)
- [Visual QA Checklist](docs/visual-qa-checklist.md)
