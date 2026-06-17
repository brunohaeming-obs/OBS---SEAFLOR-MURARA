# Design System Dashboard Tokens Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform CSS exports copied from Figma frames into a reusable local design system for dashboards, with tokens, normalized components, templates, documentation, and validation rules.

**Architecture:** Keep Figma exports as immutable source references in `raw-figma-css/`, extract shared decisions into `tokens/`, build production-ready CSS components in `components/`, and compose dashboard layouts in `templates/`. The raw CSS is the evidence; tokens and components are the code that teams should consume.

**Tech Stack:** CSS custom properties, HTML examples, optional React examples in later sprints, GitHub repository, Figma as visual reference.

---

## Operating Principles

- Figma remains the visual source of truth.
- Raw exported CSS must be preserved, not edited.
- Production CSS must use tokens, not repeated hardcoded values.
- Components must be reusable outside a single dashboard.
- Templates must be assembled from components, not from copied absolute-positioned Figma CSS.
- Every sprint should end with a visible example and a checklist update.

---

## Target Repository Structure

```text
design-system-dashboard/
  README.md
  plan.md
  package.json

  raw-figma-css/
    foundations/
    components/
    dashboard-components/
    dashboard-templates/

  tokens/
    colors.css
    typography.css
    spacing.css
    radius.css
    shadows.css
    layout.css
    index.css

  components/
    kpi-card.css
    sidebar-button.css
    filter-dropdown.css
    chart-container.css
    data-table.css
    badge.css
    dashboard-panel.css
    index.css

  templates/
    dashboard-grid-1.css
    dashboard-comex.css
    index.css

  examples/
    html/
      index.html
      dashboard-comex.html
    react/

  docs/
    css-import-guidelines.md
    token-map.md
    figma-map.md
    component-checklist.md
    visual-qa-checklist.md
```

---

## Sprint 0: Repository Setup And Intake Rules

**Goal:** Create a stable place for the design system and define how CSS copied from Figma enters the repo.

**Files:**
- Create: `README.md`
- Create: `plan.md`
- Create: `raw-figma-css/`
- Create: `docs/css-import-guidelines.md`

- [x] **Step 1: Create the base folders**

Create this structure:

```text
raw-figma-css/foundations/
raw-figma-css/components/
raw-figma-css/dashboard-components/
raw-figma-css/dashboard-templates/
tokens/
components/
templates/
examples/html/
examples/react/
docs/
```

- [x] **Step 2: Define naming rules for Figma CSS files**

Use lowercase kebab-case file names:

```text
raw-figma-css/foundations/colors.css
raw-figma-css/foundations/typography.css
raw-figma-css/components/button.css
raw-figma-css/dashboard-components/kpi-card.css
raw-figma-css/dashboard-components/data-table.css
raw-figma-css/dashboard-components/chart-container.css
raw-figma-css/dashboard-templates/dashboard-grid-1.css
```

- [x] **Step 3: Write CSS import guidelines**

Create `docs/css-import-guidelines.md` with these rules:

```markdown
# CSS Import Guidelines

1. Paste Figma exports only inside `raw-figma-css/`.
2. Do not edit raw Figma CSS after import.
3. Add the Figma frame name and node URL as a comment at the top of each imported file when available.
4. Use one file per Figma frame.
5. Do not consume `raw-figma-css/` directly in apps.
6. Convert repeated values into tokens before using them in components.
7. Convert absolute-positioned layouts into reusable component CSS.
```

- [ ] **Step 4: Commit Sprint 0**

Commit message:

```bash
chore: setup design system repository structure
```

**Acceptance Criteria:**
- Base folders exist.
- Raw CSS has a clear destination.
- Team knows where to paste Figma CSS.
- Raw CSS is explicitly separated from production CSS.

---

## Sprint 1: Inventory And Classification Of Figma CSS

**Goal:** Understand what has been exported from Figma and classify each frame before extracting tokens.

**Files:**
- Create: `docs/figma-map.md`
- Create: `docs/token-map.md`

- [x] **Step 1: Build the Figma frame inventory**

