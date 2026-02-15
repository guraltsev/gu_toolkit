# Project 025: SmartPad2D Control

**Status:** Discovery  
**Priority:** Medium

## Goal
Add a two-parameter XY pad control that can own two symbols and integrate with the existing parameter manager.

## Core Requirements
- Single control maps to two symbols (e.g. `(a, b)`).
- Drag surface + numeric fields stay synchronized.
- Uses existing parameter ownership model so slider autodetection does not duplicate controls.
- Supports throttled live updates and commit-on-release mode.

## TODO
- [ ] Finalize widget contract (`values`, `get_value`, `set_value`, `on_change`).
- [ ] Decide implementation split between Python-side composite widget and JS drag surface.
- [ ] Define parameter manager registration behavior for multi-symbol controls.
- [ ] Add tests for synchronization, validation, and callback payloads.

## Exit Criteria
- [ ] SmartPad2D can be attached to a figure as a first-class parameter control.
- [ ] Existing slider-based flows remain unchanged.
