# Design: CampusScout

The shared system for the four existing Flask app screens.

## System
- Theme: Overprint, requested by the user; newsprint stock.
- Genre: playful, applied to a functional app rather than a marketing page.
- Shape: task heading, working controls, ruled source-linked results.
- Audience: students finding events that fit their classes and saving reviewed plans.
- Palette: grey newsprint, near-black ink, teal and orange flat ink fields.
- Signature: the task heading and its explanatory text print on two intersecting ink fields; type stays outside the overlap.
- Navigation: the same four destinations in a compact masthead; no decorative icons.
- Do not add stock photography, fabricated metrics, claims or testimonials.

## Tokens
`static/css/tokens.css` is the source of truth. All colors, font families and spacing consume its variables.
- Paper: `--color-paper`, `--color-paper-2`, `--color-paper-3`.
- Ink: `--color-ink`, `--color-ink-2`, `--color-muted`, `--color-rule`.
- Passes: `--color-accent` (teal), `--color-accent-2` (orange), `--blend` (multiply).
- Display: self-hosted Anybody, weight 900, wide and uppercase, line-height at least 1.02.
- Body and controls: self-hosted Archivo, 400 or 600, sentence case and untracked.
- Body: 16px. Labels and source metadata: 14px.
- Page titles: fixed 56px desktop, 33px mobile; long availability titles step down to 28px (23px at 320px) to keep words inside their ink field.
- Radius: zero. Shadows: none. Rules: 4px at region starts and thin between results.
- Container: capped and centered, with token gutters; no sideways page scrolling.

## Screens
- Events: filters beside a ruled event list; selections and export stay beside results.
- Ask: question/category form above source excerpts.
- Availability: upload form and stored intervals; separate pairing region.
- My plan: saved plan checks beside context review; no extra containment around forms inside a region.
- Keep every existing route, field name, ID, handler and privacy/consent statement.
- Keep location, price and source links visible while scanning events; use disclosure for organizer, dietary/food unknowns, revisions and matching explanations.

## Controls and states
- Primary: teal fill, ink text; orange hover, ink press with paper text.
- Secondary: ink outline on paper; no new primary-button variant.
- Inputs: square, visible labels and an ink border; native selects/checkboxes.
- Every control has an immediate `:focus-visible` ring and at least a 44px hit target.
- Native disabled, inline loading/status, empty/error and successful server results remain functional.
- No new modal, route or data behavior is introduced by the redesign.

## Motion
Still. No reveal, parallax, floating or decorative animation. Reduced-motion fallback is retained.

## Exports
`static/css/tokens.css`, `static/css/base.css` and `static/css/style.css`.
Fonts and their OFL license files live under `static/fonts`; no runtime font service is needed.
