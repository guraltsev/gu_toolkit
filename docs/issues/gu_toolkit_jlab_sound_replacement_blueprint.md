# gu_toolkit -> vendored jlab_function_audio sound-engine replacement blueprint

Date: 2026-04-07

Source archives analyzed:
- `gu_toolkit.sound-integration.zip` — SHA256 `a134d5edba9336e0c32ab25525d22156802632b7f1d593376c12c231395a82f7`
- `jlab_function_audio_project.zip` — SHA256 `4e07c004c8f97b97b78656600b1316c4948dfc69c123e71607ce8fd8a968deac`

---

## Executive summary

`gu_toolkit` currently has **two** audio surfaces:

1. the real **figure-linked streaming sound engine** implemented by `FigureSoundManager` and the inline `_SoundStreamBridge` in `src/gu_toolkit/figure_sound.py:21-32, 50-347, 351-545`, and
2. the separate `play(...)` helper in `src/gu_toolkit/numeric_operations.py:272-379`, which renders a complete inline WAV/HTML audio element and is **not** part of the figure streaming engine.

The engine that should be replaced is the **figure-linked streaming engine**.

The correct replacement is **not** a direct paste of JLAB code into GU call sites. The maintainable replacement is:

- vendor the JLAB runtime package into `src/gu_toolkit/_vendor/jlab_function_audio/`,
- keep that vendored package GU-agnostic,
- add only small, generic, upstream-worthy vendor APIs where GU truly needs them,
- rewrite `FigureSoundManager` as a **GU adapter** that preserves GU's public API and legend behavior while delegating transport, browser playback, buffering, and bounded autonormalization to the vendored JLAB engine.

The recommended design uses **one JLAB player per figure**, not one per plot and not one recreation per mode switch. To make that possible without touching vendor private state, add two small public methods to the vendored player:

- `mark_embedded()` — tells the player it is already attached inside another widget tree, so `play()` must not call `display(self)` later.
- `set_auto_normalize(enabled: bool)` — toggles JLAB's normalization mode on the existing player instance and flushes buffered audio from the current cursor.

This is materially better than recreating the player whenever GU's per-plot `autonormalization` flag changes. Recreating the player would reset JLAB's browser-helper state and can reintroduce a user-gesture unlock boundary because the frontend only creates/resumes an `AudioContext` from a trusted gesture or an already-unlocked state within the same helper instance (`src/jlab_function_audio/_frontend.js:448-510`). That would be an avoidable UX regression.

The migration should **not** replace `numeric_operations.play(...)` in the same patch. `play(...)` is a separate whole-clip helper with intentionally different behavior (whole-clip peak normalization to `0.99`, pure-return HTML widget, no background streaming) (`src/gu_toolkit/numeric_operations.py:359-379`; `docs/issues/_closed/issue-003-play-autoplays-and-displays-unconditionally.md:15-33`). It must be explicitly documented as **audited but out of scope** for this engine swap.

If the implementation follows the blueprint below, the result is a real engine replacement, not a facade:

- GU's legacy `_SoundStreamBridge` goes away completely.
- JLAB becomes the only runtime transport/browser engine for figure-linked sound.
- GU remains responsible only for public API preservation, plot/legend coordination, strict compatibility policy, and efficient adaptation from GU plot evaluation to JLAB's callable interface.

---

## Evidence collected

### Runtime and test evidence gathered during analysis

The following commands were run successfully against the unpacked repos:

```bash
# gu_toolkit current sound behavior
PYTHONPATH=src pytest -q tests/test_figure_sound.py tests/test_prelude_nintegrate.py

# jlab_function_audio normalization behavior
PYTHONPATH=src pytest -q tests/test_autonormalization.py

# jlab_function_audio frontend/lifecycle behavior
node --experimental-default-type=module tests/frontend_activation_boundary.mjs
node --experimental-default-type=module tests/frontend_comm_resilience.mjs
node --experimental-default-type=module tests/test_frontend_autoplay_policy.mjs
```

Observations from those runs:

- GU's current figure sound tests passed, confirming the current public behavior surface described below.
- JLAB's normalization tests passed, confirming the bounded autonormalization path is already regression-covered.
- JLAB's frontend lifecycle tests passed with Node's ESM mode enabled, confirming the autoplay-boundary and comm-lifecycle hardening is not speculative.

### Independence evidence

A grep over the JLAB source returned no GU coupling:

```bash
grep -R "gu_toolkit" src/jlab_function_audio
```

Result: no hits.

That is important because it means vendoring can preserve JLAB as an independent subpackage, with all GU-specific logic living outside it.

---

## What exists today in gu_toolkit

## 1) The current figure-linked sound engine

The current GU engine is fully contained inside `src/gu_toolkit/figure_sound.py`.

### Current architecture