Create `docs/figma-map.md`:

```markdown
# Figma Map

| Area | Frame | Raw CSS File | Purpose | Status |
|---|---|---|---|---|
| Foundations | Colors | raw-figma-css/foundations/colors.css | Color palette | Pending |
| Foundations | Typography | raw-figma-css/foundations/typography.css | Font styles | Pending |
| Foundations | Spacing | raw-figma-css/foundations/spacing.css | Spacing scale | Pending |
| Dashboard Component | KPI | raw-figma-css/dashboard-components/kpi-card.css | KPI card | Pending |
| Dashboard Component | Container KPIs | raw-figma-css/dashboard-components/container-kpis.css | KPI group panel | Pending |
| Dashboard Component | Data Table | raw-figma-css/dashboard-components/data-table.css | Dark data table | Pending |
| Dashboard Component | Chart Container | raw-figma-css/dashboard-components/chart-container.css | Chart panel | Pending |
| Dashboard Template | Grid 1 | raw-figma-css/dashboard-templates/dashboard-grid-1.css | 1920x1080 dashboard grid | Pending |
```

- [x] **Step 2: Build the initial token candidate map**

Create `docs/token-map.md`:

```markdown
# Token Map

| Token Group | Source | Examples | Output File | Status |
|---|---|---|---|---|
| Colors | Foundations + dashboard CSS | #1E1E29, #242736, #2E303D | tokens/colors.css | Pending |
| Typography | Foundations + components | Montserrat 26/38, Open Sans 12/16 | tokens/typography.css | Pending |
| Spacing | Foundations + component dimensions | 4, 8, 12, 16, 24, 32, 48 | tokens/spacing.css | Pending |
| Radius | Components and templates | 4, 8, 12 | tokens/radius.css | Pending |
| Layout | Dashboard templates | 238 sidebar, 1920 canvas, 341 panels | tokens/layout.css | Pending |
| Shadows | Components if present | none identified initially | tokens/shadows.css | Pending |
```

- [x] **Step 3: Classify imported CSS files**

For each file in `raw-figma-css/`, update `docs/figma-map.md`:

```text
Pending -> Imported -> Mapped -> Tokenized -> Componentized
```

- [ ] **Step 4: Commit Sprint 1**

Commit message:

```bash
docs: map figma css sources and token candidates
```

**Acceptance Criteria:**
- Every imported Figma CSS file appears in `docs/figma-map.md`.
- Every planned token group appears in `docs/token-map.md`.
- No token extraction starts before source classification is clear.

---

## Sprint 2: Core Tokens

**Goal:** Create the base token files that all components and templates will consume.

**Files:**
- Create: `tokens/colors.css`
- Create: `tokens/typography.css`
- Create: `tokens/spacing.css`
- Create: `tokens/radius.css`
- Create: `tokens/layout.css`
- Create: `tokens/shadows.css`
- Create: `tokens/index.css`

- [x] **Step 1: Create color tokens**

Create `tokens/colors.css`:

```css
:root {
  --obs-color-bg: #1E1E29;
  --obs-color-container: #242736;
  --obs-color-subcontainer: #2E303D;
  --obs-color-border: #708097;
  --obs-color-white: #FFFFFF;
  --obs-color-text-primary: #FFFFFF;
  --obs-color-text-soft: #FAFAFA;
  --obs-color-neve: #BDD6FE;
  --obs-color-sky: #90BDFF;
  --obs-color-blue: #0077FC;
  --obs-color-blue-chip: #4285F4;
  --obs-color-lime: #54F394;
  --obs-color-gold: #FFDF6F;
  --obs-color-danger: #FF7171;
}
```

- [x] **Step 2: Create typography tokens**

Create `tokens/typography.css`:

