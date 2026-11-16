# Operations workbench overrides

UI-UX-Pro-Max selection: Logistics/Delivery, Minimalism & Swiss, density 6.

- Full viewport geographic canvas, progressive drawers, one primary planning action. Discard generated marketing/hero/landing layout suggestions.
- Primary blue `#245fe0`, ink `#182c3c`, muted `#607281`, white cards, soft `#f3f6fa`. Original vehicle identity colors remain consistent across cards/map/routes. Orange reserved for delivery locations and warning states.
- Offline typography: Segoe UI / Microsoft YaHei, optional installed Inter. No remote Google Fonts request; Chinese labels remain readable without a network.
- 4/8 spacing rhythm, 44px action targets, visible existing keyboard focus, Escape to close drawers, native labeled inputs and checkboxes.
- Desktop drawer 346px and a separate canvas reservation. Below900px drawer closed on first load; below760px expanded drawer uses overlay and close control.
- Keep physical points on the actual road graph. Deterministic badge avoidance uses leader lines; never offset a simulated vehicle location to make a layout look nicer.
- Default three operating hubs and **all vehicle routes** after planning. Use white route casing, stronger vehicle colors and direction arrows; selected vehicle renders last. The all-routes toggle allows an individual vehicle view when shared roads overlap. Candidate pool and standby locations remain explicit layer toggles.
- Orders use parcel pins, order IDs, count badges for shared destinations, and priority text plus exclamation marks. Draw only pending/planned/in-transit orders; remove delivered/cancelled/expired pins while retaining every identity in the order history. A shared destination pin counts and lists only its remaining active orders. New-order emphasis belongs to the active comparison and is never evidence of planning acceptance.
- Open the route-change drawer after an observed order/priority/traffic change. Display the backend workflow: waiting for entered actions to finish, applied plan, or blocked with a reason. Successful mutations automatically request safe checkpoint replanning; only real backend steps advance the checkpoint. Applied plans wait for the user to resume, while blocked workflows do not retry or depart automatically.
- Show before/current/overlay controls only when a prior route baseline exists. Gray dashed removed routes and orange cased added routes complement vehicle colors, with service order changes listed separately. A safe plan can defer a new order; show this outcome without inventing changed road geometry.
- The “专注地图 / 退出专注” control collapses summary, fleet and playback overlays for route inspection, then restores them. It changes display only and must not masquerade as a physical pause. Keep map controls and the route comparison reachable.
- Route comparison changes only the route layer. Order status, vehicle position and cargo remain current backend facts. Comparison is local page memory, cleared on reload/session switch; actual completed prefixes do not count as removed roads.
- Editable drafts are separate from committed session parameters. Only a successful independent backend trial creates a new displayed plan. Show coverage and partial outcomes alongside distance/fuel/cost.
- Respect reduced-motion preference. Preserve the real-action animation clock; animation speed never changes deadlines or vehicle business travel times.
