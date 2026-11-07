# Overprint frontend redesign

The November 7, 2026 redesign applies Hallmark's requested **Overprint** theme to the existing four Flask app screens. It keeps CampusScout's name, routes, field names, IDs, server calls, privacy text and approved-context workflow. No backend dependency or frontend framework was added.

## What changed

The old sidebar and tall introduction became a compact masthead and task heading. Teal and orange text surfaces intersect on grey newsprint, with heavy Anybody headings, Archivo body text, square controls and ruled listings. The event filters sit beside results on desktop and stack on smaller screens. Ask, availability and My plan use the same tokens with task-specific compositions.

Event location, cost and source links remain visible while scanning. Organizer, dietary/food fields, source revision and recommendation explanations sit in a native details disclosure. All unknown values remain explicit. Source excerpt titles use heading level 2 under the page title.

All colors, fonts and spacing consume `static/css/tokens.css`. The shared contract is in `design.md`. Fonts are self-hosted in `static/fonts`, with the original OFL license files from the Google Fonts repository; no external font request is needed at runtime.

## Copy changes

These are task labels and formatting changes, not new product claims:

| Before | After |
| --- | --- |
| Find your next campus opportunity. | Explore events |
| A clearer starting point. | Ask campus questions |
| Make space for your week. | My availability |
| Your next steps, together. | My plan |
| Small uppercase section introductions | Plain task headings |
| Decorative arrows on links/buttons | The same action labels without arrows |
| Metadata joined by middle dots or dashes | Sentences, separate columns or “to” for time ranges |
| No calendar — schedule unchecked | No calendar: schedule unchecked |

The decorative star and navigation glyphs were removed. The “Local by design” text moved to the footer. Limits, dates, source facts, unknown fields, warnings, pairing text and consent wording were retained. No routes, controls or source data were removed.

## Verification

- Full offline regression suite: **75 passed, 1 optional real-retrieval test deselected** (`eval/results/overprint-tests.xml`).
- Web integration checks after the review fixes: **3 passed**; JavaScript syntax and Git whitespace checks passed.
- Real headless-Chrome interactions covered calendar-aware recommendations, source disclosure, selection/save, an actual downloaded ICS file, context review/save/reload/clear, preserved plans, calendar upload, document evidence, empty/error states and keyboard focus.
- All **26 original IDs** and **20 named fields** remain present; the live before/after inventory retained **10/10 links** and **20/20 fields**.
- Hallmark's rendered app audit: **0 Floor failures, 0 open Reflex findings** across four live routes, with layout checks from 320 to 1920 pixels and 20 desktop/mobile captures.
- The independent finish review's two findings were fixed: the mobile availability title now stays inside its ink field, and paired numeric filters align. Focused checks at 320, 375 and 1440 pixels confirmed both.

The first audit also opened the raw Jinja file as HTML, which cannot resolve `url_for` or render conditional branches. Final visual checks use the actual Flask routes and CSS rather than that unrendered file. Three before-record warnings are acknowledged: the raw Jinja file is not rendered/read in that live pass, and the old `00:00` figure token differs from current fixture output. Original template IDs and field names were independently compared, all runtime links/fields were retained, and timestamp values remain supplied by the backend. No missing stylesheets or missing fonts in a raw `file://` template are counted as an app defect or a successful render.

Finish checks: there are two font families and three weights, immediate focus styles, one primary button recipe, no shadows or decorative animation, and no mobile-only removal of app content. Existing inline status/error behavior remains; the redesign adds no new validation or undo behavior. The existing privacy wording keeps straight apostrophes deliberately.

See `eval/results/overprint-verification.json` and the local `.hallmark/compare.html` before/after comparison. Original frontend files are snapshotted in ignored `.hallmark/before-source`; the pre-existing dirty checkout was preserved without committing or stashing it.

## Run and review

Use the Windows setup and fixed-clock demo in README. The normal server command remains:

```powershell
.\.venv\Scripts\python.exe -m campus_assistant.cli serve
```

Screenshots: `docs/screenshots/overprint-events.png`, `overprint-plan.png`, and `overprint-mobile.png`. They show fictional demo records, not real campus sources or user-study outcomes. No image slots or placeholder photography were introduced. An approved campus name/logo would be the useful additional branding material when a real campus is chosen.