```css
:root {
  --obs-font-title: "Montserrat", sans-serif;
  --obs-font-body: "Open Sans", sans-serif;
  --obs-font-chip: "Inter", sans-serif;

  --obs-text-h1-size: 48px;
  --obs-text-h1-line: 58px;
  --obs-text-h2-size: 32px;
  --obs-text-h2-line: 48px;
  --obs-text-h3-size: 26px;
  --obs-text-h3-line: 38px;
  --obs-text-body-lg-size: 16px;
  --obs-text-body-lg-line: 26px;
  --obs-text-body-md-size: 14px;
  --obs-text-body-md-line: 26px;
  --obs-text-label-size: 12px;
  --obs-text-label-line: 16px;
  --obs-text-caption-size: 10px;
  --obs-text-caption-line: 16px;

  --obs-font-weight-regular: 400;
  --obs-font-weight-semibold: 600;
}
```

- [x] **Step 3: Create spacing tokens**

Create `tokens/spacing.css`:

```css
:root {
  --obs-space-1: 4px;
  --obs-space-2: 8px;
  --obs-space-3: 12px;
  --obs-space-4: 16px;
  --obs-space-5: 20px;
  --obs-space-6: 24px;
  --obs-space-7: 28px;
  --obs-space-8: 32px;
  --obs-space-10: 40px;
  --obs-space-12: 48px;
  --obs-space-16: 64px;
  --obs-space-24: 96px;
}
```

- [x] **Step 4: Create radius tokens**

Create `tokens/radius.css`:

```css
:root {
  --obs-radius-xs: 4px;
  --obs-radius-sm: 8px;
  --obs-radius-md: 12px;
}
```

- [x] **Step 5: Create layout tokens**

Create `tokens/layout.css`:

```css
:root {
  --obs-dashboard-width: 1920px;
  --obs-dashboard-height: 1080px;
  --obs-sidebar-width: 238px;
  --obs-sidebar-button-height: 48px;
  --obs-kpi-height: 104px;
  --obs-kpi-icon-size: 48px;
  --obs-table-row-height: 40px;
  --obs-table-cell-height: 44px;
  --obs-chart-filter-height: 32px;
}
```

- [x] **Step 6: Create shadow tokens**

Create `tokens/shadows.css`:

```css
:root {
  --obs-shadow-none: none;
}
```

- [x] **Step 7: Create token entrypoint**

Create `tokens/index.css`:

```css
@import "./colors.css";
@import "./typography.css";
@import "./spacing.css";
@import "./radius.css";
@import "./layout.css";
@import "./shadows.css";
```

- [ ] **Step 8: Commit Sprint 2**

Commit message:

```bash
feat: add core dashboard design tokens
```

**Acceptance Criteria:**
- Tokens cover colors, fonts, type scale, spacing, radius, layout, and shadows.
- Token names use the `--obs-` prefix.
- Component CSS can import only `tokens/index.css`.

---

## Sprint 3: First Component Pass

**Goal:** Convert the most reused dashboard parts into token-based CSS components.

**Files:**
- Create: `components/dashboard-panel.css`
- Create: `components/kpi-card.css`
- Create: `components/sidebar-button.css`
- Create: `components/filter-dropdown.css`
- Create: `components/index.css`

- [x] **Step 1: Create dashboard panel component**

Create `components/dashboard-panel.css`:

```css
.obs-panel {
  background: var(--obs-color-container);
  border-radius: var(--obs-radius-md);
  color: var(--obs-color-text-primary);
}

.obs-panel--subtle {
  background: var(--obs-color-subcontainer);
}
```

- [x] **Step 2: Create KPI card component**

Create `components/kpi-card.css`:

```css
.obs-kpi-card {
  display: flex;
  align-items: center;
  gap: var(--obs-space-4);
  min-height: var(--obs-kpi-height);
  padding: var(--obs-space-3) var(--obs-space-6);
  background: var(--obs-color-subcontainer);
  border-radius: var(--obs-radius-md);
  color: var(--obs-color-text-primary);
}

.obs-kpi-card__icon {
  width: var(--obs-kpi-icon-size);
  height: var(--obs-kpi-icon-size);
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  border-radius: 999px;
  background: var(--obs-color-neve);
  color: var(--obs-color-bg);
}

.obs-kpi-card__body {
  min-width: 0;
}

.obs-kpi-card__label {
  margin: 0;
  font-family: var(--obs-font-title);
  font-size: var(--obs-text-body-lg-size);
  line-height: var(--obs-text-body-lg-line);
  font-weight: var(--obs-font-weight-regular);
}

.obs-kpi-card__value {
  margin: 0;
  font-family: var(--obs-font-title);
  font-size: var(--obs-text-h3-size);
  line-height: var(--obs-text-h3-line);
  font-weight: var(--obs-font-weight-semibold);
}

.obs-kpi-card__source {
  margin: 0;
  font-family: var(--obs-font-body);
  font-size: var(--obs-text-caption-size);
  line-height: var(--obs-text-caption-line);
  font-weight: var(--obs-font-weight-regular);
}
```

