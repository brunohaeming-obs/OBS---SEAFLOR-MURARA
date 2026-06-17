# CSS Import Guidelines

## Rules

1. Paste Figma exports only inside `raw-figma-css/`.
2. Do not edit raw Figma CSS after import.
3. Add the Figma frame name and node URL as a comment at the top of each imported file when available.
4. Use one file per Figma frame.
5. Do not consume `raw-figma-css/` directly in apps.
6. Convert repeated values into tokens before using them in components.
7. Convert absolute-positioned layouts into reusable component CSS.

## File Naming

Use lowercase kebab-case file names.

Recommended paths:

```text
raw-figma-css/foundations/colors.css
raw-figma-css/foundations/typography.css
raw-figma-css/components/button.css
raw-figma-css/dashboard-components/kpi-card.css
raw-figma-css/dashboard-components/data-table.css
raw-figma-css/dashboard-components/chart-container.css
raw-figma-css/dashboard-templates/dashboard-grid-1.css
```

Existing imported files with legacy names should remain untouched until they are mapped in `docs/figma-map.md`.
