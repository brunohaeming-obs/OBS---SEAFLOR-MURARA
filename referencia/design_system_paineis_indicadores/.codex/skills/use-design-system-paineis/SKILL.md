---
name: use-design-system-paineis
description: Use this skill when creating, editing, reviewing, or auditing dashboards, panels, KPI screens, tables, filters, charts, sidebars, or React/frontend UI that must follow the Observatorio FIESC design system stored in a project-root folder named design_system_paineis_indicadores. Trigger when the user asks to use this design system, follow the visual standard, reuse panel/dashboard styles, check CSS consistency, or incorporate the design_system_paineis_indicadores submodule.
---

# Use Design System Paineis

## Core Rule

Use the repository folder at the project root as the source of truth:

```text
./design_system_paineis_indicadores/
```

Do not copy the full design-system context into the skill. Read the local folder every time, because the design system may evolve independently through the git submodule.

## Workflow

1. Locate the design system at `./design_system_paineis_indicadores`.
2. If the folder is missing, tell the user to add it from the official repository:

```bash
git submodule add https://github.com/observatorio-fiesc/design_system_paineis_indicadores.git design_system_paineis_indicadores
```

3. Read these sources before creating or changing UI:
   - `README.md` for consumer setup and import rules.
   - `tokens/` for colors, typography, spacing, radius, shadows, and layout tokens.
   - `components/` for reusable CSS classes.
   - `templates/` for page/dashboard layout patterns.
   - `docs/` for mapping, import, React adoption, and visual QA guidance.
   - `raw-figma-css/` only as visual reference from Figma.
4. Prefer existing `obs-*` classes and `--obs-*` tokens before writing new styles.
5. When a needed pattern exists only in `raw-figma-css/`, translate the decision into tokens/components/templates in the consuming app or propose adding it to the design system. Do not import `raw-figma-css` in production code.
6. Keep the consuming app's CSS thin: layout composition, state tweaks, and product-specific exceptions only.

## Import Standard

Use the packaged CSS entrypoint from the submodule whenever possible:

```css
@import "../design_system_paineis_indicadores/tokens/index.css";
@import "../design_system_paineis_indicadores/components/index.css";
@import "../design_system_paineis_indicadores/templates/index.css";
```

Adjust the relative path to the actual stylesheet location in the consuming project. Do not import files from `raw-figma-css/`.

## Implementation Rules

- Use `--obs-*` variables instead of hardcoded colors, spacing, radius, typography, or shadows.
- Use component classes such as KPI cards, dashboard panels, chart containers, data tables, filter dropdowns, segmented controls, badges, and sidebar buttons when they match the UI need.
- Use template classes for dashboard grid structure before inventing a new page layout.
- Keep charts inside the design-system chart container pattern.
- Keep filters visually aligned with the design-system filter/dropdown patterns.
- Keep tables aligned with the design-system data-table pattern.
- Avoid one-off visual CSS unless there is no matching token, component, or template.
- If adding new reusable visual rules, place them in the design system repository first when the user is working inside it; otherwise document the proposed addition.

## Validation

Run the bundled validator from the consuming project root when possible:

```powershell
powershell -ExecutionPolicy Bypass -File .\.codex\skills\use-design-system-paineis\scripts\validate-design-system-usage.ps1
```

If the skill is installed elsewhere, run the script from that installed skill path and pass the project root:

```powershell
powershell -ExecutionPolicy Bypass -File <skill-path>\scripts\validate-design-system-usage.ps1 -ProjectRoot <project-root>
```

Also use targeted checks during review:

```bash
rg "raw-figma-css" src
rg "#[0-9A-Fa-f]{6}" src
rg "var\\(--obs-" src
rg "obs-" src
```

Treat direct `raw-figma-css` imports as a failure. Treat hardcoded hex values in app UI code as issues unless they are external assets, chart-library generated output, or documented exceptions.