- [x] **Step 3: Create sidebar button component**

Create `components/sidebar-button.css`:

```css
.obs-sidebar-button {
  display: flex;
  align-items: center;
  gap: var(--obs-space-2);
  width: var(--obs-sidebar-width);
  height: var(--obs-sidebar-button-height);
  padding: 14px var(--obs-space-5);
  border: 0;
  border-radius: var(--obs-radius-md);
  background: var(--obs-color-subcontainer);
  color: var(--obs-color-white);
  font-family: var(--obs-font-title);
  font-size: var(--obs-text-body-lg-size);
  line-height: 24px;
  font-weight: var(--obs-font-weight-semibold);
  cursor: pointer;
}

.obs-sidebar-button[aria-selected="true"],
.obs-sidebar-button--selected {
  background: var(--obs-color-sky);
  color: var(--obs-color-bg);
}
```

- [x] **Step 4: Create filter dropdown component**

Create `components/filter-dropdown.css`:

```css
.obs-filter-dropdown {
  display: flex;
  align-items: center;
  gap: var(--obs-space-1);
  width: 208px;
  height: var(--obs-chart-filter-height);
  padding: 0 var(--obs-space-5);
  border: 1.5px solid var(--obs-color-border);
  border-radius: var(--obs-radius-sm);
  background: var(--obs-color-subcontainer);
  color: var(--obs-color-white);
  font-family: var(--obs-font-body);
  font-size: var(--obs-text-label-size);
  line-height: var(--obs-text-label-line);
}
```

- [x] **Step 5: Create component entrypoint**

Create `components/index.css`:

```css
@import "../tokens/index.css";
@import "./dashboard-panel.css";
@import "./kpi-card.css";
@import "./sidebar-button.css";
@import "./filter-dropdown.css";
```

- [ ] **Step 6: Commit Sprint 3**

Commit message:

```bash
feat: add first token-based dashboard components
```

**Acceptance Criteria:**
- KPI, panel, sidebar button, and dropdown use tokens.
- No hardcoded Figma color appears in these component files except through tokens.
- Components avoid `position: absolute`.

---

## Sprint 4: Table, Badge, And Chart Components

**Goal:** Normalize dense dashboard components that need stricter visual consistency.

**Files:**
- Create: `components/data-table.css`
- Create: `components/badge.css`
- Create: `components/chart-container.css`
- Modify: `components/index.css`

- [x] **Step 1: Create data table component**

Create `components/data-table.css`:

```css
.obs-data-table {
  width: 100%;
  border-collapse: collapse;
  overflow: hidden;
  border-radius: var(--obs-radius-md);
  background: var(--obs-color-bg);
  color: var(--obs-color-text-soft);
}

.obs-data-table th {
  height: 48px;
  padding: 0 var(--obs-space-3);
  background: var(--obs-color-bg);
  color: var(--obs-color-text-soft);
  font-family: var(--obs-font-title);
  font-size: var(--obs-text-body-md-size);
  line-height: var(--obs-text-body-md-line);
  font-weight: var(--obs-font-weight-regular);
  text-align: left;
}

.obs-data-table td {
  height: var(--obs-table-cell-height);
  padding: 0 var(--obs-space-3);
  border-top: 1px solid var(--obs-color-bg);
  color: var(--obs-color-text-soft);
  font-family: var(--obs-font-body);
  font-size: var(--obs-text-label-size);
  line-height: var(--obs-text-label-line);
  font-weight: var(--obs-font-weight-regular);
}

.obs-data-table tbody tr:nth-child(odd) {
  background: var(--obs-color-container);
}

.obs-data-table tbody tr:nth-child(even) {
  background: var(--obs-color-bg);
}
```