- The module-level architecture note explicitly says it owns figure-scoped enable/disable state, single-active-plot playback, chunk rendering from plot numeric expressions, and a thin browser bridge (`src/gu_toolkit/figure_sound.py:21-32`).
- `_SoundStreamBridge` is an inline `anywidget.AnyWidget` with an embedded JS frontend (`src/gu_toolkit/figure_sound.py:50-347`).
- The browser bridge keeps only a small queue and requests Python chunks on demand (`src/gu_toolkit/figure_sound.py:183-208`).
- The transport format is base64-encoded mono PCM16 (`src/gu_toolkit/figure_sound.py:65-73, 507-509`).
- `FigureSoundManager` hardcodes `sample_rate = 44100`, `chunk_seconds = 1.0`, and `loop_seconds = 60.0` (`src/gu_toolkit/figure_sound.py:406-409`).
- The manager primes the first chunk synchronously on `sound(..., run=True)` and only then sends a frontend `start` message (`src/gu_toolkit/figure_sound.py:663-697`).
- Parameter changes increment a generation token and send `refresh`, causing future chunks to use the updated plot state (`src/gu_toolkit/figure_sound.py:698-759`).
- Chunk rendering is vectorized through `plot.numeric_expression(x_values)` over a full NumPy array (`src/gu_toolkit/figure_sound.py:466-489`).

### Current public behavior that must be preserved

The tests in `tests/test_figure_sound.py:44-244` define the real contract:

- sound controls are enabled by default,
- legend speaker buttons are shown when sound is enabled,
- `plot.sound(True)` starts or restarts playback,
- restarting the same plot resets playback to `0.0`,
- `plot.sound(False)` stops playback,
- starting another plot switches the active row,
- parameter changes refresh future audio,
- without `autonormalization`, a too-loud expression raises synchronously,
- with `autonormalization`, a loud expression is allowed,
- row speaker buttons follow the same semantics as `plot.sound(...)`.

### Current sound-specific integration points across GU

These files are not optional; they are part of the replacement scope.

| File | Current role | Evidence |
|---|---|---|
| `src/gu_toolkit/Figure.py` | Constructs `FigureSoundManager` and exposes `Figure.sound_generation_enabled(...)`. | `Figure.py:441-445`, `3554-3599` |
| `src/gu_toolkit/figure_api.py` | Current-figure delegation for `sound_generation_enabled(...)`. | `figure_api.py:380-425` |
| `src/gu_toolkit/figure_plot.py` | `Plot.sound(...)` delegates to manager; `Plot.autonormalization(...)` stores per-plot state and notifies manager when active plot changes mode. | `figure_plot.py:2151-2262` |
| `src/gu_toolkit/figure_legend.py` | Controls legend speaker buttons, speaker-button visibility, and the style-dialog checkbox/tooltip for autonormalization. | `figure_legend.py:868-878`, `1635-1760`, `2125-2140` |
| `src/gu_toolkit/figure_diagnostics.py` | Parameter-change render hook forwards updates into the sound manager. | `figure_diagnostics.py:463-471` |
| `src/gu_toolkit/figure_plot_helpers.py` | Plot removal currently does **not** notify the sound manager. | `figure_plot_helpers.py:180-185` |
| `src/gu_toolkit/figure_plot_style.py` | Documents the public `autonormalization` option, currently with old semantics. | `figure_plot_style.py:264-272` |
| `src/gu_toolkit/codegen.py` | Emits `autonormalization=True` in generated code. | `codegen.py:481-482`, `514-515` |
| `src/gu_toolkit/PlotSnapshot.py` | Stores `autonormalization` in the snapshot model. | `PlotSnapshot.py:17-130` |

### A real integration gap already present in GU

`remove_plot_from_figure(...)` removes the plot from the figure and legend, but it never informs the sound manager (`src/gu_toolkit/figure_plot_helpers.py:180-185`).

That means the engine replacement should **also** harden plot-removal handling. This is part of a complete replacement, not a side cleanup.

---

## 2) The separate `play(...)` helper

`src/gu_toolkit/numeric_operations.py:272-379` implements `play(...)`.

It is **not** the current figure-linked engine:

- it samples the whole requested interval at 44.1 kHz,
- applies whole-clip peak normalization to `0.99` (`numeric_operations.py:359-363`),
- encodes one complete WAV in memory,
- returns an inline HTML `<audio>` widget (`numeric_operations.py:366-379`).

Its current behavior is separately tested in `tests/test_prelude_nintegrate.py:163-174` and separately documented in `docs/issues/_closed/issue-003-play-autoplays-and-displays-unconditionally.md:15-33`.

### Scope decision for `play(...)`

Do **not** silently fold `play(...)` into the engine swap. That would either:

- change its normalization behavior, or
- force a browser-widget transport where the current API intentionally returns a static HTML audio object.

For this migration:

- **audit it**,
- **document it**,
- **leave it unchanged**.

Also update docs/examples so nobody mistakes it for the same engine.

---

## What exists today in jlab_function_audio

JLAB already solves the hard parts GU's current inline bridge solves only minimally.

## 1) Runtime architecture

The README explicitly describes a three-layer design:

- Python transport and buffering,
- phase matching,
- JupyterLab/browser playback (`README.md:16-35`).

Key runtime facts:

- it is a hidden non-visual helper controlled from Python (`README.md:13-15, 30-35`),
- playback supports play/stop/restart/seek (`README.md:9-13`),
- browser-side autoplay boundaries are handled through trusted notebook gestures (`README.md:62-73`; `_frontend.js:448-536`),
- last-view detach and comm teardown are explicitly handled (`README.md:117-120`; `_frontend.js:223-269, 1010-1040`; `player.py:1055-1103`).

## 2) Configuration and transport

`PlayerConfiguration` is a frozen, validated dataclass (`src/jlab_function_audio/config.py:113-280`).

Default values relevant to GU integration:

- `sample_rate = 48000`
- `chunk_duration = 0.025`
- `lookahead_duration = 0.075`
- `period_duration = 100.0`
- `gain = 0.18`
- `auto_normalize = False`

