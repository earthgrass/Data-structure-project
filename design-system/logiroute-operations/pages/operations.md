# Operations workbench overrides

UI-UX-Pro-Max selection: Logistics/Delivery, Minimalism & Swiss, density 6.

- Full viewport geographic canvas, progressive drawers, one primary planning action. Discard generated marketing/hero/landing layout suggestions.
- Primary blue `#245fe0`, ink `#182c3c`, muted `#607281`, white cards, soft `#f3f6fa`. Original vehicle identity colors remain consistent across cards/map/routes. Orange reserved for delivery locations and warning states.
- Offline typography: Segoe UI / Microsoft YaHei, optional installed Inter. No remote Google Fonts request; Chinese labels remain readable without a network.
- 4/8 spacing rhythm, 44px action targets, visible existing keyboard focus, Escape to close drawers, native labeled inputs and checkboxes.
- Desktop drawer 346px and a separate canvas reservation. Below900px drawer closed on first load; below760px expanded drawer uses overlay and close control.
- Keep physical points on the actual road graph. Deterministic badge avoidance uses leader lines; never offset a simulated vehicle location to make a layout look nicer.
- Default three operating hubs, selected route, current destinations. Candidate pool, all routes and standby locations use explicit layer toggles.
- Editable drafts are separate from committed session parameters. Only a successful independent backend trial creates a new displayed plan. Show coverage and partial outcomes alongside distance/fuel/cost.
- Respect reduced-motion preference. Preserve the real-action animation clock; animation speed never changes deadlines or vehicle business travel times.