- [x] **Step 2: Create badge component**

Create `components/badge.css`:

```css
.obs-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 24px;
  padding: 6px var(--obs-space-2);
  border-radius: var(--obs-radius-sm);
  background: var(--obs-color-blue-chip);
  color: var(--obs-color-white);
  font-family: var(--obs-font-chip);
  font-size: var(--obs-text-caption-size);
  line-height: 12px;
  font-weight: var(--obs-font-weight-semibold);
}
```

- [x] **Step 3: Create chart container component**

Create `components/chart-container.css`:

```css
.obs-chart-container {
  display: flex;
  flex-direction: column;
  gap: var(--obs-space-4);
  background: var(--obs-color-container);
  border-radius: var(--obs-radius-md);
  color: var(--obs-color-white);
}

.obs-chart-container__title {
  margin: 0;
  font-family: var(--obs-font-title);
  font-size: var(--obs-text-body-lg-size);
  line-height: 20px;
  font-weight: var(--obs-font-weight-regular);
}

.obs-chart-container__body {
  min-height: 280px;
  border: 1px solid var(--obs-color-danger);
}

.obs-chart-container__source {
  margin: 0;
  font-family: var(--obs-font-body);
  font-size: var(--obs-text-caption-size);
  line-height: var(--obs-text-caption-line);
  color: var(--obs-color-white);
}
```

- [x] **Step 4: Update component entrypoint**

Append to `components/index.css`:

```css
@import "./data-table.css";
@import "./badge.css";
@import "./chart-container.css";
```

- [ ] **Step 5: Commit Sprint 4**

Commit message:

```bash
feat: add dashboard table badge and chart components
```

**Acceptance Criteria:**
- Table rows match the dark alternating-row pattern.
- Badge follows the chip pattern from Figma.
- Chart container provides title, body, and source areas.

---

## Sprint 5: Dashboard Templates

**Goal:** Convert Figma dashboard layouts into reusable CSS templates.

**Files:**
- Create: `templates/dashboard-grid-1.css`
- Create: `templates/index.css`
- Modify: `examples/html/index.html`

- [x] **Step 1: Create dashboard grid template**

Create `templates/dashboard-grid-1.css`:

```css
.obs-dashboard-grid-1 {
  min-height: 100vh;
  display: grid;
  grid-template-columns: var(--obs-sidebar-width) 341px 705px 341px;
  grid-template-rows: auto 1fr;
  gap: var(--obs-space-6);
  padding: 70px 72px 56px;
  background: var(--obs-color-bg);
  color: var(--obs-color-white);
}

.obs-dashboard-grid-1__header {
  grid-column: 2 / -1;
}

.obs-dashboard-grid-1__sidebar {
  grid-column: 1;
  grid-row: 1 / span 2;
  display: flex;
  flex-direction: column;
  gap: 19px;
}

.obs-dashboard-grid-1__left {
  grid-column: 2;
}

.obs-dashboard-grid-1__main {
  grid-column: 3;
}

.obs-dashboard-grid-1__right {
  grid-column: 4;
  display: grid;
  gap: var(--obs-space-6);
}

@media (max-width: 1200px) {
  .obs-dashboard-grid-1 {
    grid-template-columns: 1fr;
    padding: var(--obs-space-6);
  }

  .obs-dashboard-grid-1__header,
  .obs-dashboard-grid-1__sidebar,
  .obs-dashboard-grid-1__left,
  .obs-dashboard-grid-1__main,
  .obs-dashboard-grid-1__right {
    grid-column: 1;
  }

  .obs-dashboard-grid-1__sidebar {
    grid-row: auto;
  }
}
```

- [x] **Step 2: Create template entrypoint**

Create `templates/index.css`:

