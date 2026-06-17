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