Evidence: `config.py:191-203`.

These defaults do **not** match current GU semantics and therefore must be adapted by the GU layer.

## 3) Sampling and normalization behavior

JLAB exposes clean sampling layers:

- clipped evaluation path: `evaluate_signal(...)`, `generate_chunk(...)` (`sampling.py:137-176`, `203-281`),
- raw evaluation path: `evaluate_signal_raw(...)`, `generate_raw_chunk(...)` (`sampling.py:179-200`, `284-325`),
- final safety clip helper: `clip_audio_chunk(...)` (`sampling.py:328-341`).

JLAB's bounded autonormalization is significantly stronger than GU's current per-chunk peak divide:

- local DC removal,
- bounded forward lookahead,
- attenuation-only normalization (`M >= 1`),
- release memory,
- final clip only as safety net.

Evidence:

- design constraints in `autonormalization_design.md:15-30`,
- implementation in `normalization.py:197-326`,
- tests in `tests/test_autonormalization.py:95-330`.

## 4) Player lifecycle and frontend hardening

`FunctionAudioPlayer` already provides the lifecycle GU needs:

- public traits for transport/frontend state (`player.py:286-307`),
- background pump thread (`player.py:412-449, 1419-1474`),
- public `play/stop/restart/seek/set_function/close` (`player.py:595-971`),
- transport disconnect and frontend detach handling (`player.py:1055-1256`),
- binary float32 chunk transport to the browser (`player.py:1216-1256`),
- browser-side queue reset/play/stop handling (`_frontend.js:842-931`).

The frontend and transport resilience work is explicitly documented as architectural rather than cosmetic in `FIX_REPORT.md:36-137`.

---

## Gap analysis: GU today vs. JLAB today

| Concern | GU current state | JLAB current state | Required adaptation |
|---|---|---|---|
| Package location | Built into `gu_toolkit.figure_sound` | Separate `jlab_function_audio` package | Vendor JLAB under `src/gu_toolkit/_vendor/jlab_function_audio/` and keep it GU-agnostic |
| Browser transport | Inline bridge, base64 PCM16 pull model | Hidden AnyWidget, float32 binary push model | Replace transport entirely; do not keep `_SoundStreamBridge` |
| Sample rate | 44.1 kHz | 48 kHz default | Override vendor config to 44.1 kHz |
| Loop period | 60 s | 100 s default | Override vendor config to 60 s |
| Output gain | implicit full scale | `gain=0.18` default | Override vendor config to `1.0` |
| Active-playback policy | one active plot per figure | one active callable per player | Preserve GU one-active-plot policy in adapter |
| Restart semantics | explicit restart from 0 on `plot.sound(True)` | `set_function(...)` can phase-match and continue | Use `phase_match=False`; explicit `seek(0.0)` for GU starts |
| Parameter-change semantics | flush future audio, keep cursor | player already supports queue reset/seek | On parameter change, flush from current cursor |
| Autonormalization granularity | per plot | player-wide config | Add generic player API `set_auto_normalize(...)` and map GU per-plot state to the active player |
| Validation without autonormalization | GU raises synchronously when first chunk exceeds range | JLAB clipped path would otherwise clip | Keep GU-side synchronous preflight and strict adapter validation |
| Plot evaluation style | vectorized NumPy evaluation | scalar callable sampling by design | Use a GU-side batched scalar adapter |
| Frontend attach model | bridge inserted into figure root | `play()` auto-displays if never shown | Add generic player API `mark_embedded()` and attach player widget under figure root |
| Removal handling | plot removal does not notify sound manager | player supports stop/close | Add `on_plot_removed(...)` handling in GU |
| Docs/tooltips | describe naive peak-scaling semantics | documents bounded autonormalization | Update GU docs/tooltips to match new truth |
| Test coverage | GU tests public behavior, some transport specifics | strong normalization/frontend regression tests | Keep GU public-contract tests and import JLAB regression tests into GU CI |

---

## Recommended target architecture

```text
Plot / parameters / legend / render hooks
                |
                v
      FigureSoundManager (GU adapter)
      - preserves GU public API
      - enforces GU compatibility policy
      - performs strict preflight validation
      - adapts vectorized plot evaluation efficiently
                |
                v
vendored gu_toolkit._vendor.jlab_function_audio.FunctionAudioPlayer
      - transport clock
      - browser queueing
      - hidden AnyWidget frontend
      - bounded autonormalization
      - frontend detach / comm resilience
                |
                v
       Web Audio in the notebook browser
```

### Rules for the target architecture

1. **All GU-specific logic stays in GU code.**
   The vendored JLAB package must not import GU or mention GU types.

2. **The old GU browser bridge is removed completely.**
   `_SoundStreamBridge` is not kept as a compatibility wrapper.

3. **The vendored package remains a real subpackage.**
   It is not flattened into `figure_sound.py`, and its internal module boundaries remain intact.

4. **GU preserves public behavior at its own boundary.**
   GU, not JLAB, is responsible for:
   - one active plot per figure,
   - strict no-autonormalization validation,
   - restart-from-zero semantics,
   - mapping parameter changes to queue flushes,
   - legend state.

5. **JLAB owns the runtime engine after the adapter boundary.**
   JLAB, not GU, owns:
   - buffering,
   - frontend lifecycle,
   - browser unlock handling,
   - float32 chunk transport,
   - bounded autonormalization math.