```css
@import "../components/index.css";
@import "./dashboard-grid-1.css";
```

- [ ] **Step 3: Commit Sprint 5**

Commit message:

```bash
feat: add dashboard grid template
```

**Acceptance Criteria:**
- Template reflects the Figma dashboard grid proportions.
- Template uses tokens and components.
- Template includes responsive behavior for narrower screens.

---

## Sprint 6: HTML Example And Visual Validation

**Goal:** Provide a working dashboard example that proves tokens and components can recreate the Figma style.

**Files:**
- Create: `examples/html/index.html`
- Create: `docs/visual-qa-checklist.md`

- [x] **Step 1: Create the HTML example**

Create `examples/html/index.html` with:

```html
<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Observatorio Dashboard Example</title>
    <link rel="stylesheet" href="../../templates/index.css">
  </head>
  <body>
    <main class="obs-dashboard-grid-1">
      <aside class="obs-dashboard-grid-1__sidebar">
        <button class="obs-sidebar-button obs-sidebar-button--selected">Visao Geral</button>
        <button class="obs-sidebar-button">Indicadores</button>
        <button class="obs-sidebar-button">Tabela</button>
      </aside>

      <header class="obs-dashboard-grid-1__header">
        <h1 class="obs-chart-container__title">Dashboard Template Grid 1</h1>
      </header>

      <section class="obs-dashboard-grid-1__left obs-panel">
        <article class="obs-kpi-card">
          <div class="obs-kpi-card__icon">%</div>
          <div class="obs-kpi-card__body">
            <p class="obs-kpi-card__label">Nome variavel</p>
            <p class="obs-kpi-card__value">99,9%</p>
            <p class="obs-kpi-card__source">FONTE: NOME FONTE 2026</p>
          </div>
        </article>
      </section>

      <section class="obs-dashboard-grid-1__main obs-chart-container">
        <h2 class="obs-chart-container__title">Inserir aqui o nome do grafico completo</h2>
        <div class="obs-chart-container__body"></div>
        <p class="obs-chart-container__source">FONTE: NOME FONTE 2026</p>
      </section>

      <section class="obs-dashboard-grid-1__right">
        <article class="obs-panel"></article>
        <article class="obs-panel"></article>
      </section>
    </main>
  </body>
</html>
```

- [x] **Step 2: Create visual QA checklist**

Create `docs/visual-qa-checklist.md`:

```markdown
# Visual QA Checklist

## Tokens
- [ ] Background uses Nanquim `#1E1E29`.
- [ ] Containers use Granito `#242736`.
- [ ] Subcontainers use Chumbo `#2E303D`.
- [ ] Radius values are 4px, 8px, or 12px.
- [ ] Fonts use Montserrat for titles/buttons and Open Sans for labels/body.

## Components
- [ ] KPI height is visually close to 104px.
- [ ] KPI icon circle is 48px.
- [ ] Sidebar button height is 48px.
- [ ] Table rows alternate between container and background colors.
- [ ] Dropdowns are 32px high with 1.5px border.

## Layout
- [ ] Desktop dashboard follows the Figma grid proportions.
- [ ] Responsive layout does not overlap or clip content.
- [ ] No production component depends on `position: absolute`.
```

- [ ] **Step 3: Commit Sprint 6**

Commit message:

```bash
feat: add html dashboard example and visual checklist
```

**Acceptance Criteria:**
- HTML example opens without build tooling.
- Example imports `templates/index.css`.
- Visual checklist can be used by designers and developers.

---

## Sprint 7: React Preparation

**Goal:** Prepare the design system for React without forcing the first version to depend on React.

**Files:**
- Create: `examples/react/README.md`
- Create: `docs/react-adoption.md`

- [x] **Step 1: Define React adoption strategy**

Create `docs/react-adoption.md`:

```markdown
# React Adoption Strategy

The CSS design system is framework-agnostic. React components should consume the same CSS classes and tokens.

Recommended React components:

- `DashboardGrid`
- `SidebarButton`
- `KpiCard`
- `ChartContainer`
- `FilterDropdown`
- `DataTable`
- `Badge`

