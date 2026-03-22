# Parameter animation

The animation system is built around the existing parameter stack instead of bypassing it.

## Where it lives

- `gu_toolkit.animation.AnimationClock` provides a shared 60 Hz cadence.
- `gu_toolkit.animation.AnimationController` owns the continuous internal animation state for one parameter.
- `gu_toolkit.Slider.FloatSlider` hosts the play/pause button and the animation settings in the existing cogwheel popup.
- `gu_toolkit.ParamRef.ProxyParamRef` surfaces animation settings and controls through the normal `ParamRef` API.

## Behavioral rules

- The controller keeps a continuous internal value.
- Before applying a value to the widget, the controller quantizes it to an admissible slider value.
- Admissible values follow the current `min` / `max` / `step` configuration and include the exact range endpoints.
- If quantization would not change the current parameter value, no update is emitted.
- When range or step settings change, the displayed value is re-quantized immediately.
- The internal value is preserved unless it falls outside the new numeric range; in that case it is reset to the closest admissible value and animation continues.

## Public API

For standard slider-backed parameters, `ParamRef` now exposes:

- `animation_time`
- `animation_mode`
- `animation_running`
- `start_animation()`
- `stop_animation()`
- `toggle_animation()`

Animation metadata also appears in `ParameterManager.snapshot(full=True)` when the backing control supports it.