---

## Why the replacement must be an adapter, not a transplant

GU's current engine is built around `plot.numeric_expression(x_values)` over a full NumPy array (`figure_sound.py:466-489`).

JLAB is intentionally scalar-callable-first (`sampling.py:156-159`).

Trying to force one directly into the other in either direction is the wrong abstraction boundary:

- pasting JLAB transport code into GU would destroy JLAB independence,
- rewriting JLAB around GU plot objects would destroy vendor isolation,
- using a naive one-sample wrapper around GU numeric evaluation would create an unnecessary performance regression.

### Performance evidence for a batched scalar adapter

A local benchmark in the analysis environment compared two GU->JLAB adaptation strategies for a representative mixed expression at **44.1 kHz** with **2205 samples per chunk**:

- naive scalar wrapper: **15.927 ms/chunk**
- batched scalar wrapper: **0.861 ms/chunk**
- improvement: **18.5x**

A second benchmark at JLAB's 1200-sample chunk size showed similar behavior:

- simple sine: `2.446 ms` naive vs `0.456 ms` batched
- mixed expression: `8.719 ms` naive vs `0.452 ms` batched

Conclusion: a GU-side batching adapter is required. It keeps JLAB generic and keeps GU from regressing badly when using symbolic/vectorized plot evaluation.

This is a deliberate architectural bridge, not a patch-level micro-optimization.

---

## Vendor strategy

## 1) Where to vendor JLAB

Recommended path:

```text
src/
  gu_toolkit/
    _vendor/
      __init__.py
      jlab_function_audio/
        __init__.py
        config.py
        matching.py
        normalization.py
        player.py
        sampling.py
        _frontend.js
        _frontend.css
        py.typed
        LICENSE
        README.md
        VENDORED_FROM.md
```

### Why this location

- It satisfies the requirement to copy JLAB into a subdirectory of `src\gu_toolkit`.
- It keeps the code independent as a real package subtree.
- `pyproject.toml` already discovers `gu_toolkit*` packages (`gu_toolkit/pyproject.toml:34-36`), so the vendored package will be included automatically as a Python package.

## 2) Provenance requirements

Add `VENDORED_FROM.md` beside the vendored package with:

- upstream package name and version (`0.1.5` from `src/jlab_function_audio/__init__.py:69` / `pyproject.toml:6-8`),
- archive hash used for vendoring,
- list of exact files changed after vendoring,
- reason for each deliberate change.

This is mandatory. Without it, future updates become guesswork.

## 3) Packaging changes required in GU

`gu_toolkit/pyproject.toml` currently only includes package data for the top-level `gu_toolkit` package (`pyproject.toml:39-40`).

Add package-data entries for the vendored frontend assets:

```toml
[tool.setuptools.package-data]
"gu_toolkit" = ["css/*.css", "math_input/*.css", "math_input/*.js"]
"gu_toolkit._vendor.jlab_function_audio" = ["*.js", "*.css", "py.typed"]
```

### Dependency floors

JLAB declares the following minimum versions (`jlab_function_audio/pyproject.toml:31-36`):

- `numpy>=1.25`
- `traitlets>=5.10`
- `IPython>=8.0`
- `anywidget>=0.9.0`
- `ipywidgets>=8.1.0`

GU currently leaves those unpinned (`gu_toolkit/pyproject.toml:10-18`).

Recommended action:

- raise GU's dependency floors to at least JLAB's tested minima, **or**
- run and document an explicit compatibility matrix proving older versions still work.

Do **not** silently assume compatibility.

---

## Required vendor changes

Only two runtime changes should be made inside the vendored package, and both should be public and generic.

## A) Add `FunctionAudioPlayer.mark_embedded()`

### Why it is necessary

`FunctionAudioPlayer.play()` currently auto-calls `show()` if `_auto_display_has_run` is false (`player.py:621-623`). `show()` calls `display(self)` (`player.py:569-593`).

GU needs to attach the widget as a hidden child of the figure root, not display it as a separate notebook output.

Using `player._auto_display_has_run = True` from GU would be a bad private-state shortcut.

### Required API

Add a public method with semantics like:

```python
def mark_embedded(self) -> "FunctionAudioPlayer":
    """Mark the widget as already attached by an external container.

    After this call, play() must not auto-display the widget.
    """
```

Implementation can be small, but the method must be public and documented.

## B) Add `FunctionAudioPlayer.set_auto_normalize(enabled: bool)`

### Why it is necessary

GU's `autonormalization` is **per plot** (`figure_plot.py:2201-2262`).
JLAB's normalization mode is currently a **player configuration field** (`config.py:199`, `player.py:1288-1385`).

Recreating the player when the active plot changes mode is technically possible, but it is not the right solution:

- it destroys the existing browser-helper instance,
- it resets JLAB's unlock state,
- and because frontend audio unlock is helper-local (`_frontend.js:448-510`), it can force another notebook gesture.

That is a real UX regression.

### Required API

Add a public method with semantics like:

```python
def set_auto_normalize(self, enabled: bool) -> None:
    """Switch between clipped and bounded-autonormalized render modes.

    The method must preserve the current transport position and play intent,
    reset normalization state appropriately, and flush any already-buffered
    audio rendered under the old mode.
    """
```

### Design requirements for `set_auto_normalize(...)`