React should not redefine colors, spacing, typography, or layout values. It should import CSS from `templates/index.css` or `components/index.css`.
```

- [x] **Step 2: Create React example preparation documentation**

Create `examples/react/README.md`:

```markdown
# React Example

This folder will contain React wrappers for the CSS design system.

The first implementation should use the same classes defined in:

- `tokens/`
- `components/`
- `templates/`

React components should add structure and props, not new visual decisions.
```

- [x] **Step 3: Commit Sprint 7**

Commit message:

```bash
docs: define react adoption strategy
```

**Acceptance Criteria:**
- Team understands that React is a wrapper layer, not a new visual system.
- CSS tokens remain the canonical style source.

---

## Sprint 8: Governance And Team Usage

**Goal:** Make the design system maintainable by the team.

**Files:**
- Create: `docs/component-checklist.md`
- Modify: `README.md`

- [ ] **Step 1: Create component checklist**

Create `docs/component-checklist.md`:

```markdown
# Component Checklist

Before adding a new component:

- [ ] Confirm there is a matching Figma frame or documented visual reference.
- [ ] Add the raw exported CSS to `raw-figma-css/`.
- [ ] Update `docs/figma-map.md`.
- [ ] Extract repeated values into `tokens/` if they are not covered.
- [ ] Build the component in `components/` using tokens.
- [ ] Add or update an HTML example.
- [ ] Run visual QA using `docs/visual-qa-checklist.md`.
- [ ] Do not import raw Figma CSS into production examples.
```

- [ ] **Step 2: Update README**

Update `README.md`:

````markdown
# Design System Dashboard

This repository converts Figma dashboard CSS exports into reusable dashboard tokens, components, and templates.

## How To Use

Import one of the entrypoints:

```css
@import "./tokens/index.css";
@import "./components/index.css";
@import "./templates/index.css";
```

## Source Of Truth

- Figma is the visual reference.
- `raw-figma-css/` stores copied CSS exports.
- `tokens/`, `components/`, and `templates/` are the production-ready design system.

## Do Not

- Do not use raw Figma CSS directly in projects.
- Do not create dashboard styles without checking existing tokens.
- Do not introduce new colors or typography without documenting them.
````

- [ ] **Step 3: Commit Sprint 8**

Commit message:

```bash
docs: add team governance for dashboard design system
```

**Acceptance Criteria:**
- Team has a repeatable process for adding components.
- README explains how to consume the design system.
- Governance reduces one-off styling decisions.

---

## Validation Strategy

Run these checks after each sprint:

```bash
git status
```

Expected:

```text
nothing to commit, working tree clean
```

Search for hardcoded colors outside tokens:

```bash
rg "#[0-9A-Fa-f]{6}" components templates examples docs
```

Expected:

```text
Only docs may reference raw hex values. Components and templates should use CSS variables.
```

Search for raw CSS imports:

```bash
rg "raw-figma-css" components templates examples
```

Expected:

```text
No results.
```

Search for absolute positioning in production CSS:

```bash
rg "position:\s*absolute" components templates
```

Expected:

```text
No results unless explicitly justified in a component note.
```

---

## Sprint Order Summary

1. **Sprint 0:** Repository setup and import rules.
2. **Sprint 1:** Inventory and classification of Figma CSS.
3. **Sprint 2:** Core tokens.
4. **Sprint 3:** First components: panel, KPI, sidebar, dropdown.
5. **Sprint 4:** Dense components: table, badge, chart container.
6. **Sprint 5:** Dashboard templates.
7. **Sprint 6:** HTML example and visual QA.
8. **Sprint 7:** React preparation.
9. **Sprint 8:** Governance and team usage.

---

## Definition Of Done

- Raw Figma CSS is stored and traceable.
- Tokens exist for shared colors, typography, spacing, radius, layout, and shadows.
- Components consume tokens instead of raw values.
- Templates compose components into dashboard layouts.
- At least one HTML example validates the visual direction.
- React adoption is documented but not required for the first release.
- Team has checklists for importing CSS, creating components, and validating visual quality.
