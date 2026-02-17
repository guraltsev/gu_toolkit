# Issue 032: Toolkit overview compendium section lacks usable API guide and option reference

## Status
Open

## Summary
Assessment (2026-02-17): implementation is partially complete; coverage and/or documentation gaps listed below keep this issue open.

State-of-completion checklist:
- [ ] Toolkit overview still contains a placeholder BUG note indicating the compendium/documentation section is insufficiently explicit.
- [ ] Users do not currently get a concise, notebook-local quick reference of core functionality and common options.
- [ ] No documentation regression test currently validates minimum compendium coverage requirements.

## Evidence
- `docs/notebooks/Toolkit_overview.ipynb` includes a dedicated BUG marker: “Compendium sucks… should be much more explicit… common options”.
- Existing notebook quality checks catch placeholder BUG markers but do not validate compendium completeness/coverage.

## TODO
- [ ] Define minimum compendium content standard for example notebooks (core concepts, key helpers, common plot options, parameter options, troubleshooting pointers).
- [ ] Rewrite the Toolkit overview compendium section to satisfy that standard with concrete examples.
- [ ] Add notebook documentation-quality tests for compendium completeness, such as:
  - required section heading presence,
  - required keyword/topics presence,
  - absence of placeholder/author-only TODO markers.
- [ ] Ensure the compendium guidance aligns with current public API names and behavior.

## Exit criteria
- [ ] Compendium section is actionable for first-time users and contains no placeholder BUG content.
- [ ] Documentation-quality regression tests enforce compendium minimum coverage.
- [ ] Notebook and API references remain in sync.