- It must not create a new widget instance.
- It must not require GU to touch `_configuration` directly.
- It must update the player's synced `auto_normalize` trait.
- It must reset normalization state when the mode changes.
- It must flush queued audio from the current cursor so no stale old-mode audio remains in the browser queue.
- It must be covered by new vendor-side tests.

---

## GU-side implementation blueprint

## 1) Rewrite `FigureSoundManager` as a GU adapter

`src/gu_toolkit/figure_sound.py` should keep the public class name `FigureSoundManager`, but its internals should be replaced.

### Public API that must remain unchanged

- `enabled`
- `active_plot_id`
- `sound_generation_enabled(...)`
- `sound(plot_id, run=True)`
- `on_parameter_change(...)`

Evidence that this is the public surface: `figure_sound.py:358-359` and call sites listed above.

### New internal state to maintain

Recommended state fields:

- `self._figure`
- `self._legend`
- `self._root_widget`
- `self._enabled`
- `self._active_plot_id`
- `self._player` — lazy, initially `None`
- `self._player_embedded` — whether current player has been attached into the root widget
- `self._player_state_observer_guard` — suppress recursive observer reactions during manager-initiated control operations
- `self._active_signal_adapter` — current GU batching adapter for the active plot
- `self._finalizer` — closes the player on manager GC

Also add a **private factory seam** for tests, for example a module-level `_PLAYER_CLASS` / `_PLAYER_CONFIG_CLASS` or a private `_create_player(...)` helper. GU integration tests should be able to inject a fake player without importing the real vendored widget runtime.

### New manager constants

Keep these GU compatibility constants:

- `sample_rate = 44100`
- `loop_seconds = 60.0`
- `start_validation_seconds = 1.0`
- `value_tolerance = 1e-9`

Do **not** keep `chunk_seconds = 1.0` as a transport contract. JLAB's chunking should remain JLAB's job.

## 2) Use one lazy player per figure

### Required configuration when creating the player

Instantiate the vendored player with a `PlayerConfiguration` that matches GU semantics where it matters:

- `sample_rate=44100`
- `period_duration=60.0`
- `gain=1.0`
- `auto_normalize=False` initially
- keep JLAB timing defaults unless profiling later proves they must change

Why those overrides are mandatory:

- GU current engine is 44.1 kHz (`figure_sound.py:406`).
- GU current loop is 60 seconds (`figure_sound.py:408`).
- JLAB's default `gain=0.18` would silently attenuate GU output (`config.py:198`).

### Why the player must be lazy

GU constructs `FigureSoundManager` for every figure at `Figure.__init__` time (`Figure.py:441-445`).

JLAB player construction starts a background thread immediately (`player.py:412-449`).

Creating that player eagerly for every figure would be wasteful and would also make all figures depend on widget runtime availability even if sound is never used. That matters because GU currently tolerates missing real `anywidget` via a local fallback stub (`src/gu_toolkit/_widget_stubs.py:2398-2424`), while JLAB's fallback `FunctionAudioPlayer` placeholder raises when widget dependencies are missing (`src/jlab_function_audio/__init__.py:72-130`).

Therefore: **do not create the player in `Figure.__init__` or `FigureSoundManager.__init__`.**
Create it only on first actual sound start.

## 3) Attach the player into the figure root

When the player is first created:

1. construct it with `auto_display=False`,
2. append it to `root_widget.children` if a root widget exists,
3. call `player.mark_embedded()`,
4. register trait observers.

If `root_widget is None`, skip embedding and let the player use its normal display path.

### Cleanup requirements

Add a private helper that removes the player widget from `root_widget.children` before `player.close()` when the manager is explicitly closed or finalized.

Even though GU currently has no public `Figure.close()`, the manager should still own best-effort cleanup.

## 4) Implement a GU batching signal adapter

This adapter is the core GU-specific bridge.

### Responsibilities

- present a scalar callable to JLAB,
- evaluate GU plots in vectorized batches,
- preserve GU's finite/range validation semantics,
- wrap times into the fixed 60-second period,
- avoid naive per-sample `plot.numeric_expression(np.array([t]))` overhead.

### Required behavior

Recommended private class shape:

```python
class _PlotSignalAdapter:
    def __init__(self, plot, *, sample_rate, period, batch_samples, allow_over_range): ...
    def __call__(self, t: float) -> float: ...
    def preflight(self, *, start_seconds: float, duration_seconds: float) -> None: ...
```

### `__call__` behavior

On cache miss:

- build one vectorized time array of `batch_samples`,
- wrap times with `np.mod(..., period)`,
- evaluate `plot.numeric_expression(times)` once,
- coerce to a 1-D float array,
- validate shape,
- validate finiteness always,
- if `allow_over_range` is false, also validate `abs(value) <= 1 + tolerance` for every sample,
- cache the batch and return the requested sample.

### `preflight(...)` behavior

For GU compatibility, `preflight(...)` must synchronously validate the **first full second** of audio before `plot.sound(True)` returns.

That preserves the important current user-facing behavior: obvious out-of-range or non-finite failures show up immediately on start, not later in the pump thread.

Rules:

- always validate finiteness,
- when `autonormalization=False`, validate `[-1, 1]` over the full first second,
- when `autonormalization=True`, allow finite values outside `[-1, 1]` but still fail on non-finite values.

### Why this preflight is necessary even though JLAB already renders chunks

JLAB's default clipped path would otherwise clip loud samples silently (`sampling.py:91-115, 137-176`).
GU currently raises on start for loud signals without autonormalization (`tests/test_figure_sound.py:195-203`).

