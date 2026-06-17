# Token Map

Token extraction has not started. This map identifies candidate groups and source evidence that should be reviewed before creating production token files.

| Token Group | Source | Examples | Output File | Status |
|---|---|---|---|---|
| Colors | `raw-figma-css/01 - Foundations/cores.css` + dashboard and core component CSS | `#1E1E29`, `#242736`, `#2E303D`, `#708097`, `#FFFFFF`, `#4285F4`, `#54F394`, `#FFDF6F`, `#FF7171` | `tokens/colors.css` | Pending |
| Typography | `raw-figma-css/01 - Foundations/tipografia.css` + component text styles | Montserrat `48/58`, Montserrat `18/150%`, Inter `16/24`, Inter `14/20`, Inter `12/16`, Inter `10/12` | `tokens/typography.css` | Pending |
| Spacing | `raw-figma-css/01 - Foundations/espacameto.css` + component padding and gap values | `4`, `8`, `12`, `14`, `16`, `20`, `24`, `32`, `40`, `48` | `tokens/spacing.css` | Pending |
| Radius | Foundations, core UI components, dashboard components, and templates | `4`, `5`, `8`, `12`, `20`, `24`, pill/circle radii | `tokens/radius.css` | Pending |
| Layout | Dashboard templates and dashboard component containers | `1920` canvas, `1080` canvas, `238` sidebar, `341` panel, `48` button height, `104` KPI height | `tokens/layout.css` | Pending |
| Shadows | Core UI component state styles | focus ring shadows such as `0px 0px 0px 3px #AEB6FB`; no dashboard elevation token confirmed yet | `tokens/shadows.css` | Pending |

## Notes

- Dashboard tokens should prioritize the dark dashboard palette before broadening into the full core UI palette.
- Repeated component dimensions should be promoted only when they represent reusable decisions, not one-off Figma frame bounds.
- Existing raw CSS remains evidence only. Production CSS should consume `tokens/`, `components/`, and `templates/`.