The preflight is therefore a compatibility requirement, not duplicated work.

## 5) Preserve GU start/stop/restart semantics exactly

### `sound(plot_id, run=True)`

Required behavior:

1. if `run=False` and this plot is active, stop playback and clear legend state,
2. if sound generation is disabled, raise the same `RuntimeError` style GU already uses,
3. resolve the plot and its current `autonormalization` flag,
4. preflight the first second,
5. ensure the player exists,
6. call `player.set_auto_normalize(plot.autonormalization())` if needed,
7. install a fresh `_PlotSignalAdapter` with `player.set_function(..., phase_match=False)`,
8. `player.seek(0.0)`,
9. `player.play()`,
10. set `self._active_plot_id` and legend state.

### Important note

Do **not** use JLAB phase matching here. GU's existing restart behavior is explicit restart-from-zero (`tests/test_figure_sound.py:82-106`).

`phase_match=False` is the correct adaptation.

## 6) Preserve GU parameter-change semantics

Current GU behavior is "refresh queued audio so future chunks use the latest parameter values" (`figure_sound.py:698-759`).

Recommended implementation:

- if nothing is active, return,
- if the active plot was removed, stop playback,
- if the active plot's `autonormalization` flag no longer matches the player, call `player.set_auto_normalize(...)`,
- otherwise call `player.seek(player.position)`.

Why `seek(player.position)` is the right operation:

- it preserves the audible cursor,
- it flushes stale buffered audio from the browser queue,
- and because the active `_PlotSignalAdapter` reads the plot dynamically, future renders naturally use the latest parameter values.

Do **not** call `set_function(...)` on every parameter change. That would unnecessarily invoke JLAB's function-swap path and would change semantics.

## 7) Handle asynchronous terminal states from the player

The manager must observe the vendored player's traitlets, especially:

- `playback_state`
- `last_error`

Required reaction:

- if the player transitions to a terminal stopped state because of an error, clear `self._active_plot_id` and legend playing state,
- preserve active state during `waiting-for-display` / `waiting-for-browser-gesture` / `playing`,
- suppress observer reactions during manager-initiated control operations to avoid recursive churn.

This is necessary because JLAB can stop itself asynchronously when the pump hits an exception (`player.py:1387-1418`).
GU's legend state must stay truthful.

## 8) Add plot-removal handling

Add a new manager method:

```python
def on_plot_removed(self, plot_id: str) -> None: ...
```

and call it from `remove_plot_from_figure(...)` before legend cleanup.

Required behavior:

- if the removed plot is active, stop playback and clear state,
- otherwise no-op.

This closes a real GU integration hole.

## 9) Add manager cleanup

Add:

```python
def close(self) -> None: ...
```

Responsibilities:

- stop playback if needed,
- detach the embedded widget from the root,
- unregister observers,
- call `player.close()`,
- clear references.

Also register a `weakref.finalize(...)` fallback so the player thread does not outlive garbage-collected figures indefinitely.

---

## File-by-file work plan

| File | Action | Required change |
|---|---|---|
| `pyproject.toml` | modify | add package-data for vendored JS/CSS/py.typed; align dependency floors or document compatibility matrix |
| `src/gu_toolkit/_vendor/__init__.py` | new | empty or minimal namespace marker |
| `src/gu_toolkit/_vendor/jlab_function_audio/*` | new | vendored runtime package copied from JLAB |
| `src/gu_toolkit/_vendor/jlab_function_audio/player.py` | modify vendor | add `mark_embedded()` and `set_auto_normalize(...)`; no GU-specific imports |
| `src/gu_toolkit/_vendor/jlab_function_audio/README.md` | copy | preserve upstream docs inside vendor subtree |
| `src/gu_toolkit/_vendor/jlab_function_audio/LICENSE` | copy | preserve MIT license |
| `src/gu_toolkit/_vendor/jlab_function_audio/VENDORED_FROM.md` | new | provenance and patch ledger |
| `src/gu_toolkit/figure_sound.py` | rewrite internals | remove `_SoundStreamBridge`; implement adapter architecture |
| `src/gu_toolkit/figure_plot_helpers.py` | modify | notify sound manager on plot removal |
| `src/gu_toolkit/figure_plot_style.py` | modify text | update `autonormalization` description to bounded/local semantics |
| `src/gu_toolkit/figure_legend.py` | modify text | update checkbox tooltip text to accurate new semantics |
| `examples/Toolkit_overview.ipynb` | modify | stop claiming figure-linked sound never auto-normalizes |
| `docs/guides/api-discovery.md` | optional wording refresh | clarify that `play(...)` and figure-linked sound are separate workflows |
| `tests/test_figure_sound.py` | rewrite | move from legacy bridge-message assertions to adapter/public-behavior assertions |
| `tests/test_Figure_module_params.py` | keep/update | preserve `autonormalization` kwarg/update coverage |
| `tests/test_legend_context_menu.py` | keep/update | preserve style-dialog checkbox integration |
| `tests/test_prelude_nintegrate.py` | keep | confirms `play(...)` remains unchanged |
| `tests/vendor_jlab/test_autonormalization.py` | new/adapted | copy/adapt JLAB normalization tests under vendored import path |
| `tests/vendor_jlab/frontend_activation_boundary.mjs` | new/adapted | copy/adapt JLAB frontend activation test |
| `tests/vendor_jlab/frontend_comm_resilience.mjs` | new/adapted | copy/adapt JLAB comm lifecycle test |
| `tests/vendor_jlab/test_frontend_autoplay_policy.mjs` | new/adapted | copy/adapt JLAB autoplay-policy test |
| `tests/test_vendored_jlab_packaging.py` or CI script | new | verify wheel includes vendored frontend assets |

---

## Detailed implementation sequence

## Phase 1 — Vendor JLAB cleanly

1. Copy the JLAB runtime package into `src/gu_toolkit/_vendor/jlab_function_audio/`.
2. Copy `README.md`, `LICENSE`, and `py.typed` with it.
3. Add `VENDORED_FROM.md`.
4. Update `pyproject.toml` package-data entries.
5. Add vendored-package smoke imports.

### Exit criteria

- `python -c "import gu_toolkit._vendor.jlab_function_audio"` works,
- no `gu_toolkit` imports exist inside the vendored package,
- built wheel contains vendored `_frontend.js`, `_frontend.css`, and `py.typed`.

## Phase 2 — Add the two vendor public APIs

1. Implement `mark_embedded()`.
2. Implement `set_auto_normalize(enabled)`.
3. Add vendor tests for those methods.
4. Record those edits in `VENDORED_FROM.md`.

### Exit criteria

- GU no longer needs to touch vendor private state,
- the same player instance can toggle normalization mode without recreation,
- vendor tests are green.

## Phase 3 — Rewrite `FigureSoundManager`

1. Delete `_SoundStreamBridge` and all related message/generation-token logic.
2. Introduce lazy player creation.
3. Introduce `_PlotSignalAdapter` and 1-second preflight validation.
4. Preserve GU public methods and legend updates.
5. Add trait observers for terminal player states.
6. Add manager cleanup.

### Exit criteria

- figure-linked sound runtime no longer depends on `_SoundStreamBridge`,
- starting/restarting/stopping plots still behaves as current GU tests require,
- strict no-autonormalization errors are still synchronous on start,
- legend state stays correct on async player errors.

## Phase 4 — Integrate plot removal and docs

1. Notify sound manager on plot removal.
2. Update tooltip/description text for `autonormalization`.
3. Update the example notebook section that currently says figure-linked sound does not auto-normalize.
4. Clarify docs that `play(...)` remains the separate quick inline helper.

### Exit criteria

- active playback stops cleanly when the active plot is removed,
- public docs stop describing the old chunk-peak scaling path.

## Phase 5 — Rebuild test coverage

1. Rewrite GU integration tests around a fake player implementing the **public** vendor surface.
2. Import/adapt JLAB's normalization tests.
3. Import/adapt JLAB's frontend Node tests.
4. Add packaging verification.
5. Keep `play(...)` tests unchanged.

### Exit criteria

- GU tests prove public GU behavior,
- vendor tests prove the vendored engine behavior,
- no critical audio behavior is covered only by manual testing.

---

## Test plan and proof obligations

## A) GU integration tests (adapter-level)

These tests should **not** depend on real browser audio. Use a fake player through a private factory seam.

Required cases:

1. **default enabled state and legend button visibility**
2. **context-menu enable/disable toggle**
3. **start / restart / stop semantics**
4. **switching between plots**
5. **parameter change flushes from current cursor**
6. **out-of-range start raises synchronously without autonormalization**
7. **autonormalization allows loud finite start**
8. **changing active plot's autonormalization flips player mode**
9. **removing the active plot stops playback**
10. **async player error clears legend active state**

What to assert against the fake player:

- `set_function(..., phase_match=False)` was used,
- `seek(0.0)` happened on explicit starts,
- `seek(current_position)` happened on parameter refreshes,
- `set_auto_normalize(...)` happened only when mode changed,
- `close()` is called on manager cleanup.

## B) Vendored JLAB regression tests

Adapt and run the following from the JLAB repo:

- `tests/test_autonormalization.py`
- `tests/frontend_activation_boundary.mjs`
- `tests/frontend_comm_resilience.mjs`
- `tests/test_frontend_autoplay_policy.mjs`

Why these matter:

- they prove the bounded normalization math,
- they prove the activation boundary,
- they prove comm/detach lifecycle handling,
- they prove the frontend hardening is architectural rather than a `try/catch` band-aid.

## C) Packaging test

Add one automated check that builds the GU wheel and asserts the following files are present:

- `gu_toolkit/_vendor/jlab_function_audio/_frontend.js`
- `gu_toolkit/_vendor/jlab_function_audio/_frontend.css`
- `gu_toolkit/_vendor/jlab_function_audio/py.typed`

## D) Manual notebook smoke tests

Run all of the following in a real JupyterLab session:

1. start sound from a plot, then move a parameter slider,
2. switch from one plot to another,
3. toggle `autonormalization` on the active plot while audio is running,
4. disable and re-enable figure sound generation,
5. remove the active plot while it is playing,
6. close/remove the notebook output and confirm no repeated `Cannot send` spam appears,
7. restart playback after a normal browser gesture unlock.

---

## Rejected shortcuts and why they are unacceptable

## 1) Keeping `_SoundStreamBridge` and using JLAB only for normalization

Rejected because it would not replace the engine. The old GU browser transport would still be in charge.

Proof obligation after implementation:

```bash
grep -R "_SoundStreamBridge" -n src/gu_toolkit
```

Expected result: **no hits** outside historical docs/tests snapshots.

## 2) Touching vendored private attributes from GU

Examples of forbidden shortcuts:

- `_auto_display_has_run`
- `_state_lock`
- `_configuration`
- `_generated_until_unwrapped`
- any underscore-prefixed transport internals

GU must use vendor public APIs only.

Proof obligation:

```bash
grep -R "_auto_display_has_run\|_configuration\|_state_lock" -n src/gu_toolkit
```

Expected result: hits only inside the vendored package itself, not in GU adapter code.

## 3) Recreating the player on every autonormalization change

Rejected because it resets the helper-local unlock state and can force extra browser gestures. That is an avoidable regression given JLAB's activation model (`_frontend.js:448-510`).

Preferred solution: `set_auto_normalize(...)` on the same player instance.

## 4) Always forcing `auto_normalize=True`

Rejected because it changes current GU semantics. GU explicitly distinguishes strict mode from normalized mode (`figure_plot.py:2201-2262`; `tests/test_figure_sound.py:195-231`).

## 5) Keeping GU's old per-chunk peak divide for `autonormalization=True`

Rejected because that is not a JLAB engine replacement. JLAB's bounded autonormalization is a materially different and better algorithm (`normalization.py:197-326`).

## 6) Using a naive scalar wrapper for GU plot evaluation

Rejected because the measured cost is much higher than a batched adapter. That would be a real performance regression.

## 7) Eager player construction in `Figure.__init__`

Rejected because every figure would start a background thread whether or not sound is ever used.

## 8) Deleting or weakening GU tests without replacing coverage

Rejected because transport details will change but public behavior must still be proven.

## 9) Ignoring `play(...)`

Rejected because the repo exposes it publicly and documents it as one of the sound workflows (`docs/guides/api-discovery.md:63`; `examples/Toolkit_overview.ipynb`, markdown cells 0 and 21).

The correct treatment is: audited, explicitly out of scope, unchanged.

## 10) Letting vendored JLAB absorb GU-specific imports or logic

Rejected because it breaks the requirement that JLAB remain independent.

Proof obligation:

```bash
grep -R "gu_toolkit" -n src/gu_toolkit/_vendor/jlab_function_audio
```

Expected result: no hits except the vendoring note/provenance file.

---

## Acceptance checklist for code review

A developer implementation is acceptable only if **all** of the following are true:

- [ ] `_SoundStreamBridge` is gone from runtime code.
- [ ] `FigureSoundManager` public API is unchanged.
- [ ] figure-linked sound is now powered by vendored JLAB transport/frontend/runtime.
- [ ] JLAB remains in `src/gu_toolkit/_vendor/jlab_function_audio/` and remains GU-agnostic.
- [ ] vendor patch ledger exists and is complete.
- [ ] GU does not touch vendored private attributes.
- [ ] no-autonormalization start validation still fails synchronously.
- [ ] `autonormalization=True` uses JLAB bounded autonormalization, not GU legacy peak scaling.
- [ ] explicit plot restarts still start from `0.0`.
- [ ] parameter changes flush stale buffered audio from the current cursor.
- [ ] removing the active plot stops playback cleanly.
- [ ] wheel packaging includes vendored JS/CSS assets.
- [ ] GU integration tests are green.
- [ ] vendored JLAB regression tests are green.
- [ ] docs/tooltips no longer describe the old normalization behavior.
- [ ] `play(...)` behavior and tests remain unchanged.

---

## Suggested commands for final validation

```bash
# Python tests
PYTHONPATH=src pytest -q \
  tests/test_figure_sound.py \
  tests/test_Figure_module_params.py \
  tests/test_legend_context_menu.py \
  tests/test_prelude_nintegrate.py \
  tests/vendor_jlab/test_autonormalization.py

# Frontend regression tests
node --experimental-default-type=module tests/vendor_jlab/frontend_activation_boundary.mjs
node --experimental-default-type=module tests/vendor_jlab/frontend_comm_resilience.mjs
node --experimental-default-type=module tests/vendor_jlab/test_frontend_autoplay_policy.mjs

# Packaging smoke test
python -m build
python - <<'PY'
from pathlib import Path
from zipfile import ZipFile
wheel = max(Path('dist').glob('*.whl'))
with ZipFile(wheel) as zf:
    names = set(zf.namelist())
required = {
    'gu_toolkit/_vendor/jlab_function_audio/_frontend.js',
    'gu_toolkit/_vendor/jlab_function_audio/_frontend.css',
    'gu_toolkit/_vendor/jlab_function_audio/py.typed',
}
missing = sorted(required - names)
assert not missing, missing
print('wheel contains vendored frontend assets')
PY

# Anti-shortcut sanity checks
grep -R "_SoundStreamBridge" -n src/gu_toolkit || true
grep -R "gu_toolkit" -n src/gu_toolkit/_vendor/jlab_function_audio || true
grep -R "_auto_display_has_run\|_configuration\|_state_lock" -n src/gu_toolkit || true
```

---

## Final recommendation

Proceed with the engine replacement, but do it as a **strict adapter-over-vendored-engine migration**.

That means:

- vendor JLAB cleanly,
- add only the two public vendor APIs GU truly needs,
- rewrite `FigureSoundManager` around that vendor engine,
- keep GU public behavior explicit and tested,
- leave `play(...)` unchanged and documented as a separate helper.

That path is comprehensive, maintainable, and honest about the real scope.
It replaces the engine rather than papering over it.
